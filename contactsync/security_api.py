from __future__ import annotations

import hmac

from fastapi import APIRouter, Cookie, Header, HTTPException, Response
from pydantic import BaseModel, Field

from contactsync.auth import authenticate, change_password, create_session, destroy_session, get_session, require_role

router = APIRouter(prefix="/api/v1/auth", tags=["security"])
COOKIE = "contactsync_session"


class LoginRequest(BaseModel):
    username: str
    password: str


class PasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(min_length=10)


def session_or_401(token: str | None):
    session = get_session(token)
    if not session:
        raise HTTPException(401, "Anmeldung erforderlich")
    return session


def csrf_or_403(session, token: str | None) -> None:
    if not token or not hmac.compare_digest(session["csrf_token"], token):
        raise HTTPException(403, "Ungültiges CSRF-Token")


@router.post("/login")
def login(payload: LoginRequest, response: Response):
    user = authenticate(payload.username, payload.password)
    if not user:
        raise HTTPException(401, "Benutzername oder Passwort falsch")
    token, csrf = create_session(user["id"])
    response.set_cookie(COOKIE, token, httponly=True, secure=True, samesite="strict", max_age=12 * 3600, path="/")
    return {"username": user["username"], "role": user["role"], "must_change_password": bool(user["must_change_password"]), "csrf_token": csrf}


@router.get("/me")
def me(contactsync_session: str | None = Cookie(default=None)):
    session = session_or_401(contactsync_session)
    return {"username": session["username"], "role": session["role"], "must_change_password": bool(session["must_change_password"]), "csrf_token": session["csrf_token"]}


@router.post("/logout", status_code=204)
def logout(response: Response, contactsync_session: str | None = Cookie(default=None), x_csrf_token: str | None = Header(default=None)):
    session = session_or_401(contactsync_session)
    csrf_or_403(session, x_csrf_token)
    destroy_session(contactsync_session)
    response.delete_cookie(COOKIE, path="/")


@router.post("/password", status_code=204)
def password(payload: PasswordRequest, contactsync_session: str | None = Cookie(default=None), x_csrf_token: str | None = Header(default=None)):
    session = session_or_401(contactsync_session)
    csrf_or_403(session, x_csrf_token)
    if not change_password(session["user_id"], payload.old_password, payload.new_password):
        raise HTTPException(400, "Aktuelles Passwort ist falsch")


@router.get("/admin-check")
def admin_check(contactsync_session: str | None = Cookie(default=None)):
    session = session_or_401(contactsync_session)
    if not require_role(session, "administrator"):
        raise HTTPException(403, "Administratorrechte erforderlich")
    return {"ok": True}
