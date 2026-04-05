from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260405_0039"
down_revision = "20260404_0034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("internal_part_groups", sa.Column("controller_type", sa.String(length=128), nullable=True))
    op.add_column("internal_part_groups", sa.Column("controller_bindings", postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    op.drop_column("internal_part_groups", "controller_bindings")
    op.drop_column("internal_part_groups", "controller_type")
