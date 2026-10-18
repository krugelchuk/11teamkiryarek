"""Qadam11 Digital HR API. Python 3.10+, standard library only."""
import argparse
import hashlib
import json
import logging
import mimetypes
import os
from pathlib import Path
import re
import secrets
import sqlite3
import socket
import time
from contextlib import closing
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlsplit

from app.database import connect, initialize, password_matches, password_hash
from app import service as svc
from app import admin
from app import learning
from app import branches
from app import integrations
from app.assistant import status as assistant_status

VERSION = "0.1.0"
SESSION_TTL = 8 * 60 * 60
MAX_BODY = 64 * 1024
DEFAULT_ORIGINS = {f"http://{host}:{port}" for host in ("localhost", "127.0.0.1") for port in (3000, 4173, 5173, 8000)}
LOG = logging.getLogger("jana_hr")


def invalid_json_constant(value):
    raise ValueError("Non-finite JSON number")


class HRServer(ThreadingHTTPServer):
    daemon_threads = True
    # On Windows SO_REUSEADDR can let two apps listen on the same endpoint,
    # making requests land in an old copy. Always own the listening port.
    allow_reuse_address = os.name != 'nt'
    allow_reuse_port = False

    def server_bind(self):
        if os.name == 'nt':
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()

    def __init__(self, address, db_path, frontend_dir=None, origins=None, seed_demo=False):
        self.db_path = str(Path(db_path).resolve())
        initialize(self.db_path, seed_demo=seed_demo)
        self.frontend_dir = Path(frontend_dir).resolve() if frontend_dir else None
        self.allowed_origins = set(DEFAULT_ORIGINS if origins is None else origins)
        self.allowed_origins.update({f"http://localhost:{address[1]}", f"http://127.0.0.1:{address[1]}"})
        self.cookie_secure = os.getenv("COOKIE_SECURE", "0") == "1"
        super().__init__(address, Handler)
        self.allowed_origins.update({f"http://localhost:{self.server_port}", f"http://127.0.0.1:{self.server_port}"})


class Handler(BaseHTTPRequestHandler):
    server_version = "JanaHR/" + VERSION
    protocol_version = "HTTP/1.1"
    timeout = 15

    def log_message(self, fmt, *args):
        # Log methods and paths only, never request bodies/cookies/passwords.
        LOG.info("%s %s", getattr(self, 'command', '?'), urlsplit(getattr(self, 'path', '/')).path)

    def respond(self, status, payload, headers=None):
        content = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
        self.send_bytes(status, content, "application/json; charset=utf-8", headers)

    def send_bytes(self, status, content, content_type, headers=None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        self.send_header("X-Frame-Options", "DENY")
        origin = self.headers.get("Origin")
        if origin in self.server.allowed_origins:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Access-Control-Allow-Credentials", "true")
        self.send_header("Vary", "Origin")
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(content)

    def do_OPTIONS(self):
        if self.headers.get("Origin") not in self.server.allowed_origins:
            return self.respond(403, {"error": {"code": "origin_denied", "message": "Источник запроса не разрешён"}})
        self.send_bytes(204, b"", "text/plain", {
            "Access-Control-Allow-Methods": "GET, POST, PATCH, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, X-CSRF-Token",
            "Access-Control-Max-Age": "600",
        })

    def do_GET(self):
        self.handle_request()

    def do_POST(self):
        self.handle_request()

    def do_PATCH(self):
        self.handle_request()

    def do_PUT(self):
        self.respond(405, {"error": {"code": "method_not_allowed", "message": "Метод не поддерживается"}})

    do_DELETE = do_PUT

    def read_body(self):
        if self.headers.get("Transfer-Encoding"):
            self.close_connection = True
            svc.fail(400, "invalid_request", "Transfer-Encoding не поддерживается")
        length_header = self.headers.get("Content-Length", "0")
        if not re.fullmatch(r"\d{1,8}", length_header) or int(length_header) > MAX_BODY:
            self.close_connection = True
            svc.fail(413, "body_too_large", "Запрос слишком большой")
        if self.headers.get("Content-Type", "").split(";")[0].strip().lower() != "application/json":
            self.close_connection = True
            svc.fail(415, "unsupported_media_type", "Используйте Content-Type: application/json")
        try:
            length = int(length_header)
            if not length:
                svc.fail(400, "invalid_json", "Ожидается JSON-объект")
            data = json.loads(self.rfile.read(length).decode("utf-8"), parse_constant=invalid_json_constant)
        except (ValueError, UnicodeDecodeError, RecursionError):
            svc.fail(400, "invalid_json", "Некорректный JSON")
        if not isinstance(data, dict):
            svc.fail(400, "invalid_json", "Ожидается JSON-объект")
        return data

    def session(self, conn):
        jar = cookies.SimpleCookie()
        try:
            jar.load(self.headers.get("Cookie", ""))
        except cookies.CookieError:
            return None
        morsel = jar.get("jana_session")
        if not morsel or not re.fullmatch(r"[A-Za-z0-9_-]{40,100}", morsel.value):
            return None
        digest = hashlib.sha256(morsel.value.encode()).hexdigest()
        row = conn.execute("SELECT * FROM sessions WHERE token_hash=? AND expires_at>?", (digest, int(time.time()))).fetchone()
        return dict(row) if row else None

    def cookie(self, token, max_age=SESSION_TTL):
        secure = "; Secure" if self.server.cookie_secure else ""
        return f"jana_session={token}; Path=/; HttpOnly; SameSite=Lax; Max-Age={max_age}{secure}"

    def login(self, conn, data):
        svc.fields(data, {"email", "password"})
        email = svc.text(data.get("email"), "Email", 254, required=True).lower()
        password = data.get("password")
        if not isinstance(password, str) or not 1 <= len(password) <= 256:
            svc.fail(400, "validation_error", "Пароль: требуется от 1 до 256 символов")
        client = self.client_address[0] + ":" + email
        instant = time.time()
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("DELETE FROM login_attempts WHERE attempted_at<?", (instant - 60,))
        failures = conn.execute("SELECT COUNT(*) FROM login_attempts WHERE client=?", (client,)).fetchone()[0]
        if failures >= 10:
            conn.commit()
            svc.fail(429, "rate_limited", "Слишком много попыток. Повторите через минуту")
        user = conn.execute("SELECT id,password_hash FROM users WHERE email=?", (email,)).fetchone()
        valid = password_matches(password, user["password_hash"]) if user else bool(password_hash(password) and False)
        if not valid:
            conn.execute("INSERT INTO login_attempts VALUES(?,?)", (client, instant))
            conn.commit()
            svc.fail(401, "invalid_credentials", "Неверный email или пароль")
        old_session = self.session(conn)
        if old_session:
            conn.execute("DELETE FROM sessions WHERE token_hash=?", (old_session["token_hash"],))
        conn.execute("DELETE FROM login_attempts WHERE client=?", (client,))
        conn.execute("DELETE FROM sessions WHERE expires_at<=?", (int(instant),))
        token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        digest = hashlib.sha256(token.encode()).hexdigest()
        conn.execute("INSERT INTO sessions VALUES(?,?,?,?)", (digest, user["id"], csrf, int(instant) + SESSION_TTL))
        return {"user": svc.profile(conn, user["id"]), "csrf_token": csrf}, {"Set-Cookie": self.cookie(token)}

    def handle_request(self):
        conn = None
        try:
            parsed = urlsplit(self.path)
            path = parsed.path.rstrip("/") or "/"
            if self.command == "GET" and path == "/api/health":
                health = {"status": "ok", "service": "Qadam11 Digital HR", "version": VERSION, "assistant_mode": assistant_status()["mode"], "database": "ready"}
                try:
                    uri = Path(self.server.db_path).resolve().as_uri() + "?mode=ro"
                    with closing(sqlite3.connect(uri, uri=True, timeout=1)) as probe:
                        probe.execute("SELECT 1 FROM users LIMIT 1").fetchone()
                except sqlite3.Error:
                    health.update(status="unavailable", database="unavailable")
                    return self.respond(503, health)
                return self.respond(200, health)
            if self.command == "GET" and not path.startswith("/api/"):
                return self.serve_file(path)
            if self.command in ("POST", "PATCH"):
                origin = self.headers.get("Origin")
                if origin is not None and origin not in self.server.allowed_origins:
                    self.close_connection = True
                    svc.fail(403, "origin_denied", "Источник запроса не разрешён")
                body = self.read_body()
            else:
                body = {}
            conn = connect(self.server.db_path)
            if self.command == "GET" and path == "/api/setup/status":
                return self.respond(200, admin.setup_status(conn))
            if self.command == "POST" and path == "/api/setup":
                payload = admin.setup(conn, body)
                conn.commit()
                return self.respond(201, payload)
            if self.command == "POST" and path == "/api/auth/login":
                payload, headers = self.login(conn, body)
                conn.commit()
                return self.respond(200, payload, headers)
            session = self.session(conn)
            if not session:
                svc.fail(401, "unauthorized", "Войдите в аккаунт")
            user = svc.profile(conn, session["user_id"])
            if self.command in ("POST", "PATCH"):
                csrf = self.headers.get("X-CSRF-Token", "")
                if not csrf.isascii() or not secrets.compare_digest(csrf, session["csrf_token"]):
                    svc.fail(403, "csrf_failed", "Обновите страницу и повторите действие")
            status, payload, headers = self.route(conn, user, session, path, parse_qs(parsed.query), body)
            conn.commit()
            self.respond(status, payload, headers)
        except svc.APIError as exc:
            if conn:
                conn.rollback()
            self.respond(exc.status, {"error": {"code": exc.code, "message": exc.message}})
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            if conn:
                conn.rollback()
            self.close_connection = True
        except sqlite3.OperationalError:
            if conn:
                conn.rollback()
            LOG.exception("Database operation failed")
            self.respond(503, {"error": {"code": "database_unavailable", "message": "База временно занята. Повторите действие"}})
        except Exception:
            if conn:
                conn.rollback()
            LOG.exception("Unhandled request error")
            self.respond(500, {"error": {"code": "internal_error", "message": "Внутренняя ошибка сервера"}})
        finally:
            if conn:
                conn.close()

    def route(self, conn, user, session, path, query, data):
        method = self.command
        if method == "GET":
            if path == "/api/admin/integrations":
                return 200, integrations.listing(user), {}
            if path == "/api/branches":
                return 200, branches.listing(conn, user, query), {}
            if match := re.fullmatch(r"/api/branches/([1-9]\d{0,17})", path):
                return 200, branches.detail(conn, user, match[1], query), {}
            if match := re.fullmatch(r"/api/branches/([1-9]\d{0,17})/employees/([1-9]\d{0,17})", path):
                return 200, branches.employee(conn, user, match[1], int(match[2])), {}
            if path == "/api/auth/me":
                return 200, {"user": user, "csrf_token": session["csrf_token"]}, {}
            if path == "/api/assistant/status":
                return 200, assistant_status(), {}
            if path == "/api/admin/learning-pack":
                return 200, learning.summary(conn, user), {}
            if path == "/api/profile":
                return 200, user, {}
            if path == "/api/dashboard":
                return 200, svc.dashboard(conn, user), {}
            if path == "/api/team":
                return 200, svc.team(conn, user), {}
            if path == "/api/requests":
                return 200, svc.list_requests(conn, user, query.get("scope", ["mine"])[0]), {}
            if match := re.fullmatch(r"/api/requests/([1-9]\d{0,17})", path):
                return 200, svc.request_record(conn, user, int(match[1])), {}
            if path == "/api/notifications":
                return 200, svc.notifications(conn, user), {}
            if path == "/api/courses":
                return 200, svc.courses(conn, user), {}
            if match := re.fullmatch(r"/api/courses/([1-9]\d{0,17})", path):
                return 200, svc.course_details(conn, user, int(match[1])), {}
            if path == "/api/admin/courses":
                return 200, admin.course_catalog(conn, user), {}
            if match := re.fullmatch(r"/api/admin/courses/([1-9]\d{0,17})", path):
                return 200, admin.course_catalog(conn, user, int(match[1])), {}
            if path == "/api/admin/knowledge":
                return 200, admin.articles(conn, user), {}
            if path == "/api/knowledge":
                return 200, svc.knowledge(conn, user), {}
            if match := re.fullmatch(r"/api/knowledge/([1-9]\d{0,17})", path):
                return 200, svc.knowledge(conn, user, int(match[1])), {}
        if method == "POST":
            if match := re.fullmatch(r"/api/admin/integrations/([a-z0-9-]{1,40})/preview", path):
                return 200, integrations.preview(user, match[1], data), {}
            if path == "/api/auth/logout":
                svc.fields(data, set())
                conn.execute("DELETE FROM sessions WHERE token_hash=?", (session["token_hash"],))
                return 200, {"ok": True}, {"Set-Cookie": self.cookie("", 0)}
            if path == "/api/requests":
                return 201, svc.create_request(conn, user, data), {}
            if match := re.fullmatch(r"/api/requests/([1-9]\d{0,17})/decision", path):
                return 200, svc.decide_request(conn, user, int(match[1]), data), {}
            if match := re.fullmatch(r"/api/requests/([1-9]\d{0,17})/cancel", path):
                return 200, svc.cancel_request(conn, user, int(match[1]), data), {}
            if path == "/api/notifications/read-all":
                svc.fields(data, set())
                conn.execute("UPDATE notifications SET is_read=1 WHERE user_id=?", (user["id"],))
                return 200, {"ok": True}, {}
            if match := re.fullmatch(r"/api/courses/([1-9]\d{0,17})/lessons/([1-9]\d{0,17})/complete", path):
                svc.fields(data, set())
                return 200, svc.complete_lesson(conn, user, int(match[1]), int(match[2])), {}
            if match := re.fullmatch(r"/api/courses/([1-9]\d{0,17})/quiz", path):
                return 200, svc.quiz(conn, user, int(match[1]), data), {}
            if path == "/api/admin/assignments":
                return 201, svc.assign_course(conn, user, data), {}
            if path == "/api/admin/users":
                return 201, admin.create_user(conn, user, data), {}
            if path == "/api/admin/learning-pack/import":
                svc.fields(data,set())
                return 201, learning.import_pack(conn,user), {}
            if path == "/api/admin/knowledge":
                return 201, admin.save_article(conn, user, data), {}
            if path == "/api/admin/courses":
                return 201, admin.save_course(conn, user, data), {}
            if path == "/api/assistant/ask":
                return 200, svc.ask_assistant(conn, user, data), {}
        if method == "PATCH":
            if match := re.fullmatch(r"/api/admin/users/([1-9]\d{0,17})/branch", path):
                return 200, branches.assign(conn, user, int(match[1]), data), {}
            if match := re.fullmatch(r"/api/admin/branches/([1-9]\d{0,17})", path):
                return 200, branches.configure(conn, user, match[1], data), {}
            if match := re.fullmatch(r"/api/admin/knowledge/([1-9]\d{0,17})", path):
                return 200, admin.save_article(conn, user, data, int(match[1])), {}
            if match := re.fullmatch(r"/api/admin/courses/([1-9]\d{0,17})", path):
                return 200, admin.save_course(conn, user, data, int(match[1])), {}
            if match := re.fullmatch(r"/api/notifications/([1-9]\d{0,17})/read", path):
                svc.fields(data, set())
                return 200, svc.read_notification(conn, user, int(match[1])), {}
        svc.fail(404, "not_found", "Маршрут не найден")

    def serve_file(self, path):
        if path == "/contract":
            contract = Path(__file__).parent / "API_CONTRACT.md"
            if contract.exists():
                return self.send_bytes(200, contract.read_bytes(), "text/plain; charset=utf-8")
        root = self.server.frontend_dir
        if root:
            target = (root / unquote(path).lstrip("/\\")).resolve()
            if not target.is_relative_to(root):
                svc.fail(404, "not_found", "Файл не найден")
            if target.is_dir():
                target = target / "index.html"
            if not target.exists() and not Path(path).suffix:
                target = root / "index.html"
            if target.is_file():
                mime = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
                if mime.startswith("text/") or mime == "application/javascript":
                    mime += "; charset=utf-8"
                return self.send_bytes(200, target.read_bytes(), mime)
        if path == "/":
            html = """<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
            <title>Qadam11 — API</title><style>body{font:17px system-ui;background:#f5f6f9;color:#17202b;max-width:720px;margin:10vh auto;padding:24px}h1{font-size:40px}a{color:#cb4b16}code{background:#e5e7ec;padding:3px 6px;border-radius:5px}article{background:white;padding:36px;border-radius:24px}</style>
            <article><p>JANA POST · КЕЙС №02</p><h1>Qadam11 Digital HR</h1><p>Бэкенд запущен. Серверная проверка ролей, заявки, уведомления, обучение и помощник по учебной базе знаний.</p>
            <p><a href="/api/health">Проверить API</a> · <a href="/contract">Контракт для фронтенда</a></p>
            <p>Для интерфейса запустите отдельный frontend на <code>localhost:5173</code> или укажите <code>--frontend путь/к/dist</code> при запуске сервера.</p>
            <p>Все пользователи и HR-правила в этой сборке — демонстрационные.</p></article></html>"""
            return self.send_bytes(200, html.encode("utf-8"), "text/html; charset=utf-8")
        svc.fail(404, "not_found", "Файл не найден")


def main():
    parser = argparse.ArgumentParser(description="Qadam11 Digital HR local API")
    parser.add_argument("--host", default=os.getenv("HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "8000")))
    parser.add_argument("--db", default=os.getenv("DATABASE_PATH", str(Path(__file__).parent / "data" / "jana_hr.db")))
    parser.add_argument("--demo", action="store_true", default=os.getenv("SEED_DEMO", "0") == "1", help="Load optional demo fixture only into an empty database")
    bundled_frontend = Path(__file__).parent / "frontend" / "dist"
    parser.add_argument("--frontend", default=os.getenv("FRONTEND_DIR", str(bundled_frontend) if (bundled_frontend / "index.html").exists() else None))
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    extra_origins = {o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()}
    server = HRServer((args.host, args.port), args.db, args.frontend, DEFAULT_ORIGINS | extra_origins, seed_demo=args.demo)
    print(f"Qadam11 API: http://localhost:{server.server_port}", flush=True)
    print(f"Database: {server.db_path}", flush=True)
    print("Demo accounts and frontend contract: README.md / API_CONTRACT.md", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
