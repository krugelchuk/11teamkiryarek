"""SQLite persistence and explicitly fictional hackathon data."""
import hashlib
import os
import secrets
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path

TZ = timezone(timedelta(hours=5))


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def today():
    return datetime.now(TZ).date()


def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 200_000)
    return salt + ":" + digest.hex()


def password_matches(password, stored):
    return secrets.compare_digest(password_hash(password, stored.split(":")[0]), stored)


def connect(path):
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
 id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT UNIQUE NOT NULL,
 password_hash TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('employee','manager','hr')),
 company TEXT NOT NULL, position TEXT NOT NULL, department TEXT NOT NULL,
 manager_id INTEGER REFERENCES users(id), hire_date TEXT NOT NULL,
 vacation_balance INTEGER NOT NULL CHECK(vacation_balance >= 0)
);
CREATE TABLE IF NOT EXISTS sessions (
 token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
 csrf_token TEXT NOT NULL, expires_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS requests (
 id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL REFERENCES users(id),
 type TEXT NOT NULL DEFAULT 'vacation' CHECK(type='vacation'),
 start_date TEXT NOT NULL, end_date TEXT NOT NULL, days INTEGER NOT NULL CHECK(days>0),
 comment TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('pending','approved','rejected','cancelled')),
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 reviewer_id INTEGER REFERENCES users(id), decision_comment TEXT
);
CREATE TABLE IF NOT EXISTS request_history (
 id INTEGER PRIMARY KEY AUTOINCREMENT, request_id INTEGER NOT NULL REFERENCES requests(id),
 status TEXT NOT NULL, actor_id INTEGER NOT NULL REFERENCES users(id),
 comment TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS notifications (
 id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL REFERENCES users(id),
 type TEXT NOT NULL, title TEXT NOT NULL, body TEXT NOT NULL,
 entity_type TEXT NOT NULL, entity_id INTEGER NOT NULL,
 is_read INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS courses (
 id INTEGER PRIMARY KEY, title TEXT NOT NULL, description TEXT NOT NULL,
 duration_minutes INTEGER NOT NULL, question TEXT NOT NULL,
 options_json TEXT NOT NULL, correct_index INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS lessons (
 id INTEGER PRIMARY KEY, course_id INTEGER NOT NULL REFERENCES courses(id),
 title TEXT NOT NULL, content TEXT NOT NULL, position INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS enrollments (
 user_id INTEGER NOT NULL REFERENCES users(id), course_id INTEGER NOT NULL REFERENCES courses(id),
 assigned_at TEXT NOT NULL, completed_at TEXT, score INTEGER,
 PRIMARY KEY(user_id,course_id)
);
CREATE TABLE IF NOT EXISTS lesson_progress (
 user_id INTEGER NOT NULL, course_id INTEGER NOT NULL, lesson_id INTEGER NOT NULL REFERENCES lessons(id),
 completed_at TEXT NOT NULL, PRIMARY KEY(user_id,lesson_id),
 FOREIGN KEY(user_id,course_id) REFERENCES enrollments(user_id,course_id)
);
CREATE TABLE IF NOT EXISTS knowledge (
 id INTEGER PRIMARY KEY, title TEXT NOT NULL, summary TEXT NOT NULL,
 content TEXT NOT NULL, keywords TEXT NOT NULL, roles TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit_log (
 id INTEGER PRIMARY KEY AUTOINCREMENT, actor_id INTEGER NOT NULL REFERENCES users(id),
 action TEXT NOT NULL, entity_type TEXT NOT NULL, entity_id INTEGER NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS login_attempts (
 client TEXT NOT NULL, attempted_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS requests_owner ON requests(user_id,status);
CREATE INDEX IF NOT EXISTS users_manager ON users(manager_id);
CREATE INDEX IF NOT EXISTS notifications_owner ON notifications(user_id,is_read);
CREATE INDEX IF NOT EXISTS login_client ON login_attempts(client,attempted_at);
"""


def notify(conn, user_id, kind, title, body, entity_type, entity_id):
    conn.execute(
        "INSERT INTO notifications(user_id,type,title,body,entity_type,entity_id,created_at) VALUES(?,?,?,?,?,?,?)",
        (user_id, kind, title, body, entity_type, entity_id, now()),
    )


def audit(conn, actor_id, action, entity_type, entity_id):
    conn.execute(
        "INSERT INTO audit_log(actor_id,action,entity_type,entity_id,created_at) VALUES(?,?,?,?,?)",
        (actor_id, action, entity_type, entity_id, now()),
    )


def initialize(path, seed_demo=False):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with closing(connect(path)) as conn, conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(SCHEMA)
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(knowledge)")}
        if "is_active" not in columns:
            conn.execute("ALTER TABLE knowledge ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1")
        if "updated_at" not in columns:
            conn.execute("ALTER TABLE knowledge ADD COLUMN updated_at TEXT")
        conn.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        conn.execute("CREATE TABLE IF NOT EXISTS learning_imports (kind TEXT NOT NULL, slug TEXT NOT NULL, entity_id INTEGER NOT NULL, PRIMARY KEY(kind,slug))")
        conn.execute("INSERT OR IGNORE INTO settings VALUES('demo_mode','0')")
        from . import branches
        branches.initialize(conn)
        conn.commit()
        if seed_demo:
            from .seed import load_demo
            conn.execute("BEGIN IMMEDIATE")
            load_demo(conn)
