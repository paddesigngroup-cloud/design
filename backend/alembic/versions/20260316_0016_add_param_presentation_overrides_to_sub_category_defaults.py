"""add param presentation overrides to sub category defaults

Revision ID: 20260316_0016
Revises: 20260316_0015
Create Date: 2026-03-16 06:05:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260316_0016"
down_revision = "20260316_0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("sub_category_param_defaults", sa.Column("display_title", sa.String(length=255), nullable=True))
    op.add_column("sub_category_param_defaults", sa.Column("description_text", sa.Text(), nullable=True))
    op.add_column("sub_category_param_defaults", sa.Column("icon_path", sa.String(length=255), nullable=True))
    op.execute(
        """
        UPDATE sub_category_param_defaults AS scpd
        SET display_title = p.param_title_fa
        FROM params AS p
        WHERE p.param_id = scpd.param_id
          AND scpd.display_title IS NULL
        """
    )


def downgrade() -> None:
    op.drop_column("sub_category_param_defaults", "icon_path")
    op.drop_column("sub_category_param_defaults", "description_text")
    op.drop_column("sub_category_param_defaults", "display_title")
