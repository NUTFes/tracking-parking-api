from sqlalchemy.orm import Session

from app.models.admin_user import AdminUser


class AdminUserRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, user_id: int) -> AdminUser | None:
        return self.db.get(AdminUser, user_id)

    def get_by_email(self, email: str) -> AdminUser | None:
        return self.db.query(AdminUser).filter(AdminUser.email == email).first()

    def list_all(self) -> list[AdminUser]:
        return self.db.query(AdminUser).order_by(AdminUser.id).all()

    def count_all(self) -> int:
        return self.db.query(AdminUser).count()

    def create(self, *, email: str) -> AdminUser:
        user = AdminUser(email=email)
        self.db.add(user)
        return user

    def delete(self, user: AdminUser) -> None:
        self.db.delete(user)
