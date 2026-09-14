import logging
from datetime import datetime

from fastapi import Depends
from sqlalchemy.orm import Session

from app import database
from app.database import get_db
from app.models.device import Device
from app.models.event import ParkingEvent
from app.repositories.event_repository import ParkingEventRepository
from app.repositories.parking_activity_repository import ParkingActivityRepository
from app.repositories.parking_lot_repository import ParkingLotRepository
from app.utils import now_local, to_naive_local

logger = logging.getLogger("app")


class EventUsecase:
    def __init__(self, db: Session):
        self.db = db
        self.events = ParkingEventRepository(db)
        self.parking_lots = ParkingLotRepository(db)
        self.activities = ParkingActivityRepository(db)

    def enqueue_event(
        self,
        *,
        device: Device,
        event_type: str,
        vehicle_track_id: str | None,
        detected_at: datetime,
        request_id: str,
    ) -> tuple[ParkingEvent, bool]:
        """Persists the raw event immediately (cheap — no parking-lot row
        lock) and leaves applying it to the lot's system_count for
        process_event, run asynchronously as a FastAPI BackgroundTask right
        after the response is sent (see routers.events.create_event).
        request_id is a client-generated idempotency key: a device retrying
        the same POST /events call (e.g. after a timeout, unsure whether the
        first attempt landed) gets back the already-queued/processed event
        instead of double-counting. Returns (event, is_new) so the caller
        only schedules background processing for genuinely new requests."""
        existing = self.events.get_by_request_id(request_id)
        if existing is not None:
            return existing, False

        event = self.events.create(
            device_id=device.id,
            event_type=event_type,
            vehicle_track_id=vehicle_track_id,
            detected_at=to_naive_local(detected_at),
            received_at=now_local(),
            request_id=request_id,
        )
        self.db.commit()
        self.db.refresh(event)
        return event, True

    def process_event(self, event_id: int) -> None:
        """Applies a queued event's effect on its parking lot's
        device-reported occupancy count (system_count), row-locked via
        ParkingLotRepository.get_for_update so concurrent entries/exits from
        different devices at the same lot serialize instead of racing.
        Deliberately does NOT touch current_count — that field is reserved
        for manual counts (manager adjust / admin reset); see
        ParkingLot.system_count. Also appends a parking_activities row
        (actor_label=device_code), same as the old synchronous record_event
        used to do inline. No-ops if the event isn't pending (guards against
        being scheduled twice for one event)."""
        event = self.events.get(event_id)
        if event is None or event.status != "pending":
            return

        lot = self.parking_lots.get_for_update(event.device.parking_lot_id)
        if lot is not None:
            before = lot.system_count
            if event.event_type == "entry":
                lot.system_count += 1
            else:
                lot.system_count = max(0, lot.system_count - 1)
            self.activities.create(
                parking_lot_id=lot.id,
                activity_type=event.event_type,
                delta=lot.system_count - before,
                count_after=lot.system_count,
                actor_label=event.device.device_code,
                note=None,
            )
        event.status = "processed"
        self.db.commit()


def get_event_usecase(db: Session = Depends(get_db)) -> EventUsecase:
    return EventUsecase(db)


def process_queued_event(event_id: int) -> None:
    """Entry point for the BackgroundTask scheduled by POST /events. Opens
    its own DB session rather than reusing the request's: FastAPI tears down
    yield-dependencies (closing app.deps.get_db's session) before running
    background tasks, so the request-scoped session is already closed by the
    time this runs. Goes through the `database` module (not a plain
    `from app.database import SessionLocal`) so tests can monkeypatch
    database.SessionLocal to the test engine and have it take effect here too."""
    db = database.SessionLocal()
    try:
        EventUsecase(db).process_event(event_id)
    except Exception:
        db.rollback()
        logger.exception("failed to process queued parking event id=%s", event_id)
        event = db.get(ParkingEvent, event_id)
        if event is not None:
            event.status = "failed"
            db.commit()
    finally:
        db.close()
