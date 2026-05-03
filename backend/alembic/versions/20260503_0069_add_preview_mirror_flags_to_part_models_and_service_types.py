"""add preview mirror flags to part models and service types

Revision ID: 20260503_0069
Revises: 20260503_0068
Create Date: 2026-05-03
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260503_0069"
down_revision = "20260503_0068"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "part_models",
        sa.Column("preview_mirror_x", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "part_models",
        sa.Column("preview_mirror_y", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "part_service_types",
        sa.Column("preview_mirror_x", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "part_service_types",
        sa.Column("preview_mirror_y", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )


def downgrade() -> None:
    op.drop_column("part_service_types", "preview_mirror_y")
    op.drop_column("part_service_types", "preview_mirror_x")
    op.drop_column("part_models", "preview_mirror_y")
    op.drop_column("part_models", "preview_mirror_x")
