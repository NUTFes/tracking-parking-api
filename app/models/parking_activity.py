from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.utils import now_local

ACTIVITY_TYPES = ("entry", "exit", "manual_adjustment", "reset")


class ParkingActivity(Base):
    """Unified, append-only log of every current_count change — device-
    detected entry/exit alongside human-triggered manual adjustments and
    resets — for time-series analysis and "who changed what" auditing."""

    __tablename__ = "parking_activities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    parking_lot_id: Mapped[int] = mapped_column(
        ForeignKey("parking_lots.id", ondelete="CASCADE"), nullable=False, index=True
    )
    activity_type: Mapped[str] = mapped_column(Enum(*ACTIVITY_TYPES, name="activity_type"), nullable=False)
    delta: Mapped[int] = mapped_column(Integer, nullable=False)
    count_after: Mapped[int] = mapped_column(Integer, nullable=False)
    # Denormalized (not a FK) so this survives device/admin-user deletion and
    # doesn't require a persisted users table for the stateless general-user
    # auth: a device_code (entry/exit) or a verified Google account's local-
    # part label, e.g. "25.m.kitano" (manual_adjustment/reset).
    actor_label: Mapped[str] = mapped_column(String(255), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_local, nullable=False)

    parking_lot: Mapped["ParkingLot"] = relationship()
