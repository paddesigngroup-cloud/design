"""default part service type measurements to zero

Revision ID: 20260428_0066
Revises: 20260428_0065
Create Date: 2026-04-28 20:15:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260428_0066"
down_revision = "20260428_0065"
branch_labels = None
depends_on = None


MEASUREMENT_COLUMNS = (
    "axis_to_opposite_edge_distance",
    "axis_to_aligned_edge_distance",
    "working_diameter",
    "working_depth",
)


def upgrade() -> None:
    for column_name in MEASUREMENT_COLUMNS:
        op.execute(f"UPDATE part_service_types SET {column_name} = 0 WHERE {column_name} IS NULL")
        op.alter_column(
            "part_service_types",
            column_name,
            existing_type=sa.Float(),
            nullable=False,
            server_default="0",
        )


def downgrade() -> None:
    for column_name in MEASUREMENT_COLUMNS:
        op.alter_column(
            "part_service_types",
            column_name,
            existing_type=sa.Float(),
            nullable=True,
            server_default=None,
        )
