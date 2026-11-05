"""One-time copy of accounts and timetables from the old SQL Server database into SQLite.

Run on the Windows machine that used SQL Server, from the project folder, with the old .env in place:

    python scripts/migrate_sqlserver.py

Passwords keep working. Everyone signs in again afterwards because sessions are not copied.
"""
import base64
import os
import re
import sqlite3
import subprocess
from contextlib import closing
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from server import store  # noqa: E402

KEYS = ('DB_HOST', 'DB_PORT', 'DB_NAME', 'DB_USER', 'DB_PASSWORD')
ERRORS = {
    'LOGIN': 'SQL Server từ chối đăng nhập. Kiểm tra DB_USER và DB_PASSWORD.',
    'DATABASE': 'Không mở được database. Kiểm tra DB_NAME và quyền truy cập.',
    'PERMISSION': 'Tài khoản chưa có quyền đọc database.',
}
# Each query returns one text column; the PowerShell helper prints rows back to back.
BASE64 = "CAST(N'' AS XML).value('xs:base64Binary(sql:column(\"data\"))', 'varchar(max)')"
USERS_SQL = ("SET NOCOUNT ON; IF OBJECT_ID(N'dbo.LichTruongUsers', N'U') IS NOT NULL "
             "SELECT CONVERT(varchar(12), id) + '|' + username + '|' + salt + '|' + passhash + ';' "
             "FROM dbo.LichTruongUsers ORDER BY id;")
STATE_SQL = ("SET NOCOUNT ON; IF OBJECT_ID(N'dbo.LichTruongUserState', N'U') IS NOT NULL "
             f"SELECT {BASE64} FROM (SELECT CONVERT(varbinary(max), data) AS data FROM dbo.LichTruongUserState "
             "WHERE user_id = {id}) AS s;")
LEGACY_SQL = ("SET NOCOUNT ON; IF OBJECT_ID(N'dbo.LichTruongState', N'U') IS NOT NULL "
              f"SELECT {BASE64} FROM (SELECT CONVERT(varbinary(max), data) AS data FROM dbo.LichTruongState "
              "WHERE id = 1) AS s;")


def read_env(file):
    env = {}
    for line in Path(file).read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or line.find('=') < 1:
            continue
        key, value = (part.strip() for part in line.split('=', 1))
        if len(value) >= 2 and value[0] == value[-1] and value[0] in '"\'':
            value = value[1:-1]
        env[key] = value
    missing = [key for key in KEYS if not env.get(key)]
    if missing:
        raise SystemExit(f'Thiếu {", ".join(missing)} trong file .env.')
    return env


def query(env, sql):
    shell = 'powershell.exe' if os.name == 'nt' else 'pwsh'
    process = subprocess.run(
        [shell, '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File', str(ROOT / 'scripts' / 'sql-query.ps1')],
        input=sql.encode('utf-8'), capture_output=True, timeout=60,
        env={**os.environ, **{f'LT_{key}': env[key] for key in KEYS}})
    if process.returncode:
        code = process.stderr.decode('utf-8', 'replace').strip()
        raise SystemExit(ERRORS.get(code, f'Không truy vấn được SQL Server ({code or process.returncode}).'))
    return process.stdout.decode('utf-8').strip()


def parse_users(output):
    users = []
    for row in filter(None, output.split(';')):
        parts = row.split('|')
        uid, username, salt, passhash = parts if len(parts) == 4 else ('', '', '', '')
        if not (uid.isdigit() and re.fullmatch('[a-z0-9._-]{3,40}', username)
                and re.fullmatch('[0-9a-f]{32}', salt) and re.fullmatch('[0-9a-f]{64}', passhash)):
            raise SystemExit(f'Dòng tài khoản không hợp lệ: {row!r}')
        users.append((int(uid), username, salt, passhash))
    return users


def decode(output):
    """SQL Server nvarchar arrives as base64 of UTF-16LE; None when there was no row."""
    output = ''.join(output.split())
    return base64.b64decode(output, validate=True).decode('utf-16-le') if output else None


def write(target, users, states, legacy):
    temp = target.with_name(target.name + '.migrating')
    temp.unlink(missing_ok=True)
    with sqlite3.connect(temp) as db:
        db.executescript(store.SCHEMA)
        db.executemany('INSERT INTO users(id, username, salt, passhash) VALUES (?, ?, ?, ?)', users)
        db.executemany('INSERT INTO user_state(user_id, data) VALUES (?, ?)', states)
        if legacy is not None:
            db.execute('INSERT INTO legacy_state(id, data) VALUES (1, ?)', (legacy,))
    db.close()
    for leftover in ('-wal', '-shm'):  # from an empty database the server created; stop the server first
        target.with_name(target.name + leftover).unlink(missing_ok=True)
    temp.replace(target)


def has_users(target):
    if not target.exists():
        return False
    with closing(sqlite3.connect(target)) as db:
        return bool(db.execute("SELECT 1 FROM sqlite_master WHERE name = 'users'").fetchone()
                    and db.execute('SELECT 1 FROM users LIMIT 1').fetchone())


def main():
    target = store.path()
    if has_users(target):
        raise SystemExit(f'{target} đã có tài khoản; dừng lại để không ghi đè dữ liệu.')
    env = read_env(os.environ.get('LT_ENV_FILE', ROOT / '.env'))
    users = parse_users(query(env, USERS_SQL))
    states = []
    for uid, *_ in users:
        data = decode(query(env, STATE_SQL.replace('{id}', str(uid))))
        if data is not None:
            states.append((uid, data))
    legacy = decode(query(env, LEGACY_SQL))
    target.parent.mkdir(parents=True, exist_ok=True)
    write(target, users, states, legacy)
    print(f'Đã chuyển {len(users)} tài khoản, {len(states)} lịch'
          f'{" và lịch dùng chung cũ" if legacy is not None else ""} sang {target}.')


if __name__ == '__main__':
    main()
