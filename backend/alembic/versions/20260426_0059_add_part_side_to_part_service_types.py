"""add part side to part service types

Revision ID: 20260426_0059
Revises: 20260426_0058
Create Date: 2026-04-26 14:20:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260426_0059"
down_revision = "20260426_0058"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "part_service_types",
        sa.Column("part_side", sa.String(length=16), server_default=sa.text("'front'"), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("part_service_types", "part_side")
