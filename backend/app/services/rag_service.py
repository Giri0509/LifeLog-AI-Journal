
from pathlib import Path

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from app.services.embedding_service import get_embedding_model

# Store vector database files inside the backend directory.
BACKEND_DIR = Path(__file__).resolve().parents[2]
CHROMA_DIR = BACKEND_DIR / "chroma_db"


# Split long diary entries into smaller searchable chunks.
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=100,
)


def prepare_diary_documents(
    entry_id: int,
    title: str,
    content: str,
    entry_date: str,
) -> list[Document]:
    """
    Convert a diary entry into LangChain documents.
    """

    text = f"Title: {title}\nDate: {entry_date}\n\n{content}"

    documents = text_splitter.create_documents(
        texts=[text],
        metadatas=[
            {
                "entry_id": entry_id,
                "title": title,
                "entry_date": entry_date,
            }
        ],
    )

    return documents


def get_vector_store() -> Chroma:
    """
    Initialize a persistent ChromaDB vector store
    using the local embedding model.
    """

    CHROMA_DIR.mkdir(parents=True, exist_ok=True)

    return Chroma(
        collection_name="diary_entries",
        embedding_function=get_embedding_model(),
        persist_directory=str(CHROMA_DIR),
    )


def cosine_similarity(left, right) -> float:
    import math
    if len(left) != len(right):
        return -1.0
    denominator = math.sqrt(sum(float(x) ** 2 for x in left) * sum(float(x) ** 2 for x in right))
    if denominator == 0:
        return -1.0
    return sum(float(x) * float(y) for x, y in zip(left, right)) / denominator


def search_diary_entries(query: str, user_id: int, limit: int = 5, date_range=None) -> list[Document]:
    """Filter candidates using explicit cosine similarity, independent of index metric.

    RAG_MIN_COSINE_SIMILARITY defaults to 0.30; tune against evaluation questions.
    Old index metadata remains supported; no reindex is needed for date filtering.
    """
    import math
    import os
    import re
    from collections import Counter

    if not query.strip() or limit <= 0:
        return []
    threshold = float(os.getenv('RAG_MIN_COSINE_SIMILARITY', '0.30'))
    if not math.isfinite(threshold) or not -1 <= threshold <= 1:
        raise ValueError('RAG_MIN_COSINE_SIMILARITY must be between -1 and 1')
    # Authorize entry IDs in PostgreSQL before Chroma sees the query.
    # This also excludes orphaned vectors and supports the existing index.
    from app.database import SessionLocal
    from app.models import DiaryEntry
    with SessionLocal() as db:
        allowed_query = db.query(DiaryEntry.id).filter(DiaryEntry.user_id == user_id)
        if date_range:
            allowed_query = allowed_query.filter(DiaryEntry.entry_date >= date_range[0], DiaryEntry.entry_date <= date_range[1])
        allowed = [row[0] for row in allowed_query.all()]
    if not allowed:
        return []
    store = get_vector_store()
    count = store._collection.count()
    if not count:
        return []
    where = {'entry_id': {'$in': allowed}}
    embedding = get_embedding_model().embed_query(query)
    raw = store._collection.query(
        query_embeddings=[embedding], n_results=min(count, max(30, limit * 6)),
        where=where, include=['documents', 'metadatas', 'embeddings'],
    )
    if raw.get('embeddings') is None:
        return []
    candidates = []
    for text, metadata, vector in zip(raw['documents'][0], raw['metadatas'][0], raw['embeddings'][0]):
        if not text or not metadata or not isinstance(metadata.get('entry_id'), int):
            continue
        if not metadata.get('entry_date'):
            continue
        score = cosine_similarity(embedding, vector)
        if score >= threshold:
            candidates.append((score, text, metadata))
    candidates.sort(key=lambda item: item[0], reverse=True)
    results, seen, per_entry = [], [], Counter()
    for score, text, metadata in candidates:
        entry_id = metadata['entry_id']
        words = re.findall(r'\w+', text.casefold())
        shingles = {tuple(words[i:i + 3]) for i in range(max(1, len(words) - 2))}
        duplicate = any(entry_id == previous_id and len(shingles & previous) / max(1, len(shingles | previous)) >= 0.65
                        for previous_id, previous in seen)
        if duplicate or per_entry[entry_id] >= 2:
            continue
        results.append(Document(page_content=text, metadata={**metadata, 'similarity': round(score, 4)}))
        seen.append((entry_id, shingles))
        per_entry[entry_id] += 1
        if len(results) >= limit:
            break
    return results

def sync_diary_entry(
    entry_id: int,
    title: str,
    content: str,
    entry_date: str,
) -> None:
    """
    Add or update a diary entry in ChromaDB.

    Removes old chunks before storing the latest version.
    """

    vector_store = get_vector_store()

    # Find existing chunks for this diary entry.
    existing = vector_store.get(
        where={"entry_id": entry_id}
    )

    # Remove old chunks to avoid duplicates.
    if existing["ids"]:
        vector_store.delete(ids=existing["ids"])

    # Prepare new document chunks.
    documents = prepare_diary_documents(
        entry_id=entry_id,
        title=title,
        content=content,
        entry_date=entry_date,
    )

    if not documents:
        return

    # Generate stable IDs for the chunks.
    document_ids = [
        f"diary_{entry_id}_chunk_{index}"
        for index in range(len(documents))
    ]

    # Generate embeddings and save to ChromaDB.
    vector_store.add_documents(
        documents=documents,
        ids=document_ids,
    )

    print(f"ChromaDB synced diary entry: {entry_id}")


def delete_diary_embeddings(entry_id: int) -> None:
    """
    Remove all vector chunks belonging to a diary entry.
    """

    vector_store = get_vector_store()

    existing = vector_store.get(
        where={"entry_id": entry_id}
    )

    if existing["ids"]:
        vector_store.delete(ids=existing["ids"])

    print(f"ChromaDB removed diary entry: {entry_id}")

