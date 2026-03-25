"""add is_internal to part kinds

Revision ID: 20260325_0027
Revises: 20260325_0026
Create Date: 2026-03-25 19:10:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260325_0027"
down_revision = "20260324_0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "part_kinds",
        sa.Column("is_internal", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.execute(
        """
        UPDATE part_kinds
        SET is_internal = true
        WHERE part_kind_code IN ('shelf', 'shelve', 'drawer');
        """
    )


def downgrade() -> None:
    op.drop_column("part_kinds", "is_internal")
