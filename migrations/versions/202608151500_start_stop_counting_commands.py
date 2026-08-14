"""add "start_counting" / "stop_counting" to device_commands.command_type
(lets Admin tell an edge device to start/stop tallying entries, alongside
the existing "restart")

Revision ID: 202608151500
Revises: 202608151000
Create Date: 2026-08-15

"""
from alembic import op
import sqlalchemy as sa

revision = "202608151500"
down_revision = "202608151000"
branch_labels = None
depends_on = None

OLD_TYPES = ("restart",)
NEW_TYPES = ("restart", "start_counting", "stop_counting")


def upgrade() -> None:
    op.alter_column(
        "device_commands",
        "command_type",
        existing_type=sa.Enum(*OLD_TYPES, name="command_type"),
        type_=sa.Enum(*NEW_TYPES, name="command_type"),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM device_commands WHERE command_type IN ('start_counting', 'stop_counting')"
    )
    op.alter_column(
        "device_commands",
        "command_type",
        existing_type=sa.Enum(*NEW_TYPES, name="command_type"),
        type_=sa.Enum(*OLD_TYPES, name="command_type"),
        existing_nullable=False,
    )
