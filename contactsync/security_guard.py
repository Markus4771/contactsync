from __future__ import annotations

import hmac

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from contactsync.auth import get_session, require_role

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
PUBLIC_PATHS = {"/health", "/api/v1/auth/login"}
ADMIN_PREFIXES = ("/api/v1/security/connectors", "/api/v1/connectors")
OPERATOR_PREFIXES = (
    "/api/v1/sync", "/api/v1/customers", "/api/v1/devices", "/api/v1/netlock",
    "/api/v1/assets", "/api/v1/automation", "/api/v1/monitoring", "/api/v1/incidents",
)


class SecurityGuardMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path in PUBLIC_PATHS or path.startswith("/docs") or path.startswith("/openapi") or path.startswith("/redoc"):
            return await call_next(request)
        if not path.startswith("/api/v1/"):
            return await call_next(request)
        # Auth endpoints perform their own session/CSRF checks.
        if path.startswith("/api/v1/auth/"):
            return await call_next(request)
        session = get_session(request.cookies.get("contactsync_session"))
        if not session:
            return JSONResponse({"detail": "Anmeldung erforderlich"}, status_code=401)
        minimum = "viewer"
        if request.method not in SAFE_METHODS:
            minimum = "operator"
        if request.method not in SAFE_METHODS and any(path.startswith(prefix) for prefix in ADMIN_PREFIXES):
            minimum = "administrator"
        if not require_role(session, minimum):
            return JSONResponse({"detail": "Unzureichende Berechtigung"}, status_code=403)
        if request.method not in SAFE_METHODS:
            supplied = request.headers.get("X-CSRF-Token", "")
            if not supplied or not hmac.compare_digest(supplied, session["csrf_token"]):
                return JSONResponse({"detail": "CSRF-Prüfung fehlgeschlagen"}, status_code=403)
        return await call_next(request)
