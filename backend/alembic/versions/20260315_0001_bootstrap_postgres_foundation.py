"""bootstrap postgres foundation

Revision ID: 20260315_0001
Revises:
Create Date: 2026-03-15 00:00:00
"""
from __future__ import annotations

from alembic import op


revision = "20260315_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto";')
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.set_row_updated_at()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            NEW.updated_at = timezone('utc', now());
            RETURN NEW;
        END;
        $$;
        """
    )


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS public.set_row_updated_at();")
    op.execute('DROP EXTENSION IF EXISTS "pgcrypto";')
