"""Transactional vector-sync outbox: PostgreSQL is the source of truth."""
import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy import text
from app.database import SessionLocal
from app.models import DiaryEntry, VectorSyncJob

logger = logging.getLogger(__name__)

def enqueue_sync(db, entry_id):
    # Insert in the same transaction as the diary change, including deletions.
    db.add(VectorSyncJob(entry_id=entry_id))

def process_one(db, entry_id=None):
    query = db.query(VectorSyncJob).filter(VectorSyncJob.next_attempt_at <= datetime.now(timezone.utc))
    if entry_id is not None:
        query = query.filter(VectorSyncJob.entry_id == entry_id)
    job = query.order_by(VectorSyncJob.id.asc()).with_for_update(skip_locked=True).first()
    if job is None:
        db.rollback()
        return False
    job_id = job.id
    if db.get_bind().dialect.name == 'postgresql':
        locked = db.execute(text('SELECT pg_try_advisory_xact_lock(69002, :entry_id)'), {'entry_id':job.entry_id}).scalar()
        if not locked:
            db.rollback()
            return False
    try:
        from app.services.rag_service import sync_diary_entry, delete_diary_embeddings
        entry = db.get(DiaryEntry, job.entry_id)
        # Always read the current row: an old job cannot resurrect a deleted diary.
        if entry is None:
            delete_diary_embeddings(job.entry_id)
        else:
            sync_diary_entry(entry.id, entry.title, entry.content, str(entry.entry_date))
        db.delete(job)
        db.commit()
        return True
    except Exception as error:
        error_type = type(error).__name__[:100]
        db.rollback()
        failed = db.query(VectorSyncJob).filter(VectorSyncJob.id == job_id).with_for_update().first()
        if failed:
            failed.attempts += 1
            failed.last_error = error_type
            failed.next_attempt_at = datetime.now(timezone.utc) + timedelta(seconds=min(300, 2 ** min(failed.attempts, 8)))
            db.commit()
        logger.warning('Vector sync deferred (%s)', error_type)
        return False

def run_pending(entry_id=None, limit=10, session_factory=None):
    factory = session_factory or SessionLocal
    completed = 0
    for _ in range(limit):
        with factory() as db:
            if not process_one(db, entry_id):
                break
            completed += 1
    return completed

def worker(stop):
    while not stop.is_set():
        try:
            run_pending(limit=10)
        except Exception as error:
            logger.warning('Vector retry worker unavailable (%s)', type(error).__name__)
        stop.wait(15)
