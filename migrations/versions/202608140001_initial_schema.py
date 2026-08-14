"""initial schema

Revision ID: 202608140001
Revises:
Create Date: 2026-08-14

"""
from alembic import op
import sqlalchemy as sa

revision = "202608140001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "parking_lots",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("capacity", sa.Integer(), nullable=True),
        sa.Column("current_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "devices",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("device_code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("parking_lot_id", sa.Integer(), sa.ForeignKey("parking_lots.id"), nullable=False),
        sa.Column("api_key_hash", sa.String(length=64), nullable=False),
        sa.Column("last_status", sa.String(length=32), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_devices_device_code", "devices", ["device_code"], unique=True)
    op.create_index("ix_devices_api_key_hash", "devices", ["api_key_hash"], unique=True)

    op.create_table(
        "parking_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("device_id", sa.Integer(), sa.ForeignKey("devices.id"), nullable=False),
        sa.Column("event_type", sa.Enum("entry", "exit", name="event_type"), nullable=False),
        sa.Column("vehicle_track_id", sa.String(length=64), nullable=True),
        sa.Column("detected_at", sa.DateTime(), nullable=False),
        sa.Column("received_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_parking_events_device_id", "parking_events", ["device_id"])

    op.create_table(
        "device_commands",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("device_id", sa.Integer(), sa.ForeignKey("devices.id"), nullable=False),
        sa.Column("command_type", sa.Enum("restart", name="command_type"), nullable=False),
        sa.Column(
            "status",
            sa.Enum("pending", "delivered", "completed", "failed", name="command_status"),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("requested_by", sa.String(length=255), nullable=True),
        sa.Column("result_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("delivered_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_device_commands_device_id", "device_commands", ["device_id"])


def downgrade() -> None:
    op.drop_table("device_commands")
    op.drop_index("ix_parking_events_device_id", table_name="parking_events")
    op.drop_table("parking_events")
    op.drop_index("ix_devices_api_key_hash", table_name="devices")
    op.drop_index("ix_devices_device_code", table_name="devices")
    op.drop_table("devices")
    op.drop_table("parking_lots")
