
import logging
from contextlib import asynccontextmanager
from threading import Event, Thread
from datetime import date
from typing import Literal

from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, ConfigDict, field_validator
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from app.config import CORS_ORIGINS, MAX_REQUEST_BYTES
from app.middleware import RequestSizeLimitMiddleware
from app.services.vector_sync import enqueue_sync, run_pending, worker
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.auth import get_current_user, router as auth_router
from app.models import User
from app.models import DiaryEntry as DiaryEntryModel
from app.services.mood_analyzer import analyze_mood
from app.services.chat_service import ask_diary_chatbot
from app.services.summary_service import period_bounds, summarize_entries, SummaryTooLarge


# Logging
logger = logging.getLogger(__name__)


def sync_diary_safely(entry):
    try:
        run_pending(entry_id=entry.id)
    except Exception as error:
        logger.warning('Vector sync remains pending (%s)', type(error).__name__)


def delete_diary_embeddings_safely(entry_id: int):
    try:
        run_pending(entry_id=entry_id)
    except Exception as error:
        logger.warning('Vector deletion remains pending (%s)', type(error).__name__)


@asynccontextmanager
async def lifespan(app):
    stop = Event()
    thread = Thread(target=worker, args=(stop,), name='vector-sync', daemon=True)
    thread.start()
    try:
        yield
    finally:
        stop.set()
        thread.join(timeout=2)


# FastAPI Application
app = FastAPI(lifespan=lifespan)
app.include_router(auth_router)

@app.middleware("http")
async def private_api_cache(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith('/api/'):
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
    return response


from app.chat_history import router as chat_history_router
app.include_router(chat_history_router)


@app.exception_handler(RequestValidationError)
async def invalid_request(request, error):
    # Never echo passwords, diary input, or raw validation context.
    details = [{'loc': item['loc'], 'msg': item['msg'], 'type': item['type']} for item in error.errors()]
    return JSONResponse(status_code=422, content={'detail': details}, headers={'Cache-Control':'no-store'})

@app.exception_handler(SQLAlchemyError)
async def database_unavailable(request, error):
    logger.warning('Database operation failed (%s)', type(error).__name__)
    return JSONResponse(status_code=503, content={'detail':'The database is temporarily unavailable. Please try again.'}, headers={'Cache-Control':'no-store'})

app.add_middleware(RequestSizeLimitMiddleware, max_bytes=MAX_REQUEST_BYTES)

# Database Dependency
def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health Endpoints
@app.get("/")
def home():
    return {
        "message": "Welcome to LifeLog AI"
    }


@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "message": "FastAPI backend is running"
    }


# Diary Request Model
class DiaryEntry(BaseModel):
    model_config = ConfigDict(extra='forbid')
    title: str = Field(min_length=1, max_length=255)
    content: str = Field(min_length=1, max_length=20000)
    entry_date: date

    @field_validator('title', 'content')
    @classmethod
    def nonempty(cls, value):
        if not value.strip():
            raise ValueError('This field cannot be blank.')
        return value


# --------------------------------------------------
# CREATE DIARY
# --------------------------------------------------

@app.post("/api/diary")
def create_diary(
    entry: DiaryEntry,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # Step 1: Analyze mood using AI
    try:
        mood_analysis = analyze_mood(entry.content)

    except Exception as error:
        logger.warning(
            "Mood analysis failed: %s",
            type(error).__name__,
        )
        mood_analysis = None

    # Step 2: Create diary entry
    new_entry = DiaryEntryModel(
        user_id=user.id,
        title=entry.title,
        content=entry.content,
        entry_date=entry.entry_date,
        mood=mood_analysis.get("mood") if mood_analysis else None,
        mood_score=mood_analysis.get("mood_score") if mood_analysis else None,
        emotions=mood_analysis.get("emotions") if mood_analysis else None,
        ai_summary=mood_analysis.get("summary") if mood_analysis else None,
    )

    # Step 3: Save to PostgreSQL
    db.add(new_entry)
    db.flush()
    enqueue_sync(db, new_entry.id)
    db.commit()
    db.refresh(new_entry)

    # Step 4: Automatically sync with ChromaDB
    sync_diary_safely(new_entry)

    # Step 5: Return response
    return {
        "message": "Diary entry saved successfully",
        "warnings": [] if mood_analysis else ["Mood analysis is temporarily unavailable for this entry."],
        "entry": {
            "id": new_entry.id,
            "title": new_entry.title,
            "content": new_entry.content,
            "entry_date": new_entry.entry_date,
            "mood": new_entry.mood,
            "mood_score": new_entry.mood_score,
            "emotions": new_entry.emotions,
            "ai_summary": new_entry.ai_summary,
        },
    }


# --------------------------------------------------
# GET ALL DIARIES
# --------------------------------------------------

@app.get("/api/diary")
def get_all_diaries(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    entries = (
        db.query(DiaryEntryModel)
        .filter(DiaryEntryModel.user_id == user.id)
        .order_by(DiaryEntryModel.entry_date.desc())
        .all()
    )

    return {
        "total": len(entries),
        "entries": [
            {
                "id": entry.id,
                "title": entry.title,
                "content": entry.content,
                "entry_date": entry.entry_date,
                "created_at": entry.created_at,
                "mood": entry.mood,
                "mood_score": entry.mood_score,
                "emotions": entry.emotions,
                "ai_summary": entry.ai_summary,
            }
            for entry in entries
        ]
    }


# --------------------------------------------------
# DELETE DIARY
# --------------------------------------------------

@app.delete("/api/diary/{entry_id}")
def delete_diary(
    entry_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # Step 1: Find diary
    entry = (
        db.query(DiaryEntryModel)
        .filter(DiaryEntryModel.user_id == user.id)
        .filter(DiaryEntryModel.id == entry_id)
        .first()
    )

    if entry is None:
        raise HTTPException(
            status_code=404,
            detail="Diary entry not found"
        )

    # Step 2: Delete from PostgreSQL
    db.delete(entry)
    enqueue_sync(db, entry_id)
    db.commit()

    # Step 3: Automatically remove from ChromaDB
    delete_diary_embeddings_safely(entry_id)

    return {
        "message": "Diary entry deleted successfully"
    }


# --------------------------------------------------
# UPDATE DIARY
# --------------------------------------------------


@app.put("/api/diary/{entry_id}")
def update_diary(
    entry_id: int,
    updated_entry: DiaryEntry,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # Step 1: Find the existing diary
    entry = (
        db.query(DiaryEntryModel)
        .filter(DiaryEntryModel.user_id == user.id)
        .filter(DiaryEntryModel.id == entry_id)
        .first()
    )

    if entry is None:
        raise HTTPException(
            status_code=404,
            detail="Diary entry not found"
        )

    # Step 2: Check whether diary content changed
    content_changed = (
        entry.content != updated_entry.content
    )

    # Step 3: Update diary fields
    entry.title = updated_entry.title
    entry.content = updated_entry.content
    entry.entry_date = updated_entry.entry_date

    # Step 4: Recalculate mood if content changed
    if content_changed or entry.mood_score is None:
        try:
            mood_analysis = analyze_mood(
                updated_entry.content
            )

            entry.mood = mood_analysis.get("mood")
            entry.mood_score = mood_analysis.get(
                "mood_score"
            )
            entry.emotions = mood_analysis.get(
                "emotions"
            )
            entry.ai_summary = mood_analysis.get(
                "summary"
            )

        except Exception as error:
            logger.warning("Mood analysis failed while updating (%s)", type(error).__name__)

            # Clear stale mood information
            entry.mood = None
            entry.mood_score = None
            entry.emotions = None
            entry.ai_summary = None

    # Save the diary and its pending vector job atomically.
    enqueue_sync(db, entry.id)
    db.commit()
    db.refresh(entry)

    # Step 6: Synchronize updated content with ChromaDB
    sync_diary_safely(entry)

    # Step 7: Return updated diary with mood analysis
    return {
        "message": "Diary entry updated successfully",
        "warnings": [] if entry.mood_score is not None else ["Mood analysis is temporarily unavailable for this entry."],
        "entry": {
            "id": entry.id,
            "title": entry.title,
            "content": entry.content,
            "entry_date": entry.entry_date,
            "created_at": entry.created_at,
            "mood": entry.mood,
            "mood_score": entry.mood_score,
            "emotions": entry.emotions,
            "ai_summary": entry.ai_summary,
        }
    }


# --------------------------------------------------
# AI MOOD ANALYSIS
# --------------------------------------------------

class MoodAnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=20000)


@app.post("/api/analyze-mood")
def analyze_diary_mood(
    request: MoodAnalysisRequest,
    user: User = Depends(get_current_user),
):
    if not request.text.strip():
        raise HTTPException(
            status_code=400,
            detail="Diary text cannot be empty"
        )

    try:
        analysis = analyze_mood(request.text)

        return {
            "message": "Mood analyzed successfully",
            "analysis": analysis
        }

    except Exception as error:
        logger.warning("AI mood analysis failed (%s)", type(error).__name__)

        raise HTTPException(
            status_code=502,
            detail="Mood analysis is temporarily unavailable. Please try again."
        ) from error


# --------------------------------------------------
# AI DIARY CHATBOT
# --------------------------------------------------

class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=1, max_length=4000)


@app.post("/api/chat")
def chat_with_diary(
    request: ChatRequest,
    user: User = Depends(get_current_user),
):
    """
    Answer diary-related questions using
    LangChain, ChromaDB, and an LLM.
    """

    question = request.question.strip()

    if not question:
        raise HTTPException(
            status_code=400,
            detail="Question cannot be empty.",
        )

    try:
        result = ask_diary_chatbot(question, user_id=user.id)

        return {
            "message": "Chat response generated successfully",
            "answer": result["answer"],
            "sources": result["sources"],
        }

    except Exception as error:
        logger.warning("AI chatbot failed (%s)", type(error).__name__)

        raise HTTPException(
            status_code=502,
            detail="Unable to generate chatbot response.",
        ) from error

# Weekly and monthly summaries (calendar boundaries, inclusive dates).

class DiarySummaryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    period: Literal["weekly", "monthly"]
    anchor_date: date

@app.post("/api/diary-summary")
def generate_diary_summary(request: DiarySummaryRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        start, end = period_bounds(request.period, request.anchor_date)
    except (ValueError, OverflowError):
        raise HTTPException(status_code=422, detail="Choose a date within a supported calendar period.")
    entries = (
        db.query(DiaryEntryModel)
        .filter(DiaryEntryModel.user_id == user.id)
        .filter(DiaryEntryModel.entry_date >= start, DiaryEntryModel.entry_date <= end)
        .order_by(DiaryEntryModel.entry_date.asc(), DiaryEntryModel.id.asc())
        .all()
    )
    try:
        return summarize_entries(entries, request.period, start, end)
    except SummaryTooLarge as error:
        raise HTTPException(status_code=413, detail=str(error)) from error
    except Exception as error:
        # Do not log provider payloads, diary contents, or credentials.
        logger.warning("Diary summary failed: %s", type(error).__name__)
        raise HTTPException(status_code=502, detail="Unable to generate a summary. Please try again.") from error


# Evidence-backed emotion patterns for the selected calendar period.
@app.post("/api/diary-insights")
def generate_diary_insights(request: DiarySummaryRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from app.services.insight_service import analyze_patterns

    try:
        start, end = period_bounds(request.period, request.anchor_date)
    except (ValueError, OverflowError):
        raise HTTPException(status_code=422, detail="Choose a date within a supported calendar period.")
    entries = (
        db.query(DiaryEntryModel)
        .filter(DiaryEntryModel.user_id == user.id)
        .filter(DiaryEntryModel.entry_date >= start, DiaryEntryModel.entry_date <= end)
        .order_by(DiaryEntryModel.entry_date.asc(), DiaryEntryModel.id.asc())
        .all()
    )
    try:
        return analyze_patterns(entries, request.period, start, end)
    except SummaryTooLarge as error:
        raise HTTPException(status_code=413, detail=str(error)) from error
    except Exception as error:
        logger.warning("Diary insights failed: %s", type(error).__name__)
        raise HTTPException(status_code=502, detail="Unable to generate insights. Please try again.") from error

