"""Environment configuration; never store credentials in source code."""
import os
from pathlib import Path
from urllib.parse import urlsplit
from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND_DIR / '.env')
DATABASE_URL = os.getenv('DATABASE_URL', '')
CORS_ORIGINS = [origin.strip().rstrip('/') for origin in os.getenv(
    'CORS_ORIGINS', 'http://localhost:5173,http://127.0.0.1:5173').split(',') if origin.strip()]
for origin in CORS_ORIGINS:
    parsed = urlsplit(origin)
    if parsed.scheme not in {'http', 'https'} or not parsed.netloc or parsed.path or parsed.query or parsed.fragment or parsed.username:
        raise ValueError('CORS_ORIGINS must contain explicit HTTP(S) origins, without paths or credentials.')
MAX_REQUEST_BYTES = 262144
