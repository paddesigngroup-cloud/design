"""add dimensions to part service types

Revision ID: 20260428_0064
Revises: 20260427_0063
Create Date: 2026-04-28 14:10:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260428_0064"
down_revision = "20260427_0063"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("part_service_types", sa.Column("axis_to_opposite_edge_distance", sa.Float(), nullable=True))
    op.add_column("part_service_types", sa.Column("axis_to_aligned_edge_distance", sa.Float(), nullable=True))
    op.add_column("part_service_types", sa.Column("working_diameter", sa.Float(), nullable=True))
    op.add_column("part_service_types", sa.Column("working_depth", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("part_service_types", "working_depth")
    op.drop_column("part_service_types", "working_diameter")
    op.drop_column("part_service_types", "axis_to_aligned_edge_distance")
    op.drop_column("part_service_types", "axis_to_opposite_edge_distance")
