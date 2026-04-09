from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260409_0041"
down_revision = "20260409_0040"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("door_part_groups", sa.Column("controller_type", sa.String(length=128), nullable=True))
    op.add_column("door_part_groups", sa.Column("controller_selection", postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    op.drop_column("door_part_groups", "controller_selection")
    op.drop_column("door_part_groups", "controller_type")
