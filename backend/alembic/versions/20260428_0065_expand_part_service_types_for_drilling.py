"""expand part service types for drilling

Revision ID: 20260428_0065
Revises: 20260428_0064
Create Date: 2026-04-28 16:40:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "20260428_0065"
down_revision = "20260428_0064"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("part_service_types", sa.Column("has_subtraction", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("part_service_types", sa.Column("service_location", sa.String(length=16), nullable=True))
    op.add_column("part_service_types", sa.Column("drill_pattern", sa.String(length=16), nullable=True))
    op.add_column("part_service_types", sa.Column("subtraction_shape", sa.String(length=16), nullable=True))
    op.add_column("part_service_types", sa.Column("shape_angles", postgresql.JSONB(astext_type=sa.Text()), nullable=True))

    op.execute(
        """
        UPDATE part_service_types
        SET service_location = CASE
            WHEN lower(coalesce(part_side, 'front')) = 'back' THEN 'back'
            ELSE 'front'
        END
        """
    )
    op.drop_column("part_service_types", "part_side")


def downgrade() -> None:
    op.add_column(
        "part_service_types",
        sa.Column("part_side", sa.String(length=16), nullable=False, server_default="front"),
    )
    op.execute(
        """
        UPDATE part_service_types
        SET part_side = CASE
            WHEN lower(coalesce(service_location, 'front')) = 'back' THEN 'back'
            ELSE 'front'
        END
        """
    )
    op.drop_column("part_service_types", "shape_angles")
    op.drop_column("part_service_types", "subtraction_shape")
    op.drop_column("part_service_types", "drill_pattern")
    op.drop_column("part_service_types", "service_location")
    op.drop_column("part_service_types", "has_subtraction")
