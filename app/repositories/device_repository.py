from sqlalchemy.orm import Session

from app.models.device import Device


class DeviceRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, *, device_code: str, name: str | None, parking_lot_id: int, api_key_hash: str) -> Device:
        device = Device(
            device_code=device_code,
            name=name,
            parking_lot_id=parking_lot_id,
            api_key_hash=api_key_hash,
        )
        self.db.add(device)
        return device

    def list_all(self) -> list[Device]:
        return self.db.query(Device).order_by(Device.id).all()

    def get(self, device_id: int) -> Device | None:
        return self.db.get(Device, device_id)

    def get_by_api_key_hash(self, api_key_hash: str) -> Device | None:
        return self.db.query(Device).filter(Device.api_key_hash == api_key_hash).first()

    def count_for_parking_lot(self, parking_lot_id: int) -> int:
        return self.db.query(Device).filter(Device.parking_lot_id == parking_lot_id).count()

    def update(
        self, device: Device, *, device_code: str | None, name: str | None, parking_lot_id: int | None
    ) -> Device:
        if device_code is not None:
            device.device_code = device_code
        if name is not None:
            device.name = name
        if parking_lot_id is not None:
            device.parking_lot_id = parking_lot_id
        return device

    def delete(self, device: Device) -> None:
        self.db.delete(device)
