from __future__ import annotations

import hmac
from typing import Any

from fastapi import APIRouter, Cookie, Header, HTTPException, Request, Response
from pydantic import BaseModel, Field

from contactsync.auth import authenticate, change_password, create_session, destroy_session, get_session, require_role
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


@router.post("/api/v1/auth/login")
def login(payload: LoginRequest, response: Response):
    user = authenticate(payload.username, payload.password)
    if not user:
        raise HTTPException(401, "Benutzername oder Passwort falsch")
    token, csrf = create_session(user["id"])
    response.set_cookie(COOKIE, token, httponly=True, secure=True, samesite="strict", max_age=12 * 3600, path="/")
    return {"username": user["username"], "role": user["role"], "must_change_password": bool(user["must_change_password"]), "csrf_token": csrf}


@router.get("/api/v1/auth/me")
def me(contactsync_session: str | None = Cookie(default=None)):
    session = session_or_401(contactsync_session)
    return {"username": session["username"], "role": session["role"], "must_change_password": bool(session["must_change_password"]), "csrf_token": session["csrf_token"]}


@router.post("/api/v1/auth/logout", status_code=204)
def logout(response: Response, contactsync_session: str | None = Cookie(default=None), x_csrf_token: str | None = Header(default=None)):
    session = session_or_401(contactsync_session)
    csrf_or_403(session, x_csrf_token)
    destroy_session(contactsync_session)
    response.delete_cookie(COOKIE, path="/")


@router.post("/api/v1/auth/password", status_code=204)
def password(payload: PasswordRequest, contactsync_session: str | None = Cookie(default=None), x_csrf_token: str | None = Header(default=None)):
    session = session_or_401(contactsync_session)
    csrf_or_403(session, x_csrf_token)
    if not change_password(session["user_id"], payload.old_password, payload.new_password):
        raise HTTPException(400, "Aktuelles Passwort ist falsch")


@router.get("/api/v1/auth/admin-check")
def admin_check(contactsync_session: str | None = Cookie(default=None)):
    session = session_or_401(contactsync_session)
    if not require_role(session, "administrator"):
        raise HTTPException(403, "Administratorrechte erforderlich")
    return {"ok": True}


@router.get("/api/v1/security/connectors")
def secure_connectors(request: Request) -> list[dict[str, Any]]:
    require_viewer(request)
    manager = get_plugin_manager()
    definitions = manager.definitions()
    with db() as connection:
        rows = {row["key"]: row for row in connection.execute("SELECT * FROM connectors")}
    result = []
    for key, definition in definitions.items():
        row = rows.get(key)
        raw = row["config_json"] if row else "{}"
        runtime = connector_runtime_config(raw)
        result.append({"key": key, **definition, "enabled": bool(row["enabled"]) if row else False, "configured": not manager.get(key).validate_config(runtime), "config": connector_public_config(raw), "status": row["last_status"] if row else "not_configured", "last_checked_at": row["last_checked_at"] if row else None})
    return result


@router.patch("/api/v1/security/connectors/{connector_key}")
def secure_update_connector(connector_key: str, payload: SecureConnectorUpdate, request: Request) -> dict[str, Any]:
    session = require_admin(request)
    csrf_or_403(session, request.headers.get("X-CSRF-Token"))
    manager = get_plugin_manager()
    if connector_key not in manager.definitions():
        raise HTTPException(404, "Connector-Plugin nicht gefunden")
    plugin = manager.get(connector_key)
    with db() as connection:
        current = connection.execute("SELECT * FROM connectors WHERE key=?", (connector_key,)).fetchone()
        if current is None:
            connection.execute("INSERT INTO connectors(key) VALUES(?)", (connector_key,))
            current = connection.execute("SELECT * FROM connectors WHERE key=?", (connector_key,)).fetchone()
        enabled = int(payload.enabled) if payload.enabled is not None else int(current["enabled"])
        plain, protected = prepare_connector_update(current["config_json"], payload.config)
        errors = plugin.validate_config(plain)
        status = "ready" if enabled and not errors else ("invalid_config" if enabled and errors else "not_configured")
        checked = now_iso()
        connection.execute("UPDATE connectors SET enabled=?,config_json=?,last_status=?,last_checked_at=? WHERE key=?", (enabled, protected, status, checked, connector_key))
    return {"key": connector_key, "enabled": bool(enabled), "status": status, "config": connector_public_config(protected), "config_errors": errors, "plugin_version": plugin.metadata.version}
