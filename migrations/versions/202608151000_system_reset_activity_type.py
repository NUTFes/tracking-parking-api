"""add "system_reset" to parking_activities.activity_type (admin reset of
system_count, distinct from "reset" which targets current_count)

Revision ID: 202608151000
Revises: 202608150002
Create Date: 2026-08-15

"""
from alembic import op
import sqlalchemy as sa

revision = "202608151000"
down_revision = "202608150002"
branch_labels = None
depends_on = None

OLD_TYPES = ("entry", "exit", "manual_adjustment", "reset")
NEW_TYPES = ("entry", "exit", "manual_adjustment", "reset", "system_reset")


def upgrade() -> None:
    op.alter_column(
        "parking_activities",
        "activity_type",
        existing_type=sa.Enum(*OLD_TYPES, name="activity_type"),
        type_=sa.Enum(*NEW_TYPES, name="activity_type"),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.execute("UPDATE parking_activities SET activity_type = 'reset' WHERE activity_type = 'system_reset'")
    op.alter_column(
        "parking_activities",
        "activity_type",
        existing_type=sa.Enum(*NEW_TYPES, name="activity_type"),
        type_=sa.Enum(*OLD_TYPES, name="activity_type"),
        existing_nullable=False,
    )
