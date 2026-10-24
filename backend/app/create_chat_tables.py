"""Add only the two chat-history tables; existing diary tables are untouched."""
from app.database import engine
from app.models import ChatConversation, ChatMessage

if __name__ == "__main__":
    ChatConversation.__table__.create(bind=engine, checkfirst=True)
    ChatMessage.__table__.create(bind=engine, checkfirst=True)
    print("Chat history tables are ready.")
