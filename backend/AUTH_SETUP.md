# Account setup

Step 68 adds username/password accounts and private diary ownership.

## Existing installation

The schema migration has been applied locally. To apply it to another existing database, stop the backend, activate its virtual environment, then run from backend:

```powershell
python -m app.migrate_auth
```

The command adds users, server-side sessions, and nullable user_id ownership columns without removing existing diary entries or chats. It is safe to rerun. Existing schema creation for a new installation also includes the account models.

Restart the backend and frontend. Create your own first account in the browser. Registration atomically assigns existing unowned diary entries and conversations to that first account. Create this account yourself on the local installation before sharing access. Subsequent accounts start without diary entries or conversations.

## Session behavior

Passwords use salted scrypt hashes. The browser receives a random opaque token in an HttpOnly, SameSite=Strict cookie; only its SHA-256 digest is stored in PostgreSQL. Sessions expire after seven days. Login rotates the session for that browser; logout revokes it. Passwords and tokens are not stored in localStorage. API responses use Cache-Control: no-store.

All diary, summary, insight, chat and mood-analysis endpoints require authentication. Database queries check the signed-in user's ownership. RAG retrieval obtains allowed diary IDs from PostgreSQL before searching ChromaDB. Other accounts and orphaned vectors are excluded. Existing vectors do not need reindexing. Local administrative scripts remain local administration tools and are not HTTP endpoints.

The first account must be created through the browser so the owner chooses their own credentials. No default account or password is installed.

## Local development

Frontend: http://localhost:5173 or http://127.0.0.1:5173.
Backend: matching hostname, port 8000. The shared frontend API helper sends credentials and keeps the host consistent for cookies.

For HTTPS deployments set SESSION_COOKIE_SECURE=true. Cookies also automatically use Secure when the backend receives HTTPS requests directly. CORS_ORIGINS in backend/.env configures both CORS and mutation origin checks; the default is the two local development origins. The in-memory login attempt guard permits 20 attempts per IP per ten minutes per process; production rate limiting, password recovery and account administration remain future hardening work.

## Verification

Run these individually from backend with the existing virtual environment:

```powershell
python tests\test_auth.py
python tests\test_chat_history.py
python tests\test_diary_insights.py
python tests\test_rag_accuracy.py
```

Tests use synthetic data in SQLite and an isolated Chroma collection. HTTP tests cover anonymous requests, ownership, first-account data assignment, login/logout, cookie rotation, expired sessions, and cross-site mutation rejection. No real user account, password, or personal diary data is used.

Manual browser checks: register the first account, confirm old diaries/chats appear, sign out, register a second account and verify it starts empty, then sign back in as the first account. Verify that each account's chatbot only cites its own diary entries.
