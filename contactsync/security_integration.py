from __future__ import annotations

import json
from typing import Any

from fastapi import HTTPException, Request

from contactsync.auth import ROLE_LEVEL, require_role
from contactsync.secure_config import merge_masked, migrate_connector_secrets, protected_json, public_config, runtime_config


def migrate_security(connection) -> int:
    return migrate_connector_secrets(connection)


def connector_runtime_config(raw: str | None) -> dict[str, Any]:
    return runtime_config(raw)


def connector_public_config(raw: str | None) -> dict[str, Any]:
    return public_config(raw)


def prepare_connector_update(current_raw: str | None, incoming: dict[str, Any] | None) -> tuple[dict[str, Any], str]:
    current_stored = json.loads(current_raw or "{}")
    if incoming is None:
        plain = runtime_config(current_raw)
    else:
        plain = merge_masked(current_stored, incoming)
    return plain, protected_json(plain)


def require_viewer(request: Request) -> dict[str, Any]:
    return require_role(request, "viewer")


def require_operator(request: Request) -> dict[str, Any]:
    return require_role(request, "operator")


def require_admin(request: Request) -> dict[str, Any]:
    return require_role(request, "admin")


def require_csrf_for_write(request: Request) -> dict[str, Any]:
    user = require_role(request, "operator")
    from contactsync.auth import _session_row, SESSION_COOKIE
    token = request.cookies.get(SESSION_COOKIE)
    session = _session_row(token) if token else None
    supplied = request.headers.get("X-CSRF-Token", "")
    if session is None or not supplied or supplied != session["csrf_token"]:
        raise HTTPException(403, "CSRF-Prüfung fehlgeschlagen")
    return user
