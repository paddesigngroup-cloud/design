"""create part models table

Revision ID: 20260426_0057
Revises: 20260425_0056
Create Date: 2026-04-26 12:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260426_0057"
down_revision = "20260425_0056"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "part_models",
        sa.Column("admin_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("side_count", sa.Integer(), nullable=False),
        sa.Column("interior_angle_sum", sa.Integer(), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("is_system", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("timezone('utc', now())"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("timezone('utc', now())"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("row_version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.CheckConstraint("side_count >= 3", name="ck_part_models_side_count_min"),
        sa.CheckConstraint("interior_angle_sum >= 180", name="ck_part_models_angle_sum_min"),
        sa.ForeignKeyConstraint(["admin_id"], ["admins.id"], name=op.f("fk_part_models_admin_id_admins"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_part_models")),
    )
    op.create_index(op.f("ix_part_models_admin_id"), "part_models", ["admin_id"], unique=False)
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_part_models_title_admin_not_null
        ON part_models (lower(title), admin_id)
        WHERE admin_id IS NOT NULL;
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_part_models_title_system
        ON part_models (lower(title))
        WHERE admin_id IS NULL;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_part_models_updated_at
        BEFORE UPDATE ON part_models
        FOR EACH ROW
        EXECUTE FUNCTION public.set_row_updated_at();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_part_models_updated_at ON part_models;")
    op.execute("DROP INDEX IF EXISTS uq_part_models_title_system;")
    op.execute("DROP INDEX IF EXISTS uq_part_models_title_admin_not_null;")
    op.drop_index(op.f("ix_part_models_admin_id"), table_name="part_models")
    op.drop_table("part_models")
