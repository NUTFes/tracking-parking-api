from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.utils import now_local


class AdminUser(Base):
    """A row here is an entry in the admin-web Google-account allow-list —
    see scripts/manage_admin_allowlist.py. No password: identity is proven by
    a verified Google ID token (app/google_auth.py); this table only decides
    which verified accounts are allowed in."""

    __tablename__ = "admin_users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_local, nullable=False)
