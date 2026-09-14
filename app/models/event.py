from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.utils import now_local

EVENT_TYPES = ("entry", "exit")
EVENT_STATUSES = ("pending", "processed", "failed")


class ParkingEvent(Base):
    __tablename__ = "parking_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(Enum(*EVENT_TYPES, name="event_type"), nullable=False)
    # Client-generated idempotency key (see app.schemas.event.EventCreate) —
    # lets a device safely retry a POST /events call (e.g. after a timeout)
    # without creating a duplicate event / double-counting the lot.
    request_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, index=True)
    # Tracks the async queue: the row is inserted as "pending" first (fast,
    # no lot lock — see EventUsecase.enqueue_event), then flipped to
    # "processed"/"failed" by the background task that applies it to the
    # lot's system_count (EventUsecase.process_event).
    status: Mapped[str] = mapped_column(
        Enum(*EVENT_STATUSES, name="parking_event_status"), nullable=False, default="pending"
    )
    # Optional correlation id from the edge-side tracker (e.g. YOLO track id).
    vehicle_track_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Timestamp the edge device detected the event.
    detected_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    # Timestamp the server received/persisted the event.
    received_at: Mapped[datetime] = mapped_column(DateTime, default=now_local, nullable=False)

    device: Mapped["Device"] = relationship()
