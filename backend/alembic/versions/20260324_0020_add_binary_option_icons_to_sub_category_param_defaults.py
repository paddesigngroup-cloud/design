"""add binary option icons to sub category param defaults

Revision ID: 20260324_0020
Revises: 20260324_0019
Create Date: 2026-03-24 12:55:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260324_0020"
down_revision = "20260324_0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sub_category_param_defaults",
        sa.Column("binary_off_icon_path", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "sub_category_param_defaults",
        sa.Column("binary_on_icon_path", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("sub_category_param_defaults", "binary_on_icon_path")
    op.drop_column("sub_category_param_defaults", "binary_off_icon_path")
