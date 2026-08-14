"""admin auth (users + refresh tokens)

Revision ID: 202608141200
Revises: 202608140001
Create Date: 2026-08-14

"""
from alembic import op
import sqlalchemy as sa

revision = "202608141200"
down_revision = "202608140001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "admin_users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_admin_users_username", "admin_users", ["username"], unique=True)

    op.create_table(
        "admin_refresh_tokens",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("admin_users.id"), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_admin_refresh_tokens_user_id", "admin_refresh_tokens", ["user_id"])
    op.create_index(
        "ix_admin_refresh_tokens_token_hash", "admin_refresh_tokens", ["token_hash"], unique=True
    )


def downgrade() -> None:
    op.drop_index("ix_admin_refresh_tokens_token_hash", table_name="admin_refresh_tokens")
    op.drop_index("ix_admin_refresh_tokens_user_id", table_name="admin_refresh_tokens")
    op.drop_table("admin_refresh_tokens")
    op.drop_index("ix_admin_users_username", table_name="admin_users")
    op.drop_table("admin_users")
