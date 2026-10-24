"""Local administration: queue current entries and remove orphaned vectors."""
from app.database import SessionLocal
from app.models import DiaryEntry
from app.services.vector_sync import enqueue_sync, run_pending

def index_diary_entries(session_factory=None, vector_store=None):
    factory = session_factory or SessionLocal
    if vector_store is None:
        from app.services.rag_service import get_vector_store
        vector_store = get_vector_store()
    metadata = vector_store.get(include=['metadatas']).get('metadatas', [])
    indexed_ids = {item['entry_id'] for item in metadata if item and isinstance(item.get('entry_id'), int)}
    with factory() as db:
        live_ids = {row[0] for row in db.query(DiaryEntry.id).all()}
        # Queue both upserts and deletions. Workers decide from the current row,
        # rather than replaying stale content captured by this scan.
        for entry_id in live_ids | indexed_ids:
            enqueue_sync(db, entry_id)
        db.commit()
    completed = run_pending(limit=max(1000,len(live_ids | indexed_ids)),session_factory=factory)
    print(f'Queued vector repair for {len(live_ids)} current entries and {len(indexed_ids - live_ids)} orphaned entries. Completed {completed} jobs; remaining work will retry automatically.')

if __name__=='__main__':
    index_diary_entries()
