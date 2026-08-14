from sqlalchemy.orm import Session

from app.models.admin_user import AdminUser


class AdminUserRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, user_id: int) -> AdminUser | None:
        return self.db.get(AdminUser, user_id)

    def get_by_email(self, email: str) -> AdminUser | None:
        return self.db.query(AdminUser).filter(AdminUser.email == email).first()
