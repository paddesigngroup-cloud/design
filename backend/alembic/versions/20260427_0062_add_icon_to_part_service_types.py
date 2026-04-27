"""add icon to part service types

Revision ID: 20260427_0062
Revises: 20260426_0061
Create Date: 2026-04-27 11:20:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260427_0062"
down_revision = "20260426_0061"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("part_service_types", sa.Column("icon_path", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("part_service_types", "icon_path")
