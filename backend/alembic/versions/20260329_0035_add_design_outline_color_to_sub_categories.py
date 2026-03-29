"""add design outline color to sub categories

Revision ID: 20260329_0035
Revises: 20260329_0034
Create Date: 2026-03-29 18:05:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260329_0035"
down_revision = "20260329_0034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sub_categories",
        sa.Column("design_outline_color", sa.String(length=7), nullable=False, server_default="#7A4A2B"),
    )


def downgrade() -> None:
    op.drop_column("sub_categories", "design_outline_color")
