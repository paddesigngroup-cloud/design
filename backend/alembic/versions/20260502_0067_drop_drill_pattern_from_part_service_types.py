"""drop drill pattern from part service types

Revision ID: 20260502_0067
Revises: 20260428_0066
Create Date: 2026-05-02 20:30:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260502_0067"
down_revision = "20260428_0066"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("part_service_types", "drill_pattern")


def downgrade() -> None:
    op.add_column("part_service_types", sa.Column("drill_pattern", sa.String(length=16), nullable=True))
