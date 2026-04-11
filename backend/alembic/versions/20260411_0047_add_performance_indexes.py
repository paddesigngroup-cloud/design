"""add performance indexes for hot list and lookup paths

Revision ID: 20260411_0047
Revises: 20260410_0046
Create Date: 2026-04-11 20:00:00
"""

from __future__ import annotations

from alembic import op


revision = "20260411_0047"
down_revision = "20260410_0046"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_orders_admin_deleted_submitted",
        "orders",
        ["admin_id", "deleted_at", "submitted_at"],
        unique=False,
    )
    op.create_index(
        "ix_order_designs_order_deleted_sort_instance",
        "order_designs",
        ["order_id", "deleted_at", "sort_order", "instance_code"],
        unique=False,
    )
    op.create_index(
        "ix_order_drawings_order_deleted",
        "order_drawings",
        ["order_id", "deleted_at"],
        unique=False,
    )
    op.create_index(
        "ix_users_admin_deleted",
        "users",
        ["admin_id", "deleted_at"],
        unique=False,
    )
    op.create_index(
        "ix_sub_category_designs_admin_deleted_sub_category",
        "sub_category_designs",
        ["admin_id", "deleted_at", "sub_category_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_sub_category_designs_admin_deleted_sub_category", table_name="sub_category_designs")
    op.drop_index("ix_users_admin_deleted", table_name="users")
    op.drop_index("ix_order_drawings_order_deleted", table_name="order_drawings")
    op.drop_index("ix_order_designs_order_deleted_sort_instance", table_name="order_designs")
    op.drop_index("ix_orders_admin_deleted_submitted", table_name="orders")
