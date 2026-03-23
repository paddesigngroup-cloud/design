"""add binary option labels to sub category param defaults

Revision ID: 20260324_0019
Revises: 20260323_0018
Create Date: 2026-03-24 00:19:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260324_0019"
down_revision = "20260323_0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sub_category_param_defaults",
        sa.Column("binary_off_label", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "sub_category_param_defaults",
        sa.Column("binary_on_label", sa.String(length=255), nullable=True),
    )
    op.execute(
        """
        UPDATE sub_category_param_defaults
        SET binary_off_label = COALESCE(NULLIF(TRIM(binary_off_label), ''), '0'),
            binary_on_label = COALESCE(NULLIF(TRIM(binary_on_label), ''), '1')
        """
    )


def downgrade() -> None:
    op.drop_column("sub_category_param_defaults", "binary_on_label")
    op.drop_column("sub_category_param_defaults", "binary_off_label")
