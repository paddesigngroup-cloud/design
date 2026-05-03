"""add is_common to part service types

Revision ID: 20260503_0071
Revises: 20260503_0070
Create Date: 2026-05-03 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260503_0071"
down_revision = "20260503_0070"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "part_service_types",
        sa.Column("is_common", sa.Boolean(), nullable=False, server_default="false"),
    )


def downgrade() -> None:
    op.drop_column("part_service_types", "is_common")
