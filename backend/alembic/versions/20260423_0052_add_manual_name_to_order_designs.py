"""add manual name to order designs

Revision ID: 20260423_0052
Revises: 20260418_0051
Create Date: 2026-04-23 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260423_0052"
down_revision = "20260418_0051"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("order_designs", sa.Column("manual_name", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("order_designs", "manual_name")
