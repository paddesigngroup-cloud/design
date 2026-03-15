"""create part kinds table

Revision ID: 20260315_0004
Revises: 20260315_0003
Create Date: 2026-03-15 01:30:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260315_0004"
down_revision = "20260315_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "part_kinds",
        sa.Column("admin_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("is_system", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("timezone('utc', now())"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("timezone('utc', now())"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("row_version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.ForeignKeyConstraint(["admin_id"], ["admins.id"], name=op.f("fk_part_kinds_admin_id_admins"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_part_kinds")),
    )
    op.create_index(op.f("ix_part_kinds_admin_id"), "part_kinds", ["admin_id"], unique=False)
    op.create_index(
        "uq_part_kinds_system_code",
        "part_kinds",
        ["code"],
        unique=True,
        postgresql_where=sa.text("admin_id IS NULL"),
    )
    op.create_index(
        "uq_part_kinds_admin_code",
        "part_kinds",
        ["admin_id", "code"],
        unique=True,
        postgresql_where=sa.text("admin_id IS NOT NULL"),
    )

    op.execute(
        """
        CREATE TRIGGER trg_part_kinds_updated_at
        BEFORE UPDATE ON part_kinds
        FOR EACH ROW
        EXECUTE FUNCTION public.set_row_updated_at();
        """
    )

    op.execute(
        """
        INSERT INTO part_kinds (admin_id, code, title, sort_order, is_system)
        VALUES
          (NULL, 'unit', 'یونیت', 1, true),
          (NULL, 'stretcher', 'ترک', 2, true),
          (NULL, 'shelf', 'طبقه', 3, true),
          (NULL, 'drawer', 'کشو', 4, true),
          (NULL, 'partition', 'جداکننده', 5, true),
          (NULL, 'door', 'درب', 6, true),
          (NULL, 'face_panel', 'پنل نما', 7, true),
          (NULL, 'toe_kick', 'پاخور', 8, true),
          (NULL, 'frame', 'فریم', 9, true);
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_part_kinds_updated_at ON part_kinds;")
    op.drop_index("uq_part_kinds_admin_code", table_name="part_kinds")
    op.drop_index("uq_part_kinds_system_code", table_name="part_kinds")
    op.drop_index(op.f("ix_part_kinds_admin_id"), table_name="part_kinds")
    op.drop_table("part_kinds")
