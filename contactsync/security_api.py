from __future__ import annotations

import hmac
import sqlite3
from typing import Any

from fastapi import APIRouter, Cookie, Header, HTTPException, Request, Response
from pydantic import BaseModel, Field

from contactsync.auth import (
    ROLES, ROLE_LABELS, authenticate, change_password, create_session, create_user,
    destroy_session, ensure_bootstrap_admin, get_session, init_auth_schema, now_iso as auth_now_iso,
    require_role,
)
from contactsync.automation_core import connect
from contactsync.main import db, now_iso
from contactsync.plugins.manager import get_plugin_manager
from contactsync.security_integration import connector_public_config, connector_runtime_config, prepare_connector_update, require_admin, require_viewer

router = APIRouter(tags=["security"])
COOKIE = "contactsync_session"

class LoginRequest(BaseModel):
    username: str
    password: str

class PasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(min_length=10)

class UserCreate(BaseModel):
    username: str
    password: str = Field(min_length=10)
    role: str = "viewer"
    must_change_password: bool = True

class UserUpdate(BaseModel):
    role: str | None = None
    enabled: bool | None = None

class SecureConnectorUpdate(BaseModel):
    enabled: bool | None = None
    config: dict[str, Any] | None = None

def session_or_401(token: str | None):
    session = get_session(token)
    if not session:
        raise HTTPException(401, "Anmeldung erforderlich")
    return session

def csrf_or_403(session, token: str | None) -> None:
    if not token or not hmac.compare_digest(session["csrf_token"], token):
        raise HTTPException(403, "Ungültiges CSRF-Token")

def admin_session(token: str | None):
    session = session_or_401(token)
    if session.get("must_change_password"):
        raise HTTPException(403, "Passwortänderung erforderlich")
    if not require_role(session, "administrator"):
        raise HTTPException(403, "Administratorrechte erforderlich")
    return session

@router.post("/api/v1/auth/login")
def login(payload: LoginRequest, response: Response):
    # Fresh installations get the historical admin/admin123 account exactly once.
    # It is flagged for mandatory replacement before any protected API can be used.
    ensure_bootstrap_admin()
    user = authenticate(payload.username, payload.password)
    if not user:
        raise HTTPException(401, "Benutzername oder Passwort falsch")
    token, csrf = create_session(user["id"])
    response.set_cookie(COOKIE, token, httponly=True, secure=True, samesite="strict", max_age=12 * 3600, path="/")
    return {"username": user["username"], "role": user["role"], "role_label": ROLE_LABELS.get(user["role"], user["role"]), "must_change_password": bool(user["must_change_password"]), "csrf_token": csrf}

@router.get("/api/v1/auth/me")
def me(contactsync_session: str | None = Cookie(default=None)):
    session = session_or_401(contactsync_session)
    return {"username": session["username"], "role": session["role"], "role_label": ROLE_LABELS.get(session["role"], session["role"]), "must_change_password": bool(session["must_change_password"]), "csrf_token": session["csrf_token"]}

@router.post("/api/v1/auth/logout", status_code=204)
def logout(response: Response, contactsync_session: str | None = Cookie(default=None), x_csrf_token: str | None = Header(default=None)):
    session = session_or_401(contactsync_session)
    csrf_or_403(session, x_csrf_token)
    destroy_session(contactsync_session)
    response.delete_cookie(COOKIE, path="/", secure=True, httponly=True, samesite="strict")

@router.post("/api/v1/auth/password", status_code=204)
def password(payload: PasswordRequest, response: Response, contactsync_session: str | None = Cookie(default=None), x_csrf_token: str | None = Header(default=None)):
    session = session_or_401(contactsync_session)
    csrf_or_403(session, x_csrf_token)
    if not change_password(session["user_id"], payload.old_password, payload.new_password):
        raise HTTPException(400, "Aktuelles Passwort ist falsch")
    # change_password invalidates all sessions, so remove the now-stale browser cookie too.
    response.delete_cookie(COOKIE, path="/", secure=True, httponly=True, samesite="strict")

@router.get("/api/v1/auth/admin-check")
def admin_check(contactsync_session: str | None = Cookie(default=None)):
    admin_session(contactsync_session)
    return {"ok": True}

@router.get("/api/v1/users")
def users(contactsync_session: str | None = Cookie(default=None)):
    admin_session(contactsync_session)
    init_auth_schema()
    with connect() as connection:
        rows = connection.execute("SELECT id,username,role,enabled,must_change_password,created_at,updated_at FROM users ORDER BY username COLLATE NOCASE").fetchall()
    return [{**dict(row), "enabled": bool(row["enabled"]), "must_change_password": bool(row["must_change_password"]), "role_label": ROLE_LABELS.get(row["role"], row["role"])} for row in rows]

@router.post("/api/v1/users", status_code=201)
def add_user(payload: UserCreate, contactsync_session: str | None = Cookie(default=None), x_csrf_token: str | None = Header(default=None)):
    session = admin_session(contactsync_session)
    csrf_or_403(session, x_csrf_token)
    if payload.role not in ROLES:
        raise HTTPException(400, "Ungültige Rolle")
    try:
        user_id = create_user(payload.username, payload.password, payload.role, must_change_password=payload.must_change_password)
    except sqlite3.IntegrityError:
        raise HTTPException(409, "Benutzername bereits vorhanden")
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return {"id": user_id, "username": payload.username.strip(), "role": payload.role, "role_label": ROLE_LABELS[payload.role], "enabled": True, "must_change_password": payload.must_change_password}

@router.patch("/api/v1/users/{user_id}")
def edit_user(user_id: int, payload: UserUpdate, contactsync_session: str | None = Cookie(default=None), x_csrf_token: str | None = Header(default=None)):
    session = admin_session(contactsync_session)
    csrf_or_403(session, x_csrf_token)
    if payload.role is not None and payload.role not in ROLES:
        raise HTTPException(400, "Ungültige Rolle")
    if user_id == session["user_id"] and payload.enabled is False:
        raise HTTPException(400, "Der eigene Benutzer kann nicht deaktiviert werden")
    changes = []
    values: list[Any] = []
    if payload.role is not None:
        changes.append("role=?"); values.append(payload.role)
    if payload.enabled is not None:
        changes.append("enabled=?"); values.append(int(payload.enabled))
    if not changes:
        raise HTTPException(400, "Keine Änderung angegeben")
    changes.append("updated_at=?"); values.append(auth_now_iso()); values.append(user_id)
    with connect() as connection:
        if connection.execute("SELECT id FROM users WHERE id=?", (user_id,)).fetchone() is None:
            raise HTTPException(404, "Benutzer nicht gefunden")
        connection.execute(f"UPDATE users SET {','.join(changes)} WHERE id=?", values)
        if payload.enabled is False:
            connection.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))
        row = connection.execute("SELECT id,username,role,enabled,must_change_password,created_at,updated_at FROM users WHERE id=?", (user_id,)).fetchone()
    return {**dict(row), "enabled": bool(row["enabled"]), "must_change_password": bool(row["must_change_password"]), "role_label": ROLE_LABELS.get(row["role"], row["role"])}

@router.get("/api/v1/security/connectors")
def secure_connectors(request: Request) -> list[dict[str, Any]]:
    require_viewer(request)
    manager = get_plugin_manager(); definitions = manager.definitions()
    with db() as connection:
        rows = {row["key"]: row for row in connection.execute("SELECT * FROM connectors")}
    result = []
    for key, definition in definitions.items():
        row = rows.get(key); raw = row["config_json"] if row else "{}"; runtime = connector_runtime_config(raw)
        result.append({"key": key, **definition, "enabled": bool(row["enabled"]) if row else False, "configured": not manager.get(key).validate_config(runtime), "config": connector_public_config(raw), "status": row["last_status"] if row else "not_configured", "last_checked_at": row["last_checked_at"] if row else None})
    return result

@router.patch("/api/v1/security/connectors/{connector_key}")
def secure_update_connector(connector_key: str, payload: SecureConnectorUpdate, request: Request) -> dict[str, Any]:
    session = require_admin(request); csrf_or_403(session, request.headers.get("X-CSRF-Token"))
    manager = get_plugin_manager()
    if connector_key not in manager.definitions():
        raise HTTPException(404, "Connector-Plugin nicht gefunden")
    plugin = manager.get(connector_key)
    with db() as connection:
        current = connection.execute("SELECT * FROM connectors WHERE key=?", (connector_key,)).fetchone()
        if current is None:
            connection.execute("INSERT INTO connectors(key) VALUES(?)", (connector_key,)); current = connection.execute("SELECT * FROM connectors WHERE key=?", (connector_key,)).fetchone()
        enabled = int(payload.enabled) if payload.enabled is not None else int(current["enabled"])
        plain, protected = prepare_connector_update(current["config_json"], payload.config)
        errors = plugin.validate_config(plain); status = "ready" if enabled and not errors else ("invalid_config" if enabled and errors else "not_configured"); checked = now_iso()
        connection.execute("UPDATE connectors SET enabled=?,config_json=?,last_status=?,last_checked_at=? WHERE key=?", (enabled, protected, status, checked, connector_key))
    return {"key": connector_key, "enabled": bool(enabled), "status": status, "config": connector_public_config(protected), "config_errors": errors, "plugin_version": plugin.metadata.version}
