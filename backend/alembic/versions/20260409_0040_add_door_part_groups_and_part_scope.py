"""add door part groups and part scope

Revision ID: 20260409_0040
Revises: 20260405_0039
Create Date: 2026-04-09 12:30:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260409_0040"
down_revision = "20260405_0039"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "part_kinds",
        sa.Column("part_scope", sa.String(length=16), server_default="structural", nullable=False),
    )
    op.execute(
        """
        UPDATE part_kinds
        SET part_scope = CASE
            WHEN is_internal IS TRUE THEN 'internal'
            ELSE 'structural'
        END;
        """
    )
    op.drop_column("part_kinds", "is_internal")

    op.add_column(
        "part_formulas",
        sa.Column("door_dependent", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )

    op.create_table(
        "door_part_groups",
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
        sa.ForeignKeyConstraint(["admin_id"], ["admins.id"], name=op.f("fk_door_part_groups_admin_id_admins"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_door_part_groups")),
    )
    op.create_index(op.f("ix_door_part_groups_admin_id"), "door_part_groups", ["admin_id"], unique=False)
    op.create_index(op.f("ix_door_part_groups_group_id"), "door_part_groups", ["group_id"], unique=True)
    op.create_index(op.f("ix_door_part_groups_code"), "door_part_groups", ["code"], unique=True)

    op.create_table(
        "door_part_group_items",
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
        sa.ForeignKeyConstraint(["group_ref_id"], ["door_part_groups.id"], name=op.f("fk_door_part_group_items_group_ref_id_door_part_groups"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["part_formula_id"], ["part_formulas.part_formula_id"], name=op.f("fk_door_part_group_items_part_formula_id_part_formulas"), ondelete="RESTRICT", onupdate="CASCADE"),
        sa.ForeignKeyConstraint(["part_kind_id"], ["part_kinds.part_kind_id"], name=op.f("fk_door_part_group_items_part_kind_id_part_kinds"), ondelete="RESTRICT", onupdate="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_door_part_group_items")),
    )
    op.create_index(op.f("ix_door_part_group_items_group_ref_id"), "door_part_group_items", ["group_ref_id"], unique=False)
    op.create_index(op.f("ix_door_part_group_items_part_formula_id"), "door_part_group_items", ["part_formula_id"], unique=False)
    op.create_index(op.f("ix_door_part_group_items_part_kind_id"), "door_part_group_items", ["part_kind_id"], unique=False)

    op.execute(
        """
        CREATE TRIGGER trg_door_part_groups_updated_at
        BEFORE UPDATE ON door_part_groups
        FOR EACH ROW
        EXECUTE FUNCTION public.set_row_updated_at();
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_door_part_group_items_updated_at
        BEFORE UPDATE ON door_part_group_items
        FOR EACH ROW
        EXECUTE FUNCTION public.set_row_updated_at();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_door_part_group_items_updated_at ON door_part_group_items;")
    op.execute("DROP TRIGGER IF EXISTS trg_door_part_groups_updated_at ON door_part_groups;")
    op.drop_index(op.f("ix_door_part_group_items_part_kind_id"), table_name="door_part_group_items")
    op.drop_index(op.f("ix_door_part_group_items_part_formula_id"), table_name="door_part_group_items")
    op.drop_index(op.f("ix_door_part_group_items_group_ref_id"), table_name="door_part_group_items")
    op.drop_table("door_part_group_items")
    op.drop_index(op.f("ix_door_part_groups_code"), table_name="door_part_groups")
    op.drop_index(op.f("ix_door_part_groups_group_id"), table_name="door_part_groups")
    op.drop_index(op.f("ix_door_part_groups_admin_id"), table_name="door_part_groups")
    op.drop_table("door_part_groups")

    op.drop_column("part_formulas", "door_dependent")

    op.add_column(
        "part_kinds",
        sa.Column("is_internal", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.execute(
        """
        UPDATE part_kinds
        SET is_internal = CASE
            WHEN part_scope = 'internal' THEN true
            ELSE false
        END;
        """
    )
    op.drop_column("part_kinds", "part_scope")
