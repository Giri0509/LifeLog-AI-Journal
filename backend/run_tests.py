"""Run each suite in a fresh interpreter to isolate dependency mocks."""
import subprocess
import sys
from pathlib import Path

backend = Path(__file__).resolve().parent
suites = ['test_auth.py', 'test_hardening.py', 'test_chat_history.py', 'test_diary_insights.py', 'test_rag_accuracy.py']
if __name__ == '__main__':
    for suite in suites:
        result = subprocess.run([sys.executable, str(backend/'tests'/suite)], cwd=backend, timeout=120)
        if result.returncode:
            raise SystemExit(result.returncode)
    print('All backend suites passed.')
