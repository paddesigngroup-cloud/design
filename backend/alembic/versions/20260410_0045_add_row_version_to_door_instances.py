"""add row_version to door instance tables

Revision ID: 20260410_0045
Revises: 20260409_0044
Create Date: 2026-04-10 00:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260410_0045"
down_revision = "20260409_0044"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sub_category_design_door_instances",
        sa.Column("row_version", sa.Integer(), nullable=False, server_default=sa.text("1")),
    )
    op.add_column(
        "order_design_door_instances",
        sa.Column("row_version", sa.Integer(), nullable=False, server_default=sa.text("1")),
    )


def downgrade() -> None:
    op.drop_column("order_design_door_instances", "row_version")
    op.drop_column("sub_category_design_door_instances", "row_version")
