"""Sign-in for the web app: Argon2 password hashes, signed httpOnly session cookie.

Every API route requires a valid session except the ones in `PUBLIC_PATHS`.
Sessions are stateless signed tokens (itsdangerous), re-checked against the
`users` table on each request so a deactivated user is locked out at once.
"""

from __future__ import annotations

import logging
import os
import secrets
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from itsdangerous import BadSignature, URLSafeTimedSerializer
from pydantic import BaseModel, Field
from sqlalchemy import select

from backend import activity, db

log = logging.getLogger(__name__)

COOKIE_NAME = "rgs_session"
SESSION_SECONDS = 12 * 60 * 60
REMEMBER_SECONDS = 30 * 24 * 60 * 60
MAX_FAILURES = 5
FAILURE_WINDOW_SECONDS = 15 * 60
PUBLIC_PATHS = frozenset({"/auth/login", "/healthz", "/readyz"})
_DEV_SECRET_FILE = Path(__file__).resolve().parent.parent / ".auth_dev_secret"

_hasher = PasswordHasher()
_failures: dict[str, deque[float]] = defaultdict(deque)
_dummy_hash: str | None = None
router = APIRouter(prefix="/auth", tags=["auth"])


class LoginIn(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=256)
    remember_me: bool = False


def _secret() -> str:
    configured = os.getenv("AUTH_SECRET_KEY")
    if configured:
        return configured
    # Local development only: a persistent random key (gitignored) so reloads keep you signed in.
    if not _DEV_SECRET_FILE.exists():
        _DEV_SECRET_FILE.write_text(secrets.token_urlsafe(48), encoding="utf-8")
        log.warning("AUTH_SECRET_KEY is not set; generated a local dev key. Set it for any shared deployment.")
    return _DEV_SECRET_FILE.read_text(encoding="utf-8").strip()


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(_secret(), salt="rgs-session")


def normalize_email(email: str) -> str:
    return email.strip().lower()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def _verify(stored_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(stored_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def _public_user(user: db.User) -> dict[str, str]:
    return {"email": user.email, "display_name": user.display_name}


def _factory():
    factory = db.get_session_factory()
    if factory is None:
        raise HTTPException(status_code=503, detail="Sign-in is unavailable: DATABASE_URL is not configured")
    return factory


def upsert_user(email: str, password: str, display_name: str) -> str:
    """Create the user, or reset the password and name if the email already exists."""
    email = normalize_email(email)
    with _factory()() as session:
        user = session.scalar(select(db.User).where(db.User.email == email))
        if user is None:
            session.add(db.User(id=str(uuid4()), email=email, display_name=display_name,
                                password_hash=hash_password(password), is_active=True))
            outcome = "created"
        else:
            user.display_name, user.password_hash, user.is_active = display_name, hash_password(password), True
            outcome = "updated"
        session.commit()
    return outcome


def _recent_failures(email: str) -> deque[float]:
    window = _failures[email]
    cutoff = time.monotonic() - FAILURE_WINDOW_SECONDS
    while window and window[0] < cutoff:
        window.popleft()
    return window


def _set_cookie(response: Response, token: str, max_age: int) -> None:
    secure = os.getenv("AUTH_COOKIE_SECURE", "").lower() in {"1", "true", "yes"}
    response.set_cookie(COOKIE_NAME, token, max_age=max_age, httponly=True, samesite="lax", secure=secure, path="/")


def _user_from_request(request: Request) -> db.User | None:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    try:
        payload, issued = _serializer().loads(token, max_age=REMEMBER_SECONDS, return_timestamp=True)
    except BadSignature:
        return None
    age = time.time() - issued.timestamp()
    if not payload.get("rm") and age > SESSION_SECONDS:
        return None
    with _factory()() as session:
        user = session.get(db.User, payload.get("uid"))
        if user is None or not user.is_active:
            return None
        session.expunge(user)
        return user


async def require_user(request: Request) -> None:
    """App-wide dependency: 401 unless the request carries a valid session."""
    if request.method == "OPTIONS" or request.url.path in PUBLIC_PATHS:
        return
    if _user_from_request(request) is None:
        raise HTTPException(status_code=401, detail="Not signed in")


async def current_user(request: Request) -> db.User:
    """Dependency for routes that need to know who is calling (e.g. to stamp edits and audit rows)."""
    user = _user_from_request(request)
    if user is None:
        raise HTTPException(status_code=401, detail="Not signed in")
    return user


CurrentUser = Annotated[db.User, Depends(current_user)]


@router.post("/login")
def login(body: LoginIn, response: Response) -> dict:
    global _dummy_hash
    email = normalize_email(body.email)
    window = _recent_failures(email)
    if len(window) >= MAX_FAILURES:
        raise HTTPException(status_code=429, detail="Too many failed attempts. Try again in a few minutes.")
    with _factory()() as session:
        user = session.scalar(select(db.User).where(db.User.email == email))
        if user is None:
            # Burn the same hashing time so a missing account is not distinguishable by latency.
            _dummy_hash = _dummy_hash or hash_password(secrets.token_urlsafe(16))
            _verify(_dummy_hash, body.password)
            ok = False
        else:
            ok = _verify(user.password_hash, body.password) and user.is_active
        if not ok:
            window.append(time.monotonic())
            activity.record(email, "auth.login_failed")
            raise HTTPException(status_code=401, detail="Invalid email or password")
        _failures.pop(email, None)
        token = _serializer().dumps({"uid": user.id, "rm": body.remember_me})
        _set_cookie(response, token, REMEMBER_SECONDS if body.remember_me else SESSION_SECONDS)
        activity.record(user.email, "auth.login")
        return {"success": True, "user": _public_user(user)}


@router.post("/logout")
def logout(request: Request, response: Response) -> dict:
    user = _user_from_request(request)
    if user is not None:
        activity.record(user.email, "auth.logout")
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"success": True}


@router.get("/me")
def me(request: Request) -> dict:
    user = _user_from_request(request)
    if user is None:
        raise HTTPException(status_code=401, detail="Not signed in")
    return {"user": _public_user(user)}
