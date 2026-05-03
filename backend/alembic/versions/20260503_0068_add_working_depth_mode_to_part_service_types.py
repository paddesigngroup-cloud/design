"""add working depth mode to part service types

Revision ID: 20260503_0068
Revises: 20260502_0067
Create Date: 2026-05-03 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260503_0068"
down_revision = "20260502_0067"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "part_service_types",
        sa.Column("working_depth_mode", sa.String(length=16), nullable=False, server_default="fixed"),
    )
    op.add_column(
        "part_service_types",
        sa.Column("working_depth_end_offset", sa.Float(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("part_service_types", "working_depth_end_offset")
    op.drop_column("part_service_types", "working_depth_mode")
