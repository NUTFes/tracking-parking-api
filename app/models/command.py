from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.utils import now_local

COMMAND_TYPES = ("restart", "start_counting", "stop_counting")
COMMAND_STATUSES = ("pending", "delivered", "completed", "failed")


class DeviceCommand(Base):
    __tablename__ = "device_commands"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True)
    command_type: Mapped[str] = mapped_column(Enum(*COMMAND_TYPES, name="command_type"), nullable=False)
    status: Mapped[str] = mapped_column(
        Enum(*COMMAND_STATUSES, name="command_status"), nullable=False, default="pending"
    )
    requested_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    result_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_local, nullable=False)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    device: Mapped["Device"] = relationship()
