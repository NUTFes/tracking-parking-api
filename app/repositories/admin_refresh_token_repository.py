from datetime import datetime

from sqlalchemy.orm import Session

from app.models.admin_refresh_token import AdminRefreshToken


class AdminRefreshTokenRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, *, user_id: int, token_hash: str, expires_at: datetime) -> AdminRefreshToken:
        record = AdminRefreshToken(user_id=user_id, token_hash=token_hash, expires_at=expires_at)
        self.db.add(record)
        return record

    def get_by_token_hash(self, token_hash: str) -> AdminRefreshToken | None:
        return self.db.query(AdminRefreshToken).filter(AdminRefreshToken.token_hash == token_hash).first()
