"""fix id defaults for door instance tables

Revision ID: 20260410_0046
Revises: 20260410_0045
Create Date: 2026-04-10 03:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260410_0046"
down_revision = "20260410_0045"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "sub_category_design_door_instances",
        "id",
        existing_type=sa.UUID(),
        server_default=sa.text("gen_random_uuid()"),
        existing_nullable=False,
    )
    op.alter_column(
        "order_design_door_instances",
        "id",
        existing_type=sa.UUID(),
        server_default=sa.text("gen_random_uuid()"),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "order_design_door_instances",
        "id",
        existing_type=sa.UUID(),
        server_default=None,
        existing_nullable=False,
    )
    op.alter_column(
        "sub_category_design_door_instances",
        "id",
        existing_type=sa.UUID(),
        server_default=None,
        existing_nullable=False,
    )
