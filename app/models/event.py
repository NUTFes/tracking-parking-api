from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.utils import now_local

EVENT_TYPES = ("entry", "exit")


class ParkingEvent(Base):
    __tablename__ = "parking_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(Enum(*EVENT_TYPES, name="event_type"), nullable=False)
    # Optional correlation id from the edge-side tracker (e.g. YOLO track id).
    vehicle_track_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Timestamp the edge device detected the event.
    detected_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    # Timestamp the server received/persisted the event.
    received_at: Mapped[datetime] = mapped_column(DateTime, default=now_local, nullable=False)

    device: Mapped["Device"] = relationship()
