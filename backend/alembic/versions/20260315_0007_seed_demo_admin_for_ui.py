"""seed demo admin for ui

Revision ID: 20260315_0007
Revises: 20260315_0006
Create Date: 2026-03-15 03:00:00
"""
from __future__ import annotations

from alembic import op


revision = "20260315_0007"
down_revision = "20260315_0006"
branch_labels = None
depends_on = None


DEMO_ADMIN_ID = "00000000-0000-0000-0000-000000000001"


def upgrade() -> None:
    op.execute(
        f"""
        INSERT INTO admins (id, email, full_name, is_active)
        VALUES ('{DEMO_ADMIN_ID}', 'admin-demo@designkp.local', 'Admin Demo', true)
        ON CONFLICT (email) DO NOTHING;
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM admins WHERE email = 'admin-demo@designkp.local';")
