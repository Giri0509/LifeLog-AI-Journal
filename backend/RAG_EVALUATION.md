# RAG accuracy evaluation

Run from backend with the existing virtual environment:

```powershell
.\venv\Scripts\python.exe tests\test_rag_accuracy.py
.\venv\Scripts\python.exe tests\test_chat_history.py
```

The retrieval evaluation uses an isolated, in-memory Chroma collection and deterministic synthetic embeddings. It never indexes, reads, or changes personal diary entries, loads the real embedding model, or calls the AI provider.

Covered questions and expectations:

| Case | Expected behavior |
| --- | --- |
| Running question against synthetic running and cooking entries | Running entries 1 and 3; cooking entry 2 excluded |
| Running in September 2026 | Only entry 3 |
| Date containing only an unrelated entry | No evidence; no answer generation |
| Overlapping duplicate chunks | Identical chunks returned once; maximum two chunks per entry |
| Last month at a year boundary | Previous December |
| Follow-up about a previous user question | User context retained; generated assistant content excluded from retrieval query |
| Unknown cited entry ID | Answer rejected |
| Real entry ID with invented supporting quote | Answer rejected |
| Invalid or ambiguous date syntax | Ask for an explicit date/range |
| Unrelated new topic after dated conversation | Previous date scope is not imposed |

`RAG_MIN_COSINE_SIMILARITY` optionally controls the minimum cosine similarity (default `0.30`, valid range -1 through 1). Similarity is calculated directly from embeddings, so it does not depend on the existing Chroma collection distance metric. No reindexing is required. Candidate search is bounded and semantic, not an exhaustive query of the diary.

The default threshold is a starting point, not a calibrated accuracy guarantee. Evaluate real MiniLM embeddings separately using synthetic representative entries and known expected sources before tuning. These automated tests verify retrieval mechanics and answer validation; they do not measure live LLM quality.

Each generated observation must include a retrieved diary ID and an exact supporting excerpt. Only cited sources appear in the response. Hover a source chip to see its excerpt. Exact excerpt checks establish traceability, but cannot prove that every inference in a generated observation is semantically entailed. Review live answers against the cited passages. Persisted older answers retain their original source format and are not rewritten.

Supported date expressions include today/yesterday, this/last week/month/year, past/last N days, month plus year, and ISO dates/ranges. Relative calendar periods use Asia/Kolkata time; weeks start Monday. Days not recorded are never assumed to contain events. Other date expressions may require an explicit ISO range.

Diary writes now use a transactional vector-sync outbox with retries. PostgreSQL ownership checks exclude foreign-account entries and orphaned vectors before retrieval. The administrative index repair command can queue physical cleanup of orphaned vectors.
