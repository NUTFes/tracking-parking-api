"""admin_refresh_tokens.user_id: add ON DELETE CASCADE

Without this, deleting an admin_users row that still has any refresh token
rows (even revoked/expired ones — the FK doesn't care) fails with a MySQL
foreign-key constraint error, which FastAPI/Starlette turns into an
unhandled 500 that skips CORSMiddleware entirely — the browser then reports
it as a generic "Failed to fetch", not a readable error. A deleted admin
account should lose its sessions anyway, so cascading here is also the
correct security behavior, not just a workaround.

Revision ID: 202608151600
Revises: 202608151500
Create Date: 2026-08-15

"""
from alembic import op

revision = "202608151600"
down_revision = "202608151500"
branch_labels = None
depends_on = None

CONSTRAINT_NAME = "admin_refresh_tokens_ibfk_1"


def upgrade() -> None:
    op.drop_constraint(CONSTRAINT_NAME, "admin_refresh_tokens", type_="foreignkey")
    op.create_foreign_key(
        CONSTRAINT_NAME,
        "admin_refresh_tokens",
        "admin_users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(CONSTRAINT_NAME, "admin_refresh_tokens", type_="foreignkey")
    op.create_foreign_key(
        CONSTRAINT_NAME,
        "admin_refresh_tokens",
        "admin_users",
        ["user_id"],
        ["id"],
    )
