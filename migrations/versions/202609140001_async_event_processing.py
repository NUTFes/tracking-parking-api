"""queue-based async processing for parking_events: request_id (client-
supplied UUID idempotency key, used to dedupe retried POST /events calls)
and status (pending/processed/failed, tracking whether the lot system_count
update queued for a background task has run yet)

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

    # Backfill: existing rows predate request_id/status and were always
    # applied to their lot synchronously in the old code path, so they're
    # all "processed" with a generated (never reused) request_id.
    conn = op.get_bind()
    conn.execute(sa.text("UPDATE parking_events SET request_id = UUID() WHERE request_id IS NULL"))

    op.alter_column("parking_events", "request_id", existing_type=sa.String(36), nullable=False)
    op.create_unique_constraint("uq_parking_events_request_id", "parking_events", ["request_id"])
    # Drop the server default now that backfill is done — the app always sets
    # status explicitly on insert (ParkingEventRepository.create relies on
    # the model's default="pending"), same convention as device_commands.status.
    op.alter_column("parking_events", "status", server_default=None)


def downgrade() -> None:
    op.drop_constraint("uq_parking_events_request_id", "parking_events", type_="unique")
    op.drop_column("parking_events", "status")
    op.drop_column("parking_events", "request_id")
