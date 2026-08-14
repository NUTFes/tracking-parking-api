"""google sso for admin (drop password auth), add parking_activities

Revision ID: 202608150001
Revises: 202608141900
Create Date: 2026-08-15

"""
from alembic import op
import sqlalchemy as sa

revision = "202608150001"
down_revision = "202608141900"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # admin_users: password auth -> Google-account allow-list. Existing rows
    # (if any) get a placeholder email so the NOT NULL backfill succeeds; real
    # allow-list entries are re-added via scripts/manage_admin_allowlist.py.
    op.add_column("admin_users", sa.Column("email", sa.String(length=255), nullable=True))
    op.execute("UPDATE admin_users SET email = CONCAT(username, '@migrated.invalid')")
    op.alter_column("admin_users", "email", existing_type=sa.String(length=255), nullable=False)
    op.create_unique_constraint("uq_admin_users_email", "admin_users", ["email"])
    op.create_index("ix_admin_users_email", "admin_users", ["email"])
    op.drop_index("ix_admin_users_username", table_name="admin_users")
    op.drop_column("admin_users", "username")
    op.drop_column("admin_users", "password_hash")

    op.create_table(
        "parking_activities",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "parking_lot_id", sa.Integer(), sa.ForeignKey("parking_lots.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "activity_type",
            sa.Enum("entry", "exit", "manual_adjustment", "reset", name="activity_type"),
            nullable=False,
        ),
        sa.Column("delta", sa.Integer(), nullable=False),
        sa.Column("count_after", sa.Integer(), nullable=False),
        sa.Column("actor_label", sa.String(length=255), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_parking_activities_parking_lot_id", "parking_activities", ["parking_lot_id"])


def downgrade() -> None:
    op.drop_index("ix_parking_activities_parking_lot_id", table_name="parking_activities")
    op.drop_table("parking_activities")

    op.add_column("admin_users", sa.Column("password_hash", sa.String(length=255), nullable=True))
    op.add_column("admin_users", sa.Column("username", sa.String(length=64), nullable=True))
    op.execute("UPDATE admin_users SET username = email, password_hash = ''")
    op.alter_column("admin_users", "username", existing_type=sa.String(length=64), nullable=False)
    op.alter_column("admin_users", "password_hash", existing_type=sa.String(length=255), nullable=False)
    op.create_index("ix_admin_users_username", "admin_users", ["username"], unique=True)
    op.drop_index("ix_admin_users_email", table_name="admin_users")
    op.drop_constraint("uq_admin_users_email", "admin_users", type_="unique")
    op.drop_column("admin_users", "email")
