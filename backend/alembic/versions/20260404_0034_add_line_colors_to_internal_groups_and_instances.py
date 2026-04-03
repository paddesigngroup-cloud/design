"""add line colors to internal groups and interior instances

Revision ID: 20260404_0034
Revises: 20260326_0033
Create Date: 2026-04-04 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260404_0034"
down_revision = "20260326_0033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "internal_part_groups",
        sa.Column("line_color", sa.String(length=7), nullable=False, server_default="#8A98A3"),
    )
    op.add_column(
        "sub_category_design_interior_instances",
        sa.Column("line_color", sa.String(length=7), nullable=True),
    )
    op.add_column(
        "order_design_interior_instances",
        sa.Column("line_color", sa.String(length=7), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("order_design_interior_instances", "line_color")
    op.drop_column("sub_category_design_interior_instances", "line_color")
    op.drop_column("internal_part_groups", "line_color")
