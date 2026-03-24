"""expand orders for v1 and seed demo user

Revision ID: 20260325_0024
Revises: 20260324_0023
Create Date: 2026-03-25 00:20:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260325_0024"
down_revision = "20260324_0023"
branch_labels = None
depends_on = None


DEMO_ADMIN_ID = "00000000-0000-0000-0000-000000000001"
DEMO_USER_ID = "00000000-0000-0000-0000-000000000101"
DEMO_USER_EMAIL = "user-demo@designkp.local"


def upgrade() -> None:
    op.execute(
        f"""
        INSERT INTO users (id, admin_id, email, full_name, is_active)
        VALUES ('{DEMO_USER_ID}', '{DEMO_ADMIN_ID}', '{DEMO_USER_EMAIL}', 'کاربر دمو', true)
        ON CONFLICT (email) DO NOTHING;
        """
    )

    op.add_column("orders", sa.Column("order_name", sa.String(length=255), nullable=True))
    op.add_column("orders", sa.Column("status", sa.String(length=32), nullable=False, server_default=sa.text("'draft'")))
    op.add_column("orders", sa.Column("notes", sa.Text(), nullable=True))

    op.execute("UPDATE orders SET order_name = COALESCE(NULLIF(trim(order_number), ''), 'سفارش بدون نام')")
    op.alter_column("orders", "order_name", existing_type=sa.String(length=255), nullable=False)

    op.drop_constraint(op.f("uq_orders_order_number"), "orders", type_="unique")
    op.create_unique_constraint("uq_orders_admin_order_number", "orders", ["admin_id", "order_number"])

    op.alter_column("orders", "status", server_default=None)


def downgrade() -> None:
    op.drop_constraint("uq_orders_admin_order_number", "orders", type_="unique")
    op.create_unique_constraint(op.f("uq_orders_order_number"), "orders", ["order_number"])

    op.drop_column("orders", "notes")
    op.drop_column("orders", "status")
    op.drop_column("orders", "order_name")

    op.execute(
        f"""
        DELETE FROM users AS u
        WHERE u.email = '{DEMO_USER_EMAIL}'
          AND NOT EXISTS (SELECT 1 FROM orders AS o WHERE o.user_id = u.id);
        """
    )
