from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from contactsync.automation_core import connect
from contactsync.security import hash_password, verify_password

ROLES = ("viewer", "operator", "administrator")
ROLE_LEVEL = {"viewer": 10, "operator": 20, "administrator": 30}
SESSION_HOURS = 12


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_auth_schema() -> None:
    with connect() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'viewer',
                enabled INTEGER NOT NULL DEFAULT 1,
                must_change_password INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                token_hash TEXT NOT NULL UNIQUE,
                csrf_token TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(token_hash);
            """
        )


def create_user(username: str, password: str, role: str = "viewer", *, must_change_password: bool = False) -> int:
    init_auth_schema()
    username = username.strip()
    if not username:
        raise ValueError("Benutzername darf nicht leer sein")
    if role not in ROLES:
        raise ValueError("Ungültige Rolle")
    stamp = now_iso()
    with connect() as connection:
        cursor = connection.execute(
            "INSERT INTO users(username,password_hash,role,enabled,must_change_password,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
            (username, hash_password(password), role, 1, int(must_change_password), stamp, stamp),
        )
        return int(cursor.lastrowid)


def authenticate(username: str, password: str) -> dict[str, Any] | None:
    init_auth_schema()
    with connect() as connection:
        row = connection.execute("SELECT * FROM users WHERE username=? COLLATE NOCASE AND enabled=1", (username.strip(),)).fetchone()
    if not row or not verify_password(password, row["password_hash"]):
        return None
    return dict(row)


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_session(user_id: int) -> tuple[str, str]:
    init_auth_schema()
    token = secrets.token_urlsafe(48)
    csrf = secrets.token_urlsafe(32)
    stamp = datetime.now(timezone.utc)
    expires = stamp + timedelta(hours=SESSION_HOURS)
    with connect() as connection:
        connection.execute(
            "INSERT INTO sessions(user_id,token_hash,csrf_token,expires_at,created_at,last_seen_at) VALUES(?,?,?,?,?,?)",
            (user_id, _digest(token), csrf, expires.isoformat(), stamp.isoformat(), stamp.isoformat()),
        )
    return token, csrf


def get_session(token: str | None) -> dict[str, Any] | None:
    if not token:
        return None
    init_auth_schema()
    with connect() as connection:
        row = connection.execute(
            """SELECT s.id session_id,s.csrf_token,s.expires_at,u.id user_id,u.username,u.role,u.must_change_password
               FROM sessions s JOIN users u ON u.id=s.user_id
               WHERE s.token_hash=? AND u.enabled=1""",
            (_digest(token),),
        ).fetchone()
        if not row or row["expires_at"] <= now_iso():
            if row:
                connection.execute("DELETE FROM sessions WHERE id=?", (row["session_id"],))
            return None
        connection.execute("UPDATE sessions SET last_seen_at=? WHERE id=?", (now_iso(), row["session_id"]))
        return dict(row)


def destroy_session(token: str | None) -> None:
    if not token:
        return
    init_auth_schema()
    with connect() as connection:
        connection.execute("DELETE FROM sessions WHERE token_hash=?", (_digest(token),))


def require_role(session: dict[str, Any] | None, minimum: str) -> bool:
    return bool(session and ROLE_LEVEL.get(session.get("role", ""), 0) >= ROLE_LEVEL[minimum])


def change_password(user_id: int, old_password: str, new_password: str) -> bool:
    init_auth_schema()
    with connect() as connection:
        row = connection.execute("SELECT password_hash FROM users WHERE id=? AND enabled=1", (user_id,)).fetchone()
        if not row or not verify_password(old_password, row["password_hash"]):
            return False
        connection.execute("UPDATE users SET password_hash=?,must_change_password=0,updated_at=? WHERE id=?", (hash_password(new_password), now_iso(), user_id))
        connection.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))
        return True
