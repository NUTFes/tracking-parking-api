from datetime import datetime

from sqlalchemy.orm import Session

from app.models.event import ParkingEvent


class ParkingEventRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        *,
        device_id: int,
        event_type: str,
        vehicle_track_id: str | None,
        detected_at: datetime,
        received_at: datetime,
    ) -> ParkingEvent:
        event = ParkingEvent(
            device_id=device_id,
            event_type=event_type,
            vehicle_track_id=vehicle_track_id,
            detected_at=detected_at,
            received_at=received_at,
        )
        self.db.add(event)
        return event

    def list_for_lot(
        self,
        lot_id: int,
        *,
        since: datetime | None,
        until: datetime | None,
        limit: int,
    ) -> list[ParkingEvent]:
        # parking_events has no parking_lot_id column of its own — it's reached
        # through the reporting device, so filter via that relationship.
        query = (
            self.db.query(ParkingEvent)
            .join(ParkingEvent.device)
            .filter(ParkingEvent.device.has(parking_lot_id=lot_id))
        )
        if since is not None:
            query = query.filter(ParkingEvent.detected_at >= since)
        if until is not None:
            query = query.filter(ParkingEvent.detected_at <= until)

        return query.order_by(ParkingEvent.detected_at.desc()).limit(limit).all()
