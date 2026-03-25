"""add icon to internal part groups

Revision ID: 20260325_0029
Revises: 20260325_0028
Create Date: 2026-03-25 20:25:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260325_0029"
down_revision = "20260325_0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("internal_part_groups", sa.Column("icon_path", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("internal_part_groups", "icon_path")
