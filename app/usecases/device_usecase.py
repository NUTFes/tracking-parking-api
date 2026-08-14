from fastapi import Depends
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.exceptions import NotFoundError
from app.models.command import DeviceCommand
from app.models.device import Device
from app.repositories.command_repository import DeviceCommandRepository
from app.repositories.device_repository import DeviceRepository
from app.repositories.parking_lot_repository import ParkingLotRepository
from app.security import generate_secret_token, hash_token
from app.utils import now_local


class DeviceUsecase:
    def __init__(self, db: Session):
        self.db = db
        self.devices = DeviceRepository(db)
        self.commands = DeviceCommandRepository(db)
        self.parking_lots = ParkingLotRepository(db)

    def register_device(self, *, device_code: str, name: str | None, parking_lot_id: int) -> tuple[Device, str]:
        """Returns (device, plaintext_api_key) — the plaintext key exists only
        for this one call; only its hash is ever persisted."""
        api_key = generate_secret_token()
        device = self.devices.create(
            device_code=device_code,
            name=name,
            parking_lot_id=parking_lot_id,
            api_key_hash=hash_token(api_key),
        )
        self.db.commit()
        self.db.refresh(device)
        return device, api_key

    def list_devices(self) -> list[Device]:
        return self.devices.list_all()

    def get_device(self, device_id: int) -> Device:
        device = self.devices.get(device_id)
        if device is None:
            raise NotFoundError("device not found")
        return device

    def is_online(self, device: Device) -> bool:
        if device.last_seen_at is None:
            return False
        age = (now_local() - device.last_seen_at).total_seconds()
        return age <= settings.device_offline_threshold_seconds

    def update_device(
        self, device_id: int, *, device_code: str | None, name: str | None, parking_lot_id: int | None
    ) -> Device:
        device = self.get_device(device_id)
        if parking_lot_id is not None and self.parking_lots.get(parking_lot_id) is None:
            raise NotFoundError("parking lot not found")
        self.devices.update(device, device_code=device_code, name=name, parking_lot_id=parking_lot_id)
        self.db.commit()
        self.db.refresh(device)
        return device

    def delete_device(self, device_id: int) -> None:
        device = self.get_device(device_id)
        self.devices.delete(device)
        self.db.commit()

    def queue_command(self, device_id: int, *, command_type: str, requested_by: str | None) -> DeviceCommand:
        device = self.get_device(device_id)
        command = self.commands.create(device_id=device.id, command_type=command_type, requested_by=requested_by)
        self.db.commit()
        self.db.refresh(command)
        return command

    def list_commands(self, device_id: int) -> list[DeviceCommand]:
        self.get_device(device_id)  # raises NotFoundError if the device doesn't exist
        return self.commands.list_for_device(device_id)


def get_device_usecase(db: Session = Depends(get_db)) -> DeviceUsecase:
    return DeviceUsecase(db)
