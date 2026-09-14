import logging
from datetime import datetime, timedelta

from fastapi import Depends
from sqlalchemy.exc import IntegrityError
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
    ) -> ParkingEvent:
        """Persists the raw event immediately (cheap — no parking-lot row
        lock) and leaves applying it to the lot's system_count for
        process_event, run asynchronously as a FastAPI BackgroundTask right
        after the response is sent (see routers.events.create_event, which
        unconditionally (re)schedules it — process_event's own status guard
        makes that safe even for an already-queued/processed retry).
        request_id is a client-generated idempotency key: a device retrying
        the same POST /events call (e.g. after a timeout, unsure whether the
        first attempt landed) gets back the already-queued/processed event
        instead of double-counting."""
        existing = self.events.get_by_request_id(request_id)
        if existing is not None:
            return existing

        event = self.events.create(
            device_id=device.id,
            event_type=event_type,
            vehicle_track_id=vehicle_track_id,
            detected_at=to_naive_local(detected_at),
            received_at=now_local(),
            request_id=request_id,
        )
        try:
            self.db.commit()
        except IntegrityError:
            # Lost a race with a concurrent retry using the same
            # request_id: both callers saw existing=None above, and the
            # other one's commit landed first. Fall back to its row instead
            # of surfacing a raw 500 to a client that's just retrying safely
            # (the exact scenario request_id was added to support).
            self.db.rollback()
            existing = self.events.get_by_request_id(request_id)
            if existing is not None:
                return existing
            raise
        self.db.refresh(event)
        return event

    def process_event(self, event_id: int) -> bool:
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
        sweep_stale_events (status="pending" or "failed"). The event itself
        is row-locked first (get_for_update) — this is what actually
        prevents double-processing: if this same event_id is already being
        processed elsewhere (e.g. the original BackgroundTask is still
        running past event_queue_stale_seconds, racing a sweep pass that
        picked up the same still-"pending" row, possibly on a different
        process/replica), the second caller blocks on this lock and, once
        unblocked, sees the already-"processed" status and no-ops instead of
        re-applying the lot update. Anything else not "pending"/"failed"
        (already "processed", or not found) is likewise a no-op.

        Any exception during processing is caught here (not left to the
        caller) so one bad event can't abort a whole sweep batch: it's
        logged, the failed transaction is rolled back, and the event is
        marked "failed" (with its attempts counter incremented) in a fresh
        mini-transaction — left for a later sweep_stale_events pass to
        retry (up to event_queue_max_attempts times), rather than silently
        dropping the lot-count update it represents. That recovery step is
        itself guarded so a second failure there (e.g. the same transient DB
        error) can't escape as an unhandled exception either.

        Returns True if the event is no longer stuck afterward — applied
        successfully just now, or found already handled by someone else —
        and False if this attempt itself failed and the event remains
        retryable. sweep_stale_events uses this to report how many events it
        actually recovered, not merely attempted."""
        event = self.events.get_for_update(event_id)
        if event is None or event.status not in ("pending", "failed"):
            return True

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
            return True
        except Exception:
            self.db.rollback()
            logger.exception("failed to process queued parking event id=%s", event_id)
            try:
                event.attempts += 1
                event.status = "failed"
                if event.attempts >= settings.event_queue_max_attempts:
                    logger.error(
                        "parking event id=%s has failed %d times and will no longer be retried by the sweep",
                        event_id,
                        event.attempts,
                    )
                self.db.commit()
            except Exception:
                self.db.rollback()
                logger.exception("failed to mark parking event id=%s as failed after a processing error", event_id)
            return False

    def sweep_stale_events(self) -> int:
        """Recovers parking_events stuck "pending"/"failed" for longer than
        settings.event_queue_stale_seconds — either process_event's
        try/except caught an error (and nothing retries a "failed" event on
        its own, short of event_queue_max_attempts), or the API process was
        killed/restarted between enqueue_event's commit and its
        BackgroundTask actually running (BackgroundTasks are in-memory only,
        not a durable queue, so that window is a real gap). The staleness
        cutoff keeps this from racing genuinely in-flight processing, which
        normally finishes in well under a second. Called periodically by the
        sweep loop started in main.py's lifespan. Returns how many were
        actually recovered (not merely attempted) — an event that fails
        again and gets re-marked "failed" doesn't count, so a
        permanently-broken event isn't logged as "recovered" every pass."""
        cutoff = now_local() - timedelta(seconds=settings.event_queue_stale_seconds)
        stale = self.events.list_stale_queued(
            before=cutoff,
            limit=settings.event_queue_sweep_batch_size,
            max_attempts=settings.event_queue_max_attempts,
        )
        return sum(1 for event in stale if self.process_event(event.id))


def get_event_usecase(db: Session = Depends(get_db)) -> EventUsecase:
    return EventUsecase(db)


def process_queued_event(event_id: int) -> None:
    """Entry point for the BackgroundTask scheduled by POST /events. Opens
    its own DB session rather than reusing the request's: FastAPI tears down
    yield-dependencies (closing app.deps.get_db's session) before running
    background tasks, so the request-scoped session is already closed by the
    time this runs — see database.session_scope."""
    with database.session_scope() as db:
        EventUsecase(db).process_event(event_id)


def sweep_stale_queued_events() -> int:
    """Sync entry point for the periodic sweep loop (see main.py's
    lifespan) — opens its own session for the same reason
    process_queued_event does."""
    with database.session_scope() as db:
        return EventUsecase(db).sweep_stale_events()
