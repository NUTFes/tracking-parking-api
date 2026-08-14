from datetime import datetime

from fastapi import Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.exceptions import NotFoundError
from app.models.command import DeviceCommand
from app.models.device import Device
from app.repositories.command_repository import DeviceCommandRepository
from app.utils import now_local


class HeartbeatUsecase:
    def __init__(self, db: Session):
        self.db = db
        self.commands = DeviceCommandRepository(db)

    def record_heartbeat(self, *, device: Device, status: str) -> tuple[datetime, list[DeviceCommand]]:
        """Updates device liveness and hands back any commands queued for it
        since the last poll — the only channel the server has to reach a
        device that sits behind NAT with no inbound connectivity. Returns
        (server_time, commands) so the caller doesn't need a second "now"."""
        now = now_local()
        device.last_status = status
        device.last_seen_at = now

        pending = self.commands.list_pending_for_device(device.id)
        for command in pending:
            command.status = "delivered"
            command.delivered_at = now

        self.db.commit()
        for command in pending:
            self.db.refresh(command)
        return now, pending

    def ack_command(
        self, *, device: Device, command_id: int, status: str, result_message: str | None
    ) -> DeviceCommand:
        command = self.commands.get(command_id)
        if command is None or command.device_id != device.id:
            raise NotFoundError("command not found")

        command.status = status
        command.result_message = result_message
        command.completed_at = now_local()
        self.db.commit()
        self.db.refresh(command)
        return command


def get_heartbeat_usecase(db: Session = Depends(get_db)) -> HeartbeatUsecase:
    return HeartbeatUsecase(db)
