"""Persistent conversations. Each successful exchange is saved atomically."""
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.auth import get_current_user
from app.models import User
from app.models import ChatConversation, ChatMessage
from app.services.chat_service import ask_diary_chatbot

router = APIRouter(prefix="/api/conversations", tags=["Chat history"])
logger = logging.getLogger(__name__)

def get_chat_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def conversation_data(conversation):
    return {"id": conversation.id, "title": conversation.title,
            "created_at": conversation.created_at, "updated_at": conversation.updated_at}

def message_data(message):
    return {"id": message.id, "role": message.role, "content": message.content,
            "sources": message.sources, "created_at": message.created_at}

class MessageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=1, max_length=4000)

@router.get("")
def list_conversations(db: Session = Depends(get_chat_db), user: User = Depends(get_current_user)):
    conversations = db.query(ChatConversation).filter(ChatConversation.user_id == user.id).order_by(ChatConversation.updated_at.desc(), ChatConversation.id.desc()).all()
    return {"conversations": [conversation_data(c) for c in conversations]}

@router.post("", status_code=201)
def create_conversation(db: Session = Depends(get_chat_db), user: User = Depends(get_current_user)):
    conversation = ChatConversation(user_id=user.id)
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation_data(conversation)

@router.get("/{conversation_id}/messages")
def get_messages(conversation_id: int, db: Session = Depends(get_chat_db), user: User = Depends(get_current_user)):
    conversation = db.query(ChatConversation).filter(ChatConversation.id == conversation_id, ChatConversation.user_id == user.id).first()
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    messages = db.query(ChatMessage).filter(ChatMessage.conversation_id == conversation_id).order_by(ChatMessage.id.asc()).all()
    return {"conversation": conversation_data(conversation), "messages": [message_data(m) for m in messages]}

@router.post("/{conversation_id}/messages")
def send_message(conversation_id: int, request: MessageRequest, db: Session = Depends(get_chat_db), user: User = Depends(get_current_user)):
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=422, detail="Question cannot be empty.")
    # Serialize simultaneous sends to the same conversation in PostgreSQL.
    conversation = db.query(ChatConversation).filter(ChatConversation.id == conversation_id, ChatConversation.user_id == user.id).with_for_update().first()
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    recent = db.query(ChatMessage).filter(ChatMessage.conversation_id == conversation_id).order_by(ChatMessage.id.desc()).limit(10).all()
    history = [{"role": m.role, "content": m.content} for m in reversed(recent)]
    try:
        result = ask_diary_chatbot(question, user_id=user.id, history=history)
        if not isinstance(result.get("answer"), str) or not result['answer'].strip():
            raise ValueError("Empty answer")
        user_message = ChatMessage(conversation_id=conversation_id, role="user", content=question, sources=[])
        assistant_message = ChatMessage(conversation_id=conversation_id, role="assistant", content=result['answer'], sources=result.get('sources', []))
        db.add(user_message)
        db.flush()
        db.add(assistant_message)
        if not recent:
            conversation.title = question[:100]
        conversation.updated_at = datetime.now(timezone.utc)
        db.flush()
        # Serialize before commit so no lazy read can fail after a successful save.
        response = {"conversation": conversation_data(conversation),
                    "messages": [message_data(user_message), message_data(assistant_message)]}
        db.commit()
        return response
    except Exception as error:
        db.rollback()
        logger.warning("Chat exchange failed: %s", type(error).__name__)
        raise HTTPException(status_code=502, detail="Unable to generate or save a response. Please try again.") from error
