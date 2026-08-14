from sqlalchemy.orm import Session

from app.models.command import DeviceCommand


class DeviceCommandRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, *, device_id: int, command_type: str, requested_by: str | None) -> DeviceCommand:
        command = DeviceCommand(device_id=device_id, command_type=command_type, requested_by=requested_by)
        self.db.add(command)
        return command

    def get(self, command_id: int) -> DeviceCommand | None:
        return self.db.get(DeviceCommand, command_id)

    def list_pending_for_device(self, device_id: int) -> list[DeviceCommand]:
        return (
            self.db.query(DeviceCommand)
            .filter(DeviceCommand.device_id == device_id, DeviceCommand.status == "pending")
            .all()
        )

    def list_for_device(self, device_id: int) -> list[DeviceCommand]:
        return (
            self.db.query(DeviceCommand)
            .filter(DeviceCommand.device_id == device_id)
            .order_by(DeviceCommand.created_at.desc())
            .all()
        )
