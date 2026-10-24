"""Cookie sessions and account registration for local LifeLog accounts."""
import hashlib
import hmac
import os
import re
import secrets
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.config import CORS_ORIGINS
from app.models import User, UserSession, DiaryEntry, ChatConversation

router = APIRouter(prefix="/api/auth", tags=["Accounts"])
COOKIE = "lifelog_session"
SESSION_SECONDS = 7 * 24 * 60 * 60
ALLOWED_ORIGINS = set(CORS_ORIGINS)
_attempts = defaultdict(deque)
_attempt_lock = threading.Lock()

def get_auth_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def check_origin(request: Request):
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        origin = request.headers.get('origin')
        if origin and origin not in ALLOWED_ORIGINS:
            raise HTTPException(status_code=403, detail="Request origin is not allowed.")
        if request.headers.get('sec-fetch-site') == 'cross-site':
            raise HTTPException(status_code=403, detail="Cross-site requests are not allowed.")

def password_hash(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()
    return f'scrypt${salt}${digest}'

def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, salt, expected = stored.split('$')
        if algorithm != 'scrypt':
            return False
        actual = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False

DUMMY_HASH = password_hash('not-a-real-account-password')

class Credentials(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=3, max_length=80, pattern=r'^[A-Za-z0-9_.-]+$')
    password: str = Field(min_length=10, max_length=128)

def public_user(user):
    return {"id": user.id, "username": user.username}

def throttle(request: Request):
    key = request.client.host if request.client else 'unknown'
    now = time.monotonic()
    with _attempt_lock:
        # Bound retained keys as well as attempts; this is a local single-process guard.
        for host in list(_attempts):
            if not _attempts[host] or _attempts[host][-1] < now - 600:
                del _attempts[host]
        attempts = _attempts[key]
        while attempts and attempts[0] < now - 600:
            attempts.popleft()
        if len(attempts) >= 20:
            raise HTTPException(status_code=429, detail="Too many attempts. Try again in 10 minutes.")
        attempts.append(now)

def set_session(user, request, response, db):
    old_token = request.cookies.get(COOKIE)
    if old_token:
        db.query(UserSession).filter(UserSession.token_hash == hashlib.sha256(old_token.encode()).hexdigest()).delete()
    token = secrets.token_urlsafe(32)
    db.add(UserSession(token_hash=hashlib.sha256(token.encode()).hexdigest(), user_id=user.id,
                       expires_at=datetime.now(timezone.utc) + timedelta(seconds=SESSION_SECONDS)))
    db.query(UserSession).filter(UserSession.expires_at <= datetime.now(timezone.utc)).delete()
    secure = os.getenv('SESSION_COOKIE_SECURE', '').lower() == 'true' or request.url.scheme == 'https'
    response.set_cookie(COOKIE, token, httponly=True, secure=secure, samesite='strict',
                        max_age=SESSION_SECONDS, path='/')
    response.headers['Cache-Control'] = 'no-store'

@router.post('/register', status_code=201)
def register(credentials: Credentials, request: Request, response: Response, db: Session = Depends(get_auth_db)):
    check_origin(request)
    throttle(request)
    # Serialize first-account claims across PostgreSQL processes.
    if db.get_bind().dialect.name == 'postgresql':
        db.execute(text('SELECT pg_advisory_xact_lock(68001)'))
    first_account = db.query(User.id).first() is None
    user = User(username=credentials.username.lower(), password_hash=password_hash(credentials.password))
    try:
        db.add(user)
        db.flush()
        if first_account:
            db.query(DiaryEntry).filter(DiaryEntry.user_id.is_(None)).update({DiaryEntry.user_id: user.id})
            db.query(ChatConversation).filter(ChatConversation.user_id.is_(None)).update({ChatConversation.user_id: user.id})
        set_session(user, request, response, db)
        result = public_user(user)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="That username is unavailable.") from None
    return {"user": result}

@router.post('/login')
def login(credentials: Credentials, request: Request, response: Response, db: Session = Depends(get_auth_db)):
    check_origin(request)
    throttle(request)
    user = db.query(User).filter(User.username == credentials.username.lower()).first()
    valid = verify_password(credentials.password, user.password_hash if user else DUMMY_HASH)
    if not user or not valid:
        raise HTTPException(status_code=401, detail="Invalid username or password.")
    set_session(user, request, response, db)
    result = public_user(user)
    db.commit()
    return {"user": result}

def get_current_user(request: Request, db: Session = Depends(get_auth_db)) -> User:
    check_origin(request)
    token = request.cookies.get(COOKIE)
    if not token:
        raise HTTPException(status_code=401, detail="Please sign in.")
    session = db.get(UserSession, hashlib.sha256(token.encode()).hexdigest())
    if not session:
        raise HTTPException(status_code=401, detail="Please sign in again.")
    expiry = session.expires_at
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    if expiry <= datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Your session has expired. Please sign in again.")
    user = db.get(User, session.user_id)
    if not user:
        raise HTTPException(status_code=401, detail="Please sign in again.")
    return user

@router.get('/me')
def me(response: Response, user: User = Depends(get_current_user)):
    response.headers['Cache-Control'] = 'no-store'
    return {"user": public_user(user)}

@router.post('/logout')
def logout(request: Request, response: Response, db: Session = Depends(get_auth_db)):
    check_origin(request)
    token = request.cookies.get(COOKIE)
    if token:
        db.query(UserSession).filter(UserSession.token_hash == hashlib.sha256(token.encode()).hexdigest()).delete()
        db.commit()
    response.delete_cookie(COOKIE, path='/')
    response.headers['Cache-Control'] = 'no-store'
    return {"message": "Signed out."}
