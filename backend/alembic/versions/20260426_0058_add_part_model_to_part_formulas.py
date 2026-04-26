"""add part model to part formulas

Revision ID: 20260426_0058
Revises: 20260426_0057
Create Date: 2026-04-26 13:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260426_0058"
down_revision = "20260426_0057"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("part_formulas", sa.Column("part_model_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_index(op.f("ix_part_formulas_part_model_id"), "part_formulas", ["part_model_id"], unique=False)
    op.create_foreign_key(
        op.f("fk_part_formulas_part_model_id_part_models"),
        "part_formulas",
        "part_models",
        ["part_model_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.execute(
        """
        WITH preferred_model AS (
            SELECT id
            FROM part_models
            WHERE lower(title) = lower('مربع مستطیل')
            ORDER BY sort_order ASC, created_at ASC
            LIMIT 1
        ),
        fallback_model AS (
            SELECT id
            FROM part_models
            ORDER BY sort_order ASC, created_at ASC
            LIMIT 1
        ),
        selected_model AS (
            SELECT id FROM preferred_model
            UNION ALL
            SELECT id FROM fallback_model
            WHERE NOT EXISTS (SELECT 1 FROM preferred_model)
            LIMIT 1
        )
        UPDATE part_formulas
        SET part_model_id = (SELECT id FROM selected_model)
        WHERE part_model_id IS NULL;
        """
    )
    op.alter_column("part_formulas", "part_model_id", nullable=False)


def downgrade() -> None:
    op.drop_constraint(op.f("fk_part_formulas_part_model_id_part_models"), "part_formulas", type_="foreignkey")
    op.drop_index(op.f("ix_part_formulas_part_model_id"), table_name="part_formulas")
    op.drop_column("part_formulas", "part_model_id")
