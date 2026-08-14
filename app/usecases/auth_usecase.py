from datetime import timedelta

from fastapi import Depends
from sqlalchemy.orm import Session

from app.auth import create_access_token
from app.config import settings
from app.database import get_db
from app.exceptions import UnauthorizedError
from app.models.admin_user import AdminUser
from app.repositories.admin_refresh_token_repository import AdminRefreshTokenRepository
from app.repositories.admin_user_repository import AdminUserRepository
from app.security import generate_secret_token, hash_token, verify_password
from app.utils import now_local


class AuthUsecase:
    def __init__(self, db: Session):
        self.db = db
        self.users = AdminUserRepository(db)
        self.refresh_tokens = AdminRefreshTokenRepository(db)

    def login(self, *, username: str, password: str) -> tuple[AdminUser, str, str]:
        """Returns (user, access_token, plaintext_refresh_token)."""
        user = self.users.get_by_username(username)
        if user is None or not verify_password(password, user.password_hash):
            raise UnauthorizedError("ユーザー名またはパスワードが正しくありません")
        return self._issue_tokens(user)

    def refresh(self, *, raw_refresh_token: str | None) -> tuple[AdminUser, str, str]:
        """Validates and rotates (invalidates-on-use) the refresh token."""
        if not raw_refresh_token:
            raise UnauthorizedError("refresh token missing")

        record = self.refresh_tokens.get_by_token_hash(hash_token(raw_refresh_token))
        if record is None or record.revoked_at is not None or record.expires_at < now_local():
            raise UnauthorizedError("refresh token invalid or expired")

        record.revoked_at = now_local()
        user = self.users.get(record.user_id)
        if user is None:
            raise UnauthorizedError("user not found")
        return self._issue_tokens(user)

    def logout(self, *, raw_refresh_token: str | None) -> None:
        if not raw_refresh_token:
            return
        record = self.refresh_tokens.get_by_token_hash(hash_token(raw_refresh_token))
        if record is not None and record.revoked_at is None:
            record.revoked_at = now_local()
        self.db.commit()

    def _issue_tokens(self, user: AdminUser) -> tuple[AdminUser, str, str]:
        raw_refresh_token = generate_secret_token()
        self.refresh_tokens.create(
            user_id=user.id,
            token_hash=hash_token(raw_refresh_token),
            expires_at=now_local() + timedelta(days=settings.refresh_token_expire_days),
        )
        self.db.commit()
        return user, create_access_token(user), raw_refresh_token


def get_auth_usecase(db: Session = Depends(get_db)) -> AuthUsecase:
    return AuthUsecase(db)
