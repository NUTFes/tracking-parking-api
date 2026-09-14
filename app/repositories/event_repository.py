from datetime import datetime

from sqlalchemy.orm import Session, joinedload

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
        request_id: str,
    ) -> ParkingEvent:
        event = ParkingEvent(
            device_id=device_id,
            event_type=event_type,
            vehicle_track_id=vehicle_track_id,
            detected_at=detected_at,
            received_at=received_at,
            request_id=request_id,
        )
        self.db.add(event)
        return event

    def get(self, event_id: int) -> ParkingEvent | None:
        return self.db.get(ParkingEvent, event_id)

    def get_for_update(self, event_id: int) -> ParkingEvent | None:
        """Row-locks the event so two concurrent processors of the same
        event_id (e.g. its original BackgroundTask still running past
        event_queue_stale_seconds, racing a sweep pass that picked up the
        same still-"pending" row) serialize instead of both passing the
        status guard and double-applying the lot update — see
        EventUsecase.process_event."""
        return self.db.query(ParkingEvent).filter(ParkingEvent.id == event_id).with_for_update().first()

    def get_by_request_id(self, request_id: str) -> ParkingEvent | None:
        return self.db.query(ParkingEvent).filter(ParkingEvent.request_id == request_id).first()

    def list_stale_queued(self, *, before: datetime, limit: int, max_attempts: int) -> list[ParkingEvent]:
        """Events still "pending" (never processed — likely an orphaned
        BackgroundTask, see EventUsecase.sweep_stale_events) or "failed"
        (processing raised) whose received_at predates `before`, excluding
        ones that have already failed max_attempts times (those are left for
        manual investigation instead of being retried forever). Ordered
        oldest-first and capped at `limit` so one sweep tick can't run
        unbounded against a large backlog. Eager-loads `device` since the
        sweep can span many events from few devices — avoids an N+1 query
        in EventUsecase.process_event's per-event device lookup."""
        return (
            self.db.query(ParkingEvent)
            .options(joinedload(ParkingEvent.device))
            .filter(
                ParkingEvent.status.in_(("pending", "failed")),
                ParkingEvent.received_at < before,
                ParkingEvent.attempts < max_attempts,
            )
            .order_by(ParkingEvent.received_at)
            .limit(limit)
            .all()
        )

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
