# Testing, reliability, and privacy

## Repeatable checks

From backend with its virtual environment active:

```powershell
python run_tests.py
python -m pip check
```

The runner gives each suite its own interpreter so external-service mocks cannot leak between suites. Tests use synthetic SQLite databases, an isolated in-memory Chroma collection, and mocked AI responses. They do not inspect personal diaries or call the paid AI provider.

From frontend:

```powershell
npm.cmd test
npm.cmd run lint
npm.cmd run build
```

The frontend suite covers private-view gating, sign-in/sign-out, expired sessions, saved-chat switching, citations, combined search/filter behavior, missing mood scores, invalid dates, connection failures, and mutation timeout messages.

## Configuration and schema

Database credentials belong in backend/.env or process environment variables, using DATABASE_URL. The existing local URL has been preserved in the ignored .env file. See .env.example for placeholders. AI provider URL and model are unchanged. CORS_ORIGINS is the shared comma-separated list of explicit frontend origins used by CORS and mutation origin checks. Set SESSION_COOKIE_SECURE=true behind HTTPS.

Run migrations before starting the backend:

```powershell
python -m app.migrations
```

The schema_migrations table records applied versions. Migrations are forward-only and additive, use a PostgreSQL transaction/advisory lock, and are safe to rerun. Version 001 accounts for the prior account/ownership schema; version 002 adds the vector outbox. Existing data and account assignments are retained. For future changes, add a new migration rather than editing an already-applied one. Back up the database before future deployments; automatic destructive downgrades are intentionally unavailable.

## PostgreSQL and Chroma synchronization

Every diary creation, update and deletion adds a vector_sync_jobs record in the same SQL transaction. The request attempts processing immediately, and a background worker retries every 15 seconds with capped exponential backoff. A successful operation removes its job. Failures retain the job with only an exception type, not diary content or credentials. PostgreSQL workers lock jobs and use a per-entry advisory lock to avoid competing writes for one diary entry.

Workers read the current PostgreSQL row when executing. Old jobs cannot restore deleted content. Retry operations are idempotent: current chunks are replaced or removed. This is eventual consistency, not a distributed transaction. A saved entry may briefly be absent from semantic search while Chroma is unavailable. RAG authorization checks PostgreSQL ownership first, so deleted and foreign-account entries cannot be retrieved while cleanup is pending.

To retry manually:

```powershell
python -m app.retry_vector_sync
```

To repair the full index, including vectors with IDs no longer in PostgreSQL:

```powershell
python -m app.index_diaries
```

The repair command queues work and logs counts only. It does not print diary titles or contents. It was tested with synthetic data; a full repair has not been run against the user's diary. Use it only when needed. Neither maintenance command is an HTTP endpoint.

## Input and error behavior

Titles are limited to 255 characters, diary content to 20,000, and questions to 4,000. Blank titles/content and extra request fields are rejected. Request bodies are capped at 256 KiB, including streamed bodies. Mood output is validated for permitted labels, integer scores from 1 to 10, short emotions and a nonempty summary before storage. A mood-provider failure still saves the diary and displays a warning; saving an unanalyzed entry again retries analysis.

Validation responses omit raw input values. Database failures return a generic 503. Provider and vector errors are logged by type without response payloads. The SQL engine hides parameter values. API responses disable caching and add nosniff/no-referrer headers. Frontend requests have bounded waits, send the HttpOnly cookie, and never automatically retry a mutation after a timeout.

## Data sent to AI Credits

- Mood analysis: the submitted diary text.
- Summaries and insights: entries from the selected calendar period.
- Chat: the question, recent conversation context, and authorized retrieved diary passages with source IDs/dates/titles.

Passwords, password hashes and session tokens are never part of AI prompts. Embeddings run locally on CPU. The current AI provider still receives sensitive diary data for the features above; this step does not add a local-LLM mode or change the provider's retention policy.

## Scope of verification

Automated checks cover account isolation, source/date handling, invalid model output, input limits, safe errors, additive migrations, durable sync failures, retries and deletion handling. Frontend package installation reported zero known npm audit vulnerabilities; backend dependency consistency passed pip check. These checks do not establish that dependencies have no vulnerabilities or replace a production penetration test. Live browser and paid-provider behavior should be checked after restart. Remaining deployment work includes HTTPS/proxy configuration, a durable shared rate limiter for multiple application processes, backup/restore procedures, Docker, and deployment documentation in Step 70.
