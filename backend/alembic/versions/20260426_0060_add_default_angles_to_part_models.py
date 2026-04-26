"""add default angles to part models

Revision ID: 20260426_0060
Revises: 20260426_0059
Create Date: 2026-04-26 18:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260426_0060"
down_revision = "20260426_0059"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "part_models",
        sa.Column(
            "default_angles",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.execute(
        """
        UPDATE part_models
        SET default_angles = (
            SELECT jsonb_agg(
                jsonb_build_object(
                    'index',
                    gs.i,
                    'angle_deg',
                    CASE
                        WHEN gs.i = part_models.side_count - 1 THEN
                            ROUND(
                                part_models.interior_angle_sum::numeric
                                - (ROUND((part_models.interior_angle_sum::numeric / part_models.side_count::numeric), 6) * (part_models.side_count - 1)),
                                6
                            )
                        ELSE ROUND((part_models.interior_angle_sum::numeric / part_models.side_count::numeric), 6)
                    END
                )
                ORDER BY gs.i
            )
            FROM generate_series(0, part_models.side_count - 1) AS gs(i)
        )
        WHERE default_angles IS NULL;
        """
    )
    op.alter_column("part_models", "default_angles", nullable=False)


def downgrade() -> None:
    op.drop_column("part_models", "default_angles")
