import logging
from datetime import datetime, timedelta

from fastapi import Depends
from sqlalchemy.orm import Session

from app import database
from app.config import settings
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
        used to do inline.

        Callable both for a single freshly-queued event (process_queued_event,
        status="pending") and for a stale one being retried by
        sweep_stale_events (status="pending" or "failed") — anything else
        (already "processed", or not found) is a no-op, guarding against
        being run twice for one event. Any exception during processing is
        caught here (not left to the caller) so one bad event can't abort a
        whole sweep batch: it's logged, the failed transaction is rolled
        back, and the event is marked "failed" in a fresh mini-transaction —
        left for a later sweep_stale_events pass to retry, rather than
        silently dropping the lot-count update it represents."""
        event = self.events.get(event_id)
        if event is None or event.status not in ("pending", "failed"):
            return

        try:
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
        except Exception:
            self.db.rollback()
            logger.exception("failed to process queued parking event id=%s", event_id)
            event = self.events.get(event_id)
            if event is not None:
                event.status = "failed"
                self.db.commit()

    def sweep_stale_events(self) -> int:
        """Recovers parking_events stuck "pending"/"failed" for longer than
        settings.event_queue_stale_seconds — either process_event's
        try/except caught an error (and nothing retries a "failed" event on
        its own), or the API process was killed/restarted between
        enqueue_event's commit and its BackgroundTask actually running
        (BackgroundTasks are in-memory only, not a durable queue, so that
        window is a real gap). The staleness cutoff keeps this from racing
        genuinely in-flight processing, which normally finishes in well
        under a second. Called periodically by the sweep loop started in
        main.py's lifespan. Returns how many were reprocessed, for logging."""
        cutoff = now_local() - timedelta(seconds=settings.event_queue_stale_seconds)
        stale = self.events.list_stale_queued(before=cutoff)
        for event in stale:
            self.process_event(event.id)
        return len(stale)


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
    finally:
        db.close()


def sweep_stale_queued_events() -> int:
    """Sync entry point for the periodic sweep loop (see main.py's
    lifespan) — opens its own session for the same reason
    process_queued_event does."""
    db = database.SessionLocal()
    try:
        return EventUsecase(db).sweep_stale_events()
    finally:
        db.close()
