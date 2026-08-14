import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

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
_bearer_scheme = HTTPBearer(auto_error=False, description="Admin console access token (from /auth/login)")
_api_key_scheme = APIKeyHeader(name="X-API-Key", auto_error=False, description="Edge device API key")


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
