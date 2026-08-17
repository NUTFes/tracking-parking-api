from fastapi import Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.exceptions import ConflictError, NotFoundError
from app.models.admin_user import AdminUser
from app.repositories.admin_user_repository import AdminUserRepository


class AdminUserUsecase:
    def __init__(self, db: Session):
        self.db = db
        self.admin_users = AdminUserRepository(db)

    def list_users(self) -> list[AdminUser]:
        return self.admin_users.list_all()

    def create_user(self, *, email: str) -> AdminUser:
        """`email` is assumed already normalized/format-checked — see
        app.schemas.admin_user.AdminUserCreate. Only the DB-dependent
        uniqueness check belongs here."""
        if self.admin_users.get_by_email(email) is not None:
            raise ConflictError("このメールアドレスは既に許可リストに登録されています")
        user = self.admin_users.create(email=email)
        self.db.commit()
        self.db.refresh(user)
        return user

    def delete_user(self, user_id: int) -> None:
        user = self.admin_users.get(user_id)
        if user is None:
            raise NotFoundError("admin user not found")
        # Guard against locking every admin out of admin-web via a misclick —
        # the CLI (scripts/manage_admin_allowlist.py) remains available for
        # recovery, but the UI shouldn't be able to reach a zero-admin state.
        if self.admin_users.count_all() <= 1:
            raise ConflictError("最後の管理者アカウントは削除できません")
        self.admin_users.delete(user)
        self.db.commit()


def get_admin_user_usecase(db: Session = Depends(get_db)) -> AdminUserUsecase:
    return AdminUserUsecase(db)
