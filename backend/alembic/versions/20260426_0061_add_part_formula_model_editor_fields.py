"""add part formula model editor fields

Revision ID: 20260426_0061
Revises: 20260426_0060
Create Date: 2026-04-26 20:20:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260426_0061"
down_revision = "20260426_0060"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "part_formulas",
        sa.Column(
            "lw_frame_mapping",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "part_formulas",
        sa.Column(
            "part_model_side_services",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.execute(
        """
        UPDATE part_formulas
        SET
            lw_frame_mapping = COALESCE(
                lw_frame_mapping,
                jsonb_build_object(
                    'l_axis', 'horizontal',
                    'w_axis', 'vertical'
                )
            ),
            part_model_side_services = COALESCE(part_model_side_services, '[]'::jsonb)
        """
    )
    op.alter_column("part_formulas", "lw_frame_mapping", nullable=False)
    op.alter_column("part_formulas", "part_model_side_services", nullable=False)


def downgrade() -> None:
    op.drop_column("part_formulas", "part_model_side_services")
    op.drop_column("part_formulas", "lw_frame_mapping")
