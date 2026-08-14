import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app import google_auth
from app.auth import decode_access_token
from app.database import get_db
from app.models.admin_user import AdminUser
from app.models.device import Device
from app.repositories.admin_user_repository import AdminUserRepository
from app.repositories.device_repository import DeviceRepository
from app.security import hash_token

# auto_error=False on both: we want our own 401 + detail message (consistent
# with the rest of the app) instead of each scheme's default error, while still
# getting them registered as OpenAPI security schemes (Swagger's padlock icon
# and "Authorize" button, and per-endpoint `security` requirements).
_bearer_scheme = HTTPBearer(
    auto_error=False, scheme_name="AdminAccessToken", description="Admin console access token (from /auth/google)"
)
_api_key_scheme = APIKeyHeader(name="X-API-Key", auto_error=False, description="Edge device API key")
# Distinct scheme_name from _bearer_scheme: both are structurally HTTPBearer,
# but this one carries a raw Google ID token (verified per-request against
# Google, no session of ours), not our own JWT — keep them visually separate
# in the OpenAPI/Swagger UI.
_google_id_token_scheme = HTTPBearer(
    auto_error=False, scheme_name="GoogleIdToken", description="Google ID token (Sign In With Google)"
)


def get_current_device(
    x_api_key: str | None = Depends(_api_key_scheme),
    db: Session = Depends(get_db),
) -> Device:
    """Resolves the calling edge device from its API key. Device-facing endpoints
    (events, heartbeat, command ack) use this instead of a device id in the path,
    so a device only needs to know its own secret token, nothing else.

    Lives in deps.py rather than a usecase: this is FastAPI-specific request
    auth resolution (raises HTTPException directly), not reusable business
    logic — usecases stay framework-agnostic and raise DomainError instead."""
    if not x_api_key:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="X-API-Key header is required")

    device = DeviceRepository(db).get_by_api_key_hash(hash_token(x_api_key))
    if device is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="invalid API key")
    return device


def get_current_admin_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> AdminUser:
    """Resolves the logged-in admin user from a short-lived JWT access token
    (`Authorization: Bearer <token>`), issued by /auth/login or /auth/refresh.
    Admin-console mutating/operational endpoints depend on this."""
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Authorization header is required")

    try:
        payload = decode_access_token(credentials.credentials)
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="invalid or expired access token")

    user = AdminUserRepository(db).get(int(payload["sub"]))
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="user not found")
    return user


def get_current_general_user_label(
    credentials: HTTPAuthorizationCredentials | None = Depends(_google_id_token_scheme),
) -> str:
    """Resolves the acting person's log label (e.g. "25.m.kitano") from a raw
    Google ID token sent directly by the frontend (services/web) on each
    request. Unlike admin auth, this issues no session of ours — every
    mutating request re-verifies the token against Google — and there's no
    allow-list: any Google account matching the NUTFes executive-committee
    email format is accepted. Used only by the manual parking-count-adjustment
    endpoint, which is intentionally lightweight."""
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Google ID token is required")

    email = google_auth.verify_google_id_token(credentials.credentials)
    return google_auth.label_from_email(email)
