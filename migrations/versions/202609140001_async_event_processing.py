"""queue-based async processing for parking_events: request_id (client-
supplied UUID idempotency key, used to dedupe retried POST /events calls),
status (pending/processed/failed, tracking whether the lot system_count
update queued for a background task has run yet), and attempts (how many
times processing has failed, so the periodic sweep can stop retrying a
permanently-broken event instead of retrying it forever)

Revision ID: 202609140001
Revises: 202608260001
Create Date: 2026-09-14

"""
from alembic import op
import sqlalchemy as sa

revision = "202609140001"
down_revision = "202608260001"
branch_labels = None
depends_on = None

EVENT_STATUSES = ("pending", "processed", "failed")


def upgrade() -> None:
    op.add_column("parking_events", sa.Column("request_id", sa.String(36), nullable=True))
    op.add_column(
        "parking_events",
        sa.Column(
            "status",
            sa.Enum(*EVENT_STATUSES, name="parking_event_status"),
            nullable=False,
            server_default="processed",
        ),
    )
    op.add_column(
        "parking_events",
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
    )

    # Backfill: existing rows predate request_id/status and were always
    # applied to their lot synchronously in the old code path, so they're
    # all "processed" with a generated (never reused) request_id.
    conn = op.get_bind()
    conn.execute(sa.text("UPDATE parking_events SET request_id = UUID() WHERE request_id IS NULL"))

    op.alter_column("parking_events", "request_id", existing_type=sa.String(36), nullable=False)
    # Created as a unique index (not a separately-named constraint) to match
    # this codebase's convention for every other unique lookup column
    # (device_code, api_key_hash, ...) — see 202608140001_initial_schema.py —
    # and the ORM model's own index=True on request_id.
    op.create_index("ix_parking_events_request_id", "parking_events", ["request_id"], unique=True)
    # Supports EventUsecase.sweep_stale_events / list_stale_queued's
    # WHERE status IN (...) AND received_at < :before, run on every sweep
    # tick — without this, that query is a full table scan of parking_events.
    op.create_index("ix_parking_events_status_received_at", "parking_events", ["status", "received_at"])
    # Drop the server defaults now that backfill is done — the app always
    # sets status/attempts explicitly on insert (ParkingEventRepository.create
    # relies on the model's defaults), same convention as device_commands.status.
    op.alter_column("parking_events", "status", server_default=None)
    op.alter_column("parking_events", "attempts", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_parking_events_status_received_at", table_name="parking_events")
    op.drop_index("ix_parking_events_request_id", table_name="parking_events")
    op.drop_column("parking_events", "attempts")
    op.drop_column("parking_events", "status")
    op.drop_column("parking_events", "request_id")
