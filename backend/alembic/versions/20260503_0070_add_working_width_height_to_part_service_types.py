"""add working width and height to part service types

Revision ID: 20260503_0070
Revises: 20260503_0069
Create Date: 2026-05-03 18:10:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260503_0070"
down_revision = "20260503_0069"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("part_service_types", sa.Column("working_width", sa.Float(), nullable=True))
    op.add_column("part_service_types", sa.Column("working_height", sa.Float(), nullable=True))
    op.execute("UPDATE part_service_types SET working_width = 0 WHERE working_width IS NULL")
    op.execute("UPDATE part_service_types SET working_height = 0 WHERE working_height IS NULL")
    op.alter_column("part_service_types", "working_width", nullable=False, server_default="0")
    op.alter_column("part_service_types", "working_height", nullable=False, server_default="0")


def downgrade() -> None:
    op.drop_column("part_service_types", "working_height")
    op.drop_column("part_service_types", "working_width")
