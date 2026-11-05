"""Start the server on a throwaway database and run the browser-level API test against it."""
import os
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

try:  # never run against a server that is using a real database
    urllib.request.urlopen('http://127.0.0.1:3000/', timeout=1)
    sys.exit('Cổng 3000 đang bận; hãy tắt máy chủ đang chạy trước khi chạy test.')
except OSError:
    pass

with tempfile.TemporaryDirectory() as folder:
    db = Path(folder) / 'test.db'
    env = {**os.environ, 'LT_DB_FILE': str(db), 'PYTHON': sys.executable}
    server = subprocess.Popen([sys.executable, '-X', 'utf8', '-m', 'server.app'], cwd=ROOT, env=env)
    try:
        for _ in range(100):
            try:
                urllib.request.urlopen('http://127.0.0.1:3000/', timeout=1)
                break
            except OSError:
                time.sleep(0.1)
        with sqlite3.connect(db) as conn:
            conn.execute('INSERT INTO legacy_state(id, data) VALUES (1, ?)', ('{"term":"legacy","closed":[1]}',))
        code = subprocess.run(['node', 'tests/auth-integration.test.mjs'], cwd=ROOT, env=env).returncode
    finally:
        server.terminate()
        server.wait()
sys.exit(code)
