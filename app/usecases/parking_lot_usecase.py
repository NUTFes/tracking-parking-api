from datetime import datetime
from typing import Literal

from fastapi import Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.exceptions import ConflictError, NotFoundError
from app.models.event import ParkingEvent
from app.models.parking_activity import ParkingActivity
from app.models.parking_lot import ParkingLot
from app.repositories.device_repository import DeviceRepository
from app.repositories.event_repository import ParkingEventRepository
from app.repositories.parking_activity_repository import ParkingActivityRepository
from app.repositories.parking_lot_repository import ParkingLotRepository


class ParkingLotUsecase:
    def __init__(self, db: Session):
        self.db = db
        self.parking_lots = ParkingLotRepository(db)
        self.events = ParkingEventRepository(db)
        self.devices = DeviceRepository(db)
        self.activities = ParkingActivityRepository(db)

    def create_parking_lot(self, *, name: str, capacity: int) -> ParkingLot:
        lot = self.parking_lots.create(name=name, capacity=capacity)
        self.db.commit()
        self.db.refresh(lot)
        return lot

    def list_parking_lots(self) -> list[ParkingLot]:
        return self.parking_lots.list_all()

    def get_parking_lot(self, lot_id: int) -> ParkingLot:
        lot = self.parking_lots.get(lot_id)
        if lot is None:
            raise NotFoundError("parking lot not found")
        return lot

    def update_parking_lot(self, lot_id: int, *, name: str | None, capacity: int | None) -> ParkingLot:
        lot = self.get_parking_lot(lot_id)
        self.parking_lots.update(lot, name=name, capacity=capacity)
        self.db.commit()
        self.db.refresh(lot)
        return lot

    def delete_parking_lot(self, lot_id: int) -> None:
        lot = self.get_parking_lot(lot_id)
        if self.devices.count_for_parking_lot(lot_id) > 0:
            raise ConflictError("この駐車場に紐づくデバイスが存在するため削除できません")
        self.parking_lots.delete(lot)
        self.db.commit()

    def reset_count(
        self, lot_id: int, *, count: int, target: Literal["current", "system"], actor_label: str, note: str | None
    ) -> ParkingLot:
        """Admin-only: force current_count or system_count to an exact value
        (e.g. after reconciling against a physical headcount, or correcting
        device drift)."""
        lot = self.parking_lots.get_for_update(lot_id)
        if lot is None:
            raise NotFoundError("parking lot not found")

        if target == "current":
            delta = count - lot.current_count
            lot.current_count = count
            activity_type = "reset"
        else:
            delta = count - lot.system_count
            lot.system_count = count
            activity_type = "system_reset"

        self.activities.create(
            parking_lot_id=lot.id,
            activity_type=activity_type,
            delta=delta,
            count_after=count,
            actor_label=actor_label,
            note=note,
        )
        self.db.commit()
        self.db.refresh(lot)
        return lot

    def reset_all_counts(
        self, *, target: Literal["current", "system"], actor_label: str, note: str | None
    ) -> list[ParkingLot]:
        """Admin-only: reset every parking lot's current_count or
        system_count to 0 in one operation (e.g. at the start of an event)."""
        lots = self.parking_lots.list_all()
        activity_type = "reset" if target == "current" else "system_reset"
        for lot in lots:
            before = lot.current_count if target == "current" else lot.system_count
            if target == "current":
                lot.current_count = 0
            else:
                lot.system_count = 0
            self.activities.create(
                parking_lot_id=lot.id,
                activity_type=activity_type,
                delta=-before,
                count_after=0,
                actor_label=actor_label,
                note=note,
            )
        self.db.commit()
        for lot in lots:
            self.db.refresh(lot)
        return lots

    def adjust_count(self, lot_id: int, *, delta: int, actor_label: str, note: str | None) -> ParkingLot:
        """General-user operation: nudge current_count by a signed delta,
        clamped at 0 (same floor as device-detected exits)."""
        lot = self.parking_lots.get_for_update(lot_id)
        if lot is None:
            raise NotFoundError("parking lot not found")

        before = lot.current_count
        lot.current_count = max(0, before + delta)
        applied_delta = lot.current_count - before
        self.activities.create(
            parking_lot_id=lot.id,
            activity_type="manual_adjustment",
            delta=applied_delta,
            count_after=lot.current_count,
            actor_label=actor_label,
            note=note,
        )
        self.db.commit()
        self.db.refresh(lot)
        return lot

    def list_events(
        self, lot_id: int, *, since: datetime | None, until: datetime | None, limit: int
    ) -> list[ParkingEvent]:
        self.get_parking_lot(lot_id)  # raises NotFoundError if the lot doesn't exist
        return self.events.list_for_lot(lot_id, since=since, until=until, limit=limit)

    def list_activities(self, lot_id: int, *, limit: int) -> list[ParkingActivity]:
        self.get_parking_lot(lot_id)  # raises NotFoundError if the lot doesn't exist
        return self.activities.list_for_lot(lot_id, limit=limit)

    def list_all_activities(self, *, limit: int) -> list[ParkingActivity]:
        return self.activities.list_recent(limit=limit)


def get_parking_lot_usecase(db: Session = Depends(get_db)) -> ParkingLotUsecase:
    return ParkingLotUsecase(db)
