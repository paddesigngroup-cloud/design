"""create part service types table

Revision ID: 20260425_0056
Revises: 20260425_0055
Create Date: 2026-04-25 18:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260425_0056"
down_revision = "20260425_0055"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "part_service_types",
        sa.Column("admin_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("service_type", sa.String(length=255), nullable=False),
        sa.Column("service_title", sa.String(length=255), nullable=False),
        sa.Column("short_code", sa.String(length=64), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("is_system", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("timezone('utc', now())"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("timezone('utc', now())"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("row_version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.ForeignKeyConstraint(["admin_id"], ["admins.id"], name=op.f("fk_part_service_types_admin_id_admins"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_part_service_types")),
    )
    op.create_index(op.f("ix_part_service_types_admin_id"), "part_service_types", ["admin_id"], unique=False)
    op.create_index(op.f("ix_part_service_types_short_code"), "part_service_types", ["short_code"], unique=False)
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_part_service_types_scope_admin_not_null
        ON part_service_types (lower(service_type), lower(short_code), admin_id)
        WHERE admin_id IS NOT NULL;
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_part_service_types_scope_system
        ON part_service_types (lower(service_type), lower(short_code))
        WHERE admin_id IS NULL;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_part_service_types_updated_at
        BEFORE UPDATE ON part_service_types
        FOR EACH ROW
        EXECUTE FUNCTION public.set_row_updated_at();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_part_service_types_updated_at ON part_service_types;")
    op.execute("DROP INDEX IF EXISTS uq_part_service_types_scope_system;")
    op.execute("DROP INDEX IF EXISTS uq_part_service_types_scope_admin_not_null;")
    op.drop_index(op.f("ix_part_service_types_short_code"), table_name="part_service_types")
    op.drop_index(op.f("ix_part_service_types_admin_id"), table_name="part_service_types")
    op.drop_table("part_service_types")
