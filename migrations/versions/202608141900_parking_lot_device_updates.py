"""drop parking_lots.location, require capacity, cascade device deletes

Revision ID: 202608141900
Revises: 202608141200
Create Date: 2026-08-14

"""
from alembic import op
import sqlalchemy as sa

revision = "202608141900"
down_revision = "202608141200"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE parking_lots SET capacity = 0 WHERE capacity IS NULL")
    op.alter_column("parking_lots", "capacity", existing_type=sa.Integer(), nullable=False)
    op.drop_column("parking_lots", "location")

    op.drop_constraint("device_commands_ibfk_1", "device_commands", type_="foreignkey")
    op.create_foreign_key(
        "device_commands_ibfk_1", "device_commands", "devices", ["device_id"], ["id"], ondelete="CASCADE"
    )

    op.drop_constraint("parking_events_ibfk_1", "parking_events", type_="foreignkey")
    op.create_foreign_key(
        "parking_events_ibfk_1", "parking_events", "devices", ["device_id"], ["id"], ondelete="CASCADE"
    )


def downgrade() -> None:
    op.drop_constraint("parking_events_ibfk_1", "parking_events", type_="foreignkey")
    op.create_foreign_key("parking_events_ibfk_1", "parking_events", "devices", ["device_id"], ["id"])

    op.drop_constraint("device_commands_ibfk_1", "device_commands", type_="foreignkey")
    op.create_foreign_key("device_commands_ibfk_1", "device_commands", "devices", ["device_id"], ["id"])

    op.add_column("parking_lots", sa.Column("location", sa.String(length=255), nullable=True))
    op.alter_column("parking_lots", "capacity", existing_type=sa.Integer(), nullable=True)
