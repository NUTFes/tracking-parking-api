"""add parking_lots.system_count (device-reported count, separate from
current_count which becomes manual-only)

Revision ID: 202608150002
Revises: 202608150001
Create Date: 2026-08-15

"""
from alembic import op
import sqlalchemy as sa

revision = "202608150002"
down_revision = "202608150001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "parking_lots", sa.Column("system_count", sa.Integer(), nullable=False, server_default="0")
    )
    # Backfill: seed system_count from the existing current_count so
    # device-linked lots start from today's real occupancy rather than 0.
    op.execute("UPDATE parking_lots SET system_count = current_count")
    op.alter_column("parking_lots", "system_count", server_default=None)


def downgrade() -> None:
    op.drop_column("parking_lots", "system_count")
