"""add orders list index for admin query path

Revision ID: 20260425_0055
Revises: 20260425_0054
Create Date: 2026-04-25 17:10:00
"""

from __future__ import annotations

from alembic import op


revision = "20260425_0055"
down_revision = "20260425_0054"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_orders_admin_submitted_number_live "
            "ON orders (admin_id, submitted_at DESC, order_number ASC) "
            "WHERE deleted_at IS NULL"
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_orders_admin_submitted_number_live")
