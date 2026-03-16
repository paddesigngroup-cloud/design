"""add input mode to sub category param defaults

Revision ID: 20260316_0017
Revises: 20260316_0016
Create Date: 2026-03-16 07:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260316_0017"
down_revision = "20260316_0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sub_category_param_defaults",
        sa.Column("input_mode", sa.String(length=16), nullable=False, server_default="value"),
    )


def downgrade() -> None:
    op.drop_column("sub_category_param_defaults", "input_mode")
