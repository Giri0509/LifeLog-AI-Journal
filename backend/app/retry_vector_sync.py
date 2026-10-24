"""Retry pending vector work once; the API also retries every 15 seconds."""
from app.services.vector_sync import run_pending
if __name__ == '__main__':
    print(f'Completed {run_pending(limit=1000)} pending vector jobs.')
