"""add design outline color to categories

Revision ID: 20260329_0036
Revises: 20260329_0035
Create Date: 2026-03-29 20:10:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260329_0036"
down_revision = "20260329_0035"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "categories",
        sa.Column("design_outline_color", sa.String(length=7), nullable=False, server_default="#7A4A2B"),
    )
    op.execute(
        """
        UPDATE categories
        SET design_outline_color = COALESCE(
            (
                SELECT sc.design_outline_color
                FROM sub_categories AS sc
                WHERE sc.cat_id = categories.cat_id
                  AND sc.design_outline_color IS NOT NULL
                  AND sc.design_outline_color <> ''
                ORDER BY sc.sort_order ASC NULLS LAST, sc.sub_cat_id ASC NULLS LAST
                LIMIT 1
            ),
            '#7A4A2B'
        )
        """
    )


def downgrade() -> None:
    op.drop_column("categories", "design_outline_color")
