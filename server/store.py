"""SQLite storage for accounts, sessions and each account's timetable state."""
import hashlib
import hmac
import os
import secrets
import sqlite3
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SESSION_SECONDS = 30 * 24 * 3600
SCHEMA = '''
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    salt TEXT NOT NULL,
    passhash TEXT NOT NULL,
    sessionhash TEXT,
    expires INTEGER
);
CREATE INDEX IF NOT EXISTS users_session ON users(sessionhash);
CREATE TABLE IF NOT EXISTS user_state (
    user_id INTEGER PRIMARY KEY REFERENCES users(id),
    data TEXT NOT NULL
);
-- The single shared timetable from before accounts existed; the first account inherits it.
CREATE TABLE IF NOT EXISTS legacy_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    data TEXT NOT NULL
);
'''

# ponytail: one connection behind one lock; queries take microseconds, so this only matters past many concurrent users.
_lock = threading.Lock()
_db = None


def path():
    return Path(os.environ.get('LT_DB_FILE') or ROOT / 'data' / 'lich-truong.db')


def connect(file=None):
    """Open (and create if needed) the database; returns the connection for scripts that need it."""
    global _db
    with _lock:
        if _db is None:
            file = Path(file or path())
            file.parent.mkdir(parents=True, exist_ok=True)
            _db = sqlite3.connect(file, check_same_thread=False, isolation_level=None)
            _db.execute('PRAGMA journal_mode=WAL')
            _db.execute('PRAGMA foreign_keys=ON')
            _db.executescript(SCHEMA)
        return _db


def _run(sql, args=()):
    db = connect()
    with _lock:
        return db.execute(sql, args).fetchall()


def digest(token):
    return hashlib.sha256(token.encode('ascii')).hexdigest()


def hash_password(password, salt):
    # Same parameters as the former Java PBKDF2WithHmacSHA256 hashes, so imported accounts keep working.
    return hashlib.pbkdf2_hmac('sha256', password.encode('utf-8', 'surrogatepass'), bytes.fromhex(salt), 210000, 32).hex()


def lookup(token):
    """Return (id, username) for a live session token, else None."""
    if not token:
        return None
    found = _run('SELECT id, username FROM users WHERE sessionhash = ? AND expires > ?', (digest(token), int(time.time())))
    return found[0] if found else None


def load_state(token):
    """Return (id, username, data) for a live session; data is None when nothing is saved yet."""
    if not token:
        return None
    found = _run('SELECT u.id, u.username, s.data FROM users u LEFT JOIN user_state s ON s.user_id = u.id '
                 'WHERE u.sessionhash = ? AND u.expires > ?', (digest(token), int(time.time())))
    return found[0] if found else None


def save_state(token, data):
    """Store data for the session's account; False when the session is no longer valid."""
    db = connect()
    with _lock:
        user = db.execute('SELECT id FROM users WHERE sessionhash = ? AND expires > ?',
                          (digest(token), int(time.time()))).fetchone()
        if user is None:
            return False
        db.execute('INSERT INTO user_state(user_id, data) VALUES (?, ?) '
                   'ON CONFLICT(user_id) DO UPDATE SET data = excluded.data', (user[0], data))
        return True


def register(username, password, token):
    """Create an account signed in with token; None when the name is taken."""
    salt = secrets.token_hex(16)
    passhash = hash_password(password, salt)
    db = connect()
    with _lock:
        try:
            db.execute('BEGIN IMMEDIATE')
            first = db.execute('SELECT NOT EXISTS (SELECT 1 FROM users)').fetchone()[0]
            if db.execute('SELECT 1 FROM users WHERE username = ?', (username,)).fetchone():
                db.execute('ROLLBACK')
                return None
            uid = db.execute('INSERT INTO users(username, salt, passhash, sessionhash, expires) VALUES (?, ?, ?, ?, ?)',
                             (username, salt, passhash, digest(token), int(time.time()) + SESSION_SECONDS)).lastrowid
            if first:
                db.execute('INSERT INTO user_state(user_id, data) SELECT ?, data FROM legacy_state WHERE id = 1', (uid,))
            db.execute('COMMIT')
            return uid
        except BaseException:
            if db.in_transaction:
                db.execute('ROLLBACK')
            raise


def login(username, password, token):
    """Start a new session (ending any other) and return the account id; None for wrong credentials."""
    found = _run('SELECT id, salt, passhash FROM users WHERE username = ?', (username,))
    uid, salt, passhash = found[0] if found else (None, '0' * 32, 'invalid')
    # Hash even for unknown names so response time does not reveal which accounts exist.
    if not hmac.compare_digest(hash_password(password, salt), passhash) or uid is None:
        return None
    _run('UPDATE users SET sessionhash = ?, expires = ? WHERE id = ?',
         (digest(token), int(time.time()) + SESSION_SECONDS, uid))
    return uid


def logout(token):
    if token:
        _run('UPDATE users SET sessionhash = NULL, expires = NULL WHERE sessionhash = ?', (digest(token),))
