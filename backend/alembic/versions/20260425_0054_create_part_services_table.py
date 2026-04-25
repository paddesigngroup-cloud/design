"""create part services table

Revision ID: 20260425_0054
Revises: 20260424_0053
Create Date: 2026-04-25 15:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260425_0054"
down_revision = "20260424_0053"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "part_services",
        sa.Column("admin_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("service_type", sa.String(length=255), nullable=False),
        sa.Column("service_description", sa.Text(), nullable=False),
        sa.Column("service_code", sa.String(length=64), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("is_system", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("timezone('utc', now())"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("timezone('utc', now())"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("row_version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.ForeignKeyConstraint(["admin_id"], ["admins.id"], name=op.f("fk_part_services_admin_id_admins"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_part_services")),
    )
    op.create_index(op.f("ix_part_services_admin_id"), "part_services", ["admin_id"], unique=False)
    op.create_index(op.f("ix_part_services_service_code"), "part_services", ["service_code"], unique=False)
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_part_services_code_admin_not_null
        ON part_services (lower(service_code), admin_id)
        WHERE admin_id IS NOT NULL;
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_part_services_code_system
        ON part_services (lower(service_code))
        WHERE admin_id IS NULL;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_part_services_updated_at
        BEFORE UPDATE ON part_services
        FOR EACH ROW
        EXECUTE FUNCTION public.set_row_updated_at();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_part_services_updated_at ON part_services;")
    op.execute("DROP INDEX IF EXISTS uq_part_services_code_system;")
    op.execute("DROP INDEX IF EXISTS uq_part_services_code_admin_not_null;")
    op.drop_index(op.f("ix_part_services_service_code"), table_name="part_services")
    op.drop_index(op.f("ix_part_services_admin_id"), table_name="part_services")
    op.drop_table("part_services")
