"""add icon to part services

Revision ID: 20260427_0063
Revises: 20260427_0062
Create Date: 2026-04-27 11:45:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260427_0063"
down_revision = "20260427_0062"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("part_services", sa.Column("icon_path", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("part_services", "icon_path")
