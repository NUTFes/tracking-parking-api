"""add parking_lots.x_percent/y_percent (campus-map pin position, editable
from admin-web instead of the old hardcoded campusMapPins.ts frontend file)

Revision ID: 202608260001
Revises: 202608151600
Create Date: 2026-08-26

"""
from alembic import op
import sqlalchemy as sa

revision = "202608260001"
down_revision = "202608151600"
branch_labels = None
depends_on = None

# Backfill for the known demo lots (same values the old
# services/web/src/campusMapPins.ts hand-placed), so existing rows keep
# their current pin position instead of resetting to dead-center. Any other
# existing lot is left NULL — the map simply won't show a pin for it until
# it's dragged into place once in admin-web.
_KNOWN_POSITIONS = {
    "イチョウ通り": (4.8, 35.5),
    "RIセンター北": (63.8, 21.4),
    "講義棟西2": (72.5, 23.9),
    "講義棟西1": (70.0, 34.6),
    "講義棟北2": (90.8, 41.6),
    "体育館下": (29.5, 81.2),
    "地域防災実践研究センター下": (11.3, 85.3),
}


def upgrade() -> None:
    op.add_column("parking_lots", sa.Column("x_percent", sa.Float(), nullable=True))
    op.add_column("parking_lots", sa.Column("y_percent", sa.Float(), nullable=True))

    conn = op.get_bind()
    for name, (x, y) in _KNOWN_POSITIONS.items():
        conn.execute(
            sa.text("UPDATE parking_lots SET x_percent = :x, y_percent = :y WHERE name = :name"),
            {"x": x, "y": y, "name": name},
        )


def downgrade() -> None:
    op.drop_column("parking_lots", "y_percent")
    op.drop_column("parking_lots", "x_percent")
