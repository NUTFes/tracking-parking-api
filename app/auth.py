"""JWT + cookie mechanics only — issuing/rotating/revoking refresh tokens is
business logic and lives in app.usecases.auth_usecase.AuthUsecase instead."""

from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Response

from app.config import settings
from app.models.admin_user import AdminUser


def create_access_token(user: AdminUser) -> str:
    # Real UTC wall-clock time, deliberately NOT now_local(): JWT exp/iat must be
    # true epoch time regardless of the host's timezone, whereas now_local() only
    # guarantees a correct *naive JST* value (see app/utils.py) — converting that
    # to epoch would silently pick up the host's local timezone offset instead.
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.id),
        "username": user.username,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_access_token(token: str) -> dict:
    """Raises jwt.PyJWTError (invalid signature, malformed, or expired)."""
    return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])


def set_refresh_cookie(response: Response, raw_token: str) -> None:
    response.set_cookie(
        key=settings.refresh_token_cookie_name,
        value=raw_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.refresh_token_expire_days * 24 * 3600,
        # Scoped to the auth endpoints only, so the refresh token isn't sent on
        # every single API request — just login/refresh/logout.
        path="/api/v1/auth",
    )


def clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(key=settings.refresh_token_cookie_name, path="/api/v1/auth")
