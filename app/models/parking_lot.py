from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.utils import now_local


class ParkingLot(Base):
    __tablename__ = "parking_lots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    # The official occupancy count: only manager (adjust) and admin (reset)
    # ever change this. Device-detected entry/exit no longer touches it —
    # see system_count — so a human count and the device's count can diverge
    # without one silently overwriting the other.
    current_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Device-reported occupancy count, kept in sync as entry/exit events are
    # recorded. Purely informational (shown alongside current_count for
    # comparison on the manager screen) — never drives capacity/"満車" logic.
    system_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_local, nullable=False)

    devices: Mapped[list["Device"]] = relationship(back_populates="parking_lot")

    @property
    def has_device(self) -> bool:
        return len(self.devices) > 0
