"""Local web server: static frontend, accounts, timetable storage, Excel import/export and the solver."""
import collections
import secrets
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

from . import solver, store, validator, xlsx
from .state import check_teacher_names, clean, dump, parse, text

PUBLIC = Path(__file__).resolve().parents[1] / 'public'
HOSTS = ('localhost:3000', '127.0.0.1:3000')
ORIGINS = (None, 'http://localhost:3000', 'http://127.0.0.1:3000')
EXPIRED = 'Phiên đăng nhập đã hết hiệu lực. Vui lòng đăng nhập lại.'
COOKIE = 'lt_session'
TYPES = {'.css': 'text/css', '.js': 'text/javascript'}


class Reply(Exception):
    """Stop handling a request and answer with this status and JSON body."""

    def __init__(self, status, body):
        super().__init__(status)
        self.status, self.body = status, body


def error(status, message):
    return Reply(status, {'error': message})


_attempts = collections.defaultdict(collections.deque)
_attempts_lock = threading.Lock()


def allowed(address):
    """At most 10 sign-in or registration attempts per minute from one address."""
    now = time.monotonic()
    with _attempts_lock:
        queue = _attempts[address]
        while queue and queue[0] < now - 60:
            queue.popleft()
        if len(queue) >= 10:
            return False
        queue.append(now)
        return True


_static = {}


def static_file(file):
    """Return (bytes, etag) for a file, re-reading it only when it changes on disk."""
    stat = file.stat()
    tag = f'"{stat.st_mtime_ns:x}-{stat.st_size:x}"'
    cached = _static.get(file)
    if cached is None or cached[1] != tag:
        cached = _static[file] = (file.read_bytes(), tag)
    return cached


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    server_version = 'LichTruong'
    sys_version = ''

    def log_message(self, *args):
        pass

    # ---- plumbing -------------------------------------------------------

    def send(self, status, body, content_type='application/json', headers=()):
        if not isinstance(body, bytes):
            body = (body if isinstance(body, str) else dump(body)).encode('utf-8')
        self.send_response(status)
        if self.unread:
            # The unread body would be parsed as the next request on this connection.
            self.send_header('Connection', 'close')
        self.send_header('Content-Type', content_type if content_type.startswith('application/vnd') else content_type + '; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        for name, value in (*self.extra_headers, *headers):
            self.send_header(name, value)
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(body)

    def body(self, limit, message):
        length = self.unread
        if not 0 <= length <= limit:
            if 0 < length <= 64_000_000:
                # Drain the upload so the browser reads our answer instead of seeing a reset connection.
                while length > 0 and (chunk := self.rfile.read(min(length, 1 << 20))):
                    length -= len(chunk)
                self.unread = length
            raise ValueError(message)
        self.unread = 0
        return self.rfile.read(length)

    def json_body(self, limit, message):
        return parse(self.body(limit, message).decode('utf-8', 'replace'))

    def token(self):
        for part in (self.headers.get('Cookie') or '').split(';'):
            name, _, value = part.strip().partition('=')
            if name == COOKIE and len(value) == 64 and all(c in '0123456789abcdef' for c in value):
                return value
        return ''

    def origin_ok(self):
        host = self.headers.get('Host') or ''
        return (host.lower() == HOSTS[0] or host == HOSTS[1]) and self.headers.get('Origin') in ORIGINS

    def authorize(self):
        """Require a live session whose account matches the X-LT-User header."""
        if not self.origin_ok():
            raise error(403, 'Yêu cầu không hợp lệ.')
        user = store.lookup(self.token())
        if user is None or self.headers.get('X-LT-User') != str(user[0]):
            raise error(401, EXPIRED)
        return user

    def route(self, unexpected, handler, *args):
        """Run handler; ValueError is the client's fault (400), anything else is ours."""
        try:
            handler(*args)
        except Reply as reply:
            self.send(reply.status, reply.body)
        except ValueError as exc:
            self.send(400, {'error': str(exc) or 'Dữ liệu không hợp lệ.'})
        except (BrokenPipeError, ConnectionResetError):
            self.close_connection = True
        except Exception as exc:  # noqa: BLE001 - last resort so the client always gets an answer
            print(f'{self.command} {self.path}: {exc!r}', file=sys.stderr)
            self.send(*unexpected)

    # ---- dispatch -------------------------------------------------------

    def start(self):
        try:
            self.unread = int(self.headers.get('Content-Length') or 0)
        except ValueError:
            self.unread = -1
        self.extra_headers = []

    def dispatch(self):
        self.start()
        path = unquote(urlsplit(self.path).path)
        method = self.command
        if path.startswith('/api/auth'):
            self.extra_headers = [('Cache-Control', 'no-store')]
            return self.route((503, {'error': 'Không thể xử lý yêu cầu. Hãy kiểm tra cơ sở dữ liệu.'}), self.auth, path)
        api = {
            '/api/state': (self.state, ('GET', 'PUT'), (503, {'error': 'Không truy cập được cơ sở dữ liệu.'})),
            '/api/import-xlsx': (self.import_xlsx, ('POST',), (400, {'error': 'Không đọc được file Excel.'})),
            '/api/export-school-xlsx': (self.export_xlsx, ('POST',), (500, {'error': 'Không thể tạo file Excel. Hãy thử lại.'})),
            '/api/generate-stream': (self.generate, ('POST',), (503, {'error': 'Không xác thực được phiên đăng nhập.'})),
        }
        if path in api:
            handler, methods, unexpected = api[path]

            def guarded():
                user = self.authorize()
                if method not in methods:
                    raise Reply(405, {})
                handler(user)
            return self.route(unexpected, guarded)
        self.route((500, 'Server error', 'text/plain'), self.static, path)

    do_GET = do_POST = do_PUT = do_DELETE = do_PATCH = dispatch

    def do_HEAD(self):
        self.start()
        self.route((500, 'Server error', 'text/plain'), self.static, unquote(urlsplit(self.path).path))

    # ---- routes ---------------------------------------------------------

    def static(self, path):
        file = (PUBLIC / ('index.html' if path == '/' else path.lstrip('/'))).resolve()
        if not file.is_relative_to(PUBLIC) or not file.is_file():
            return self.send(404, 'Not found', 'text/plain')
        data, tag = static_file(file)
        headers = [('ETag', tag), ('Cache-Control', 'no-cache')]
        if self.headers.get('If-None-Match') == tag:
            self.send_response(304)
            if self.unread:
                self.send_header('Connection', 'close')
            for header in headers:
                self.send_header(*header)
            self.send_header('Content-Length', '0')
            return self.end_headers()
        self.send(200, data, TYPES.get(file.suffix, 'text/html'), headers)

    def state(self, user):
        token = self.token()
        if self.command == 'GET':
            found = store.load_state(token)
            if found is None:
                raise error(401, 'Phiên đăng nhập đã hết hiệu lực.')
            return self.send(200, 'null' if found[2] is None else dump(clean(found[2])))
        data = clean(self.body(2_000_000, 'Dữ liệu quá lớn.').decode('utf-8', 'replace'))
        check_teacher_names(data)
        if not store.save_state(token, dump(data)):
            raise error(401, 'Phiên đăng nhập đã hết hiệu lực.')
        self.send(200, {'ok': True})

    def import_xlsx(self, user):
        self.send(200, xlsx.read(self.body(5_000_000, 'File vượt quá 5 MB.')))

    def export_xlsx(self, user):
        state = self.json_body(2_000_000, 'Dữ liệu quá lớn để xuất Excel.')
        if not isinstance(state, dict):
            raise ValueError('Dữ liệu xuất không hợp lệ.')
        self.send(200, xlsx.school_workbook(state), 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                  [('Content-Disposition', 'attachment; filename="thoi-khoa-bieu-toan-truong.xlsx"'),
                   ('Cache-Control', 'no-store')])

    def generate(self, user):
        state = self.json_body(2_000_000, 'Dữ liệu quá lớn.')
        if not isinstance(state, dict):
            raise ValueError('Dữ liệu không hợp lệ.')
        cancel, outcome = threading.Event(), {}

        def work():
            try:
                result = solver.run(state, cancel)
                if result.get('ok') is True:
                    validator.check_result(state, result)
                outcome['event'] = {'type': 'result', 'result': result}
            except Exception as exc:  # noqa: BLE001 - reported to the client as a failed run
                outcome['event'] = {'type': 'error', 'error': str(exc) or 'Dữ liệu không hợp lệ.'}

        self.send_response(200)
        self.send_header('Content-Type', 'application/x-ndjson; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Connection', 'close')
        self.end_headers()
        self.close_connection = True
        worker = threading.Thread(target=work, daemon=True)
        start = time.monotonic()
        try:
            self.event({'type': 'progress', 'phase': 'search', 'elapsed': 0})
            worker.start()
            while worker.join(1) is None and worker.is_alive():
                self.event({'type': 'progress', 'phase': 'search', 'elapsed': int(time.monotonic() - start)})
            self.event(outcome['event'])
        except (BrokenPipeError, ConnectionResetError):
            cancel.set()  # the user pressed stop or closed the page

    def event(self, value):
        self.wfile.write((dump(value) + '\n').encode('utf-8'))
        self.wfile.flush()

    def auth(self, path):
        if not self.origin_ok():
            raise error(403, 'Yêu cầu không hợp lệ.')
        method = self.command
        if path == '/api/auth/bootstrap' and method == 'GET':
            found = store.load_state(self.token())
            if found is None:
                raise Reply(401, {'error': 'Chưa đăng nhập.'})
            uid, username, data = found
            return self.send(200, {'id': uid, 'username': username, 'state': None if data is None else clean(data)})
        if path == '/api/auth/me' and method == 'GET':
            user = store.lookup(self.token())
            if user is None:
                raise Reply(401, {'error': 'Chưa đăng nhập.'})
            return self.send(200, {'id': user[0], 'username': user[1]})
        if path == '/api/auth/logout' and method == 'POST':
            store.logout(self.token())
            return self.send(200, {'ok': True}, headers=[('Set-Cookie', self.cookie(''))])
        if method != 'POST' or path not in ('/api/auth/register', '/api/auth/login'):
            raise Reply(404, {})
        if not allowed(self.client_address[0]):
            raise Reply(429, {'error': 'Bạn thao tác quá nhiều lần. Hãy thử lại sau một phút.'})
        form = self.json_body(8192, 'Dữ liệu quá lớn.')
        if not isinstance(form, dict):
            raise ValueError('Dữ liệu không hợp lệ.')
        username = text(form, 'username').lower()
        password = form.get('password')
        password = '' if password is None else str(password)
        if not (3 <= len(username) <= 40 and all(c in 'abcdefghijklmnopqrstuvwxyz0123456789._-' for c in username)):
            raise ValueError('Tên đăng nhập cần 3–40 ký tự, chỉ gồm chữ không dấu, số, dấu chấm, gạch dưới hoặc gạch ngang.')
        # Length in UTF-16 units, as the browser counts it.
        if not 10 <= len(password.encode('utf-16-le', 'surrogatepass')) // 2 <= 128:
            raise ValueError('Mật khẩu cần từ 10 đến 128 ký tự.')
        token = secrets.token_hex(32)
        if path == '/api/auth/register':
            uid = store.register(username, password, token)
            if uid is None:
                raise Reply(409, {'error': 'Tên đăng nhập đã được sử dụng.'})
        else:
            uid = store.login(username, password, token)
            if uid is None:
                raise Reply(401, {'error': 'Tên đăng nhập hoặc mật khẩu chưa đúng.'})
        self.send(200, {'id': uid, 'username': username}, headers=[('Set-Cookie', self.cookie(token))])

    @staticmethod
    def cookie(token):
        return f'{COOKIE}={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age={2592000 if token else 0}'


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address):
        if not isinstance(sys.exc_info()[1], ConnectionError):  # browsers drop idle connections all the time
            super().handle_error(request, client_address)


def main():
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding='utf-8')
    store.connect()
    server = Server(('127.0.0.1', 3000), Handler)
    print('Lịch Trường đang chạy tại http://localhost:3000', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
