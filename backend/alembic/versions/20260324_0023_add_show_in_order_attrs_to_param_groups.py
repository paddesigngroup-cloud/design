"""add show_in_order_attrs to param groups

Revision ID: 20260324_0023
Revises: 20260324_0022
Create Date: 2026-03-24 23:58:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260324_0023"
down_revision = "20260324_0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "param_groups",
        sa.Column("show_in_order_attrs", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.execute("UPDATE param_groups SET show_in_order_attrs = true WHERE show_in_order_attrs IS NULL")
    op.alter_column("param_groups", "show_in_order_attrs", server_default=None)


def downgrade() -> None:
    op.drop_column("param_groups", "show_in_order_attrs")
