from __future__ import annotations

import hmac
import json
from typing import Any

from fastapi import HTTPException, Request

from contactsync.auth import get_session, require_role
from contactsync.secure_config import merge_masked, migrate_connector_secrets, protected_json, public_config, runtime_config

SESSION_COOKIE = "contactsync_session"


def migrate_security(connection) -> int:
    return migrate_connector_secrets(connection)


def connector_runtime_config(raw: str | None) -> dict[str, Any]:
    return runtime_config(raw)


def connector_public_config(raw: str | None) -> dict[str, Any]:
    return public_config(raw)


def prepare_connector_update(current_raw: str | None, incoming: dict[str, Any] | None) -> tuple[dict[str, Any], str]:
    current_stored = json.loads(current_raw or "{}")
    plain = runtime_config(current_raw) if incoming is None else merge_masked(current_stored, incoming)
    return plain, protected_json(plain)


def _session(request: Request) -> dict[str, Any]:
    session = get_session(request.cookies.get(SESSION_COOKIE))
    if not session:
        raise HTTPException(401, "Anmeldung erforderlich")
    return session


def require_request_role(request: Request, minimum: str) -> dict[str, Any]:
    session = _session(request)
    if not require_role(session, minimum):
        raise HTTPException(403, "Unzureichende Berechtigung")
    return session


def require_viewer(request: Request) -> dict[str, Any]:
    return require_request_role(request, "viewer")


def require_operator(request: Request) -> dict[str, Any]:
    return require_request_role(request, "operator")


def require_admin(request: Request) -> dict[str, Any]:
    return require_request_role(request, "administrator")


def require_csrf_for_write(request: Request, minimum: str = "operator") -> dict[str, Any]:
    session = require_request_role(request, minimum)
    supplied = request.headers.get("X-CSRF-Token", "")
    if not supplied or not hmac.compare_digest(supplied, session["csrf_token"]):
        raise HTTPException(403, "CSRF-Prüfung fehlgeschlagen")
    return session
