from datetime import datetime

from fastapi import Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.device import Device
from app.models.event import ParkingEvent
from app.repositories.event_repository import ParkingEventRepository
from app.repositories.parking_lot_repository import ParkingLotRepository
from app.utils import now_local, to_naive_local


class EventUsecase:
    def __init__(self, db: Session):
        self.db = db
        self.events = ParkingEventRepository(db)
        self.parking_lots = ParkingLotRepository(db)

    def record_event(
        self, *, device: Device, event_type: str, vehicle_track_id: str | None, detected_at: datetime
    ) -> ParkingEvent:
        """Records the event and keeps the parking lot's running occupancy
        count in sync in the same transaction (row-locked via
        ParkingLotRepository.get_for_update, so concurrent entries/exits from
        different devices at the same lot serialize instead of racing)."""
        event = self.events.create(
            device_id=device.id,
            event_type=event_type,
            vehicle_track_id=vehicle_track_id,
            detected_at=to_naive_local(detected_at),
            received_at=now_local(),
        )

        lot = self.parking_lots.get_for_update(device.parking_lot_id)
        if lot is not None:
            if event_type == "entry":
                lot.current_count += 1
            else:
                lot.current_count = max(0, lot.current_count - 1)

        self.db.commit()
        self.db.refresh(event)
        return event


def get_event_usecase(db: Session = Depends(get_db)) -> EventUsecase:
    return EventUsecase(db)
