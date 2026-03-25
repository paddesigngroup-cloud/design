"""create internal part groups table

Revision ID: 20260325_0028
Revises: 20260325_0027
Create Date: 2026-03-25 20:05:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260325_0028"
down_revision = "20260325_0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "internal_part_groups",
        sa.Column("admin_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("group_id", sa.Integer(), nullable=True),
        sa.Column("group_title", sa.String(length=255), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("is_system", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("timezone('utc', now())"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("timezone('utc', now())"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("row_version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.ForeignKeyConstraint(["admin_id"], ["admins.id"], name=op.f("fk_internal_part_groups_admin_id_admins"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_internal_part_groups")),
    )
    op.create_index(op.f("ix_internal_part_groups_admin_id"), "internal_part_groups", ["admin_id"], unique=False)
    op.create_index(op.f("ix_internal_part_groups_group_id"), "internal_part_groups", ["group_id"], unique=True)
    op.create_index(op.f("ix_internal_part_groups_code"), "internal_part_groups", ["code"], unique=True)

    op.create_table(
        "internal_part_group_items",
        sa.Column("group_ref_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("part_formula_id", sa.Integer(), nullable=False),
        sa.Column("part_kind_id", sa.Integer(), nullable=False),
        sa.Column("part_code", sa.String(length=64), nullable=False),
        sa.Column("part_title", sa.String(length=255), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("ui_order", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("timezone('utc', now())"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("timezone('utc', now())"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("row_version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.ForeignKeyConstraint(["group_ref_id"], ["internal_part_groups.id"], name=op.f("fk_internal_part_group_items_group_ref_id_internal_part_groups"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["part_formula_id"], ["part_formulas.part_formula_id"], name=op.f("fk_internal_part_group_items_part_formula_id_part_formulas"), ondelete="RESTRICT", onupdate="CASCADE"),
        sa.ForeignKeyConstraint(["part_kind_id"], ["part_kinds.part_kind_id"], name=op.f("fk_internal_part_group_items_part_kind_id_part_kinds"), ondelete="RESTRICT", onupdate="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_internal_part_group_items")),
    )
    op.create_index(op.f("ix_internal_part_group_items_group_ref_id"), "internal_part_group_items", ["group_ref_id"], unique=False)
    op.create_index(op.f("ix_internal_part_group_items_part_formula_id"), "internal_part_group_items", ["part_formula_id"], unique=False)
    op.create_index(op.f("ix_internal_part_group_items_part_kind_id"), "internal_part_group_items", ["part_kind_id"], unique=False)

    op.execute(
        """
        CREATE TRIGGER trg_internal_part_groups_updated_at
        BEFORE UPDATE ON internal_part_groups
        FOR EACH ROW
        EXECUTE FUNCTION public.set_row_updated_at();
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_internal_part_group_items_updated_at
        BEFORE UPDATE ON internal_part_group_items
        FOR EACH ROW
        EXECUTE FUNCTION public.set_row_updated_at();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_internal_part_group_items_updated_at ON internal_part_group_items;")
    op.execute("DROP TRIGGER IF EXISTS trg_internal_part_groups_updated_at ON internal_part_groups;")
    op.drop_index(op.f("ix_internal_part_group_items_part_kind_id"), table_name="internal_part_group_items")
    op.drop_index(op.f("ix_internal_part_group_items_part_formula_id"), table_name="internal_part_group_items")
    op.drop_index(op.f("ix_internal_part_group_items_group_ref_id"), table_name="internal_part_group_items")
    op.drop_table("internal_part_group_items")
    op.drop_index(op.f("ix_internal_part_groups_code"), table_name="internal_part_groups")
    op.drop_index(op.f("ix_internal_part_groups_group_id"), table_name="internal_part_groups")
    op.drop_index(op.f("ix_internal_part_groups_admin_id"), table_name="internal_part_groups")
    op.drop_table("internal_part_groups")
