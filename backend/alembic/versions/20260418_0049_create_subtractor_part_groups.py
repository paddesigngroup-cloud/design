"""create subtractor part group tables

Revision ID: 20260418_0049
Revises: 20260414_0048
Create Date: 2026-04-18 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260418_0049"
down_revision = "20260414_0048"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "subtractor_part_groups",
        sa.Column("admin_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("group_id", sa.Integer(), nullable=True),
        sa.Column("group_title", sa.String(length=255), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("icon_path", sa.String(length=255), nullable=True),
        sa.Column("line_color", sa.String(length=7), server_default="#8A98A3", nullable=False),
        sa.Column("controller_type", sa.String(length=128), nullable=True),
        sa.Column("controller_bindings", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("sort_order", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("is_system", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("timezone('utc', now())"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("timezone('utc', now())"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("row_version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.ForeignKeyConstraint(["admin_id"], ["admins.id"], name=op.f("fk_subtractor_part_groups_admin_id_admins"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_subtractor_part_groups")),
    )
    op.create_index(op.f("ix_subtractor_part_groups_admin_id"), "subtractor_part_groups", ["admin_id"], unique=False)
    op.create_index(op.f("ix_subtractor_part_groups_group_id"), "subtractor_part_groups", ["group_id"], unique=True)
    op.create_index(op.f("ix_subtractor_part_groups_code"), "subtractor_part_groups", ["code"], unique=True)

    op.create_table(
        "subtractor_part_group_items",
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
        sa.ForeignKeyConstraint(
            ["group_ref_id"],
            ["subtractor_part_groups.id"],
            name=op.f("fk_subtractor_part_group_items_group_ref_id_subtractor_part_groups"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["part_formula_id"],
            ["part_formulas.part_formula_id"],
            name=op.f("fk_subtractor_part_group_items_part_formula_id_part_formulas"),
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["part_kind_id"],
            ["part_kinds.part_kind_id"],
            name=op.f("fk_subtractor_part_group_items_part_kind_id_part_kinds"),
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_subtractor_part_group_items")),
    )
    op.create_index(op.f("ix_subtractor_part_group_items_group_ref_id"), "subtractor_part_group_items", ["group_ref_id"], unique=False)
    op.create_index(op.f("ix_subtractor_part_group_items_part_formula_id"), "subtractor_part_group_items", ["part_formula_id"], unique=False)
    op.create_index(op.f("ix_subtractor_part_group_items_part_kind_id"), "subtractor_part_group_items", ["part_kind_id"], unique=False)

    op.create_table(
        "subtractor_part_group_param_groups",
        sa.Column("group_ref_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("param_group_id", sa.Integer(), nullable=False),
        sa.Column("param_group_code", sa.String(length=64), nullable=False),
        sa.Column("param_group_title", sa.String(length=255), nullable=False),
        sa.Column("param_group_icon_path", sa.String(length=255), nullable=True),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("ui_order", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("timezone('utc', now())"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("timezone('utc', now())"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("row_version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.ForeignKeyConstraint(
            ["group_ref_id"],
            ["subtractor_part_groups.id"],
            name=op.f("fk_subtractor_part_group_param_groups_group_ref_id_subtractor_part_groups"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["param_group_id"],
            ["param_groups.param_group_id"],
            name=op.f("fk_subtractor_part_group_param_groups_param_group_id_param_groups"),
            ondelete="RESTRICT",
            onupdate="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_subtractor_part_group_param_groups")),
    )
    op.create_index(
        op.f("ix_subtractor_part_group_param_groups_group_ref_id"),
        "subtractor_part_group_param_groups",
        ["group_ref_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_subtractor_part_group_param_groups_param_group_id"),
        "subtractor_part_group_param_groups",
        ["param_group_id"],
        unique=False,
    )

    op.create_table(
        "subtractor_part_group_param_defaults",
        sa.Column("subtractor_part_group_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("param_id", sa.Integer(), nullable=False),
        sa.Column("default_value", sa.Text(), nullable=True),
        sa.Column("display_title", sa.String(length=255), nullable=True),
        sa.Column("description_text", sa.Text(), nullable=True),
        sa.Column("icon_path", sa.String(length=255), nullable=True),
        sa.Column("input_mode", sa.String(length=16), server_default=sa.text("'value'"), nullable=False),
        sa.Column("binary_off_label", sa.String(length=255), nullable=True),
        sa.Column("binary_on_label", sa.String(length=255), nullable=True),
        sa.Column("binary_off_icon_path", sa.String(length=255), nullable=True),
        sa.Column("binary_on_icon_path", sa.String(length=255), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("timezone('utc', now())"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("timezone('utc', now())"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("row_version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.ForeignKeyConstraint(
            ["subtractor_part_group_id"],
            ["subtractor_part_groups.id"],
            name=op.f("fk_subtractor_part_group_param_defaults_subtractor_part_group_id_subtractor_part_groups"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["param_id"],
            ["params.param_id"],
            name=op.f("fk_subtractor_part_group_param_defaults_param_id_params"),
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_subtractor_part_group_param_defaults")),
    )
    op.create_index(
        op.f("ix_subtractor_part_group_param_defaults_subtractor_part_group_id"),
        "subtractor_part_group_param_defaults",
        ["subtractor_part_group_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_subtractor_part_group_param_defaults_param_id"),
        "subtractor_part_group_param_defaults",
        ["param_id"],
        unique=False,
    )

    op.execute(
        """
        CREATE TRIGGER trg_subtractor_part_groups_updated_at
        BEFORE UPDATE ON subtractor_part_groups
        FOR EACH ROW
        EXECUTE FUNCTION public.set_row_updated_at();
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_subtractor_part_group_items_updated_at
        BEFORE UPDATE ON subtractor_part_group_items
        FOR EACH ROW
        EXECUTE FUNCTION public.set_row_updated_at();
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_subtractor_part_group_param_groups_updated_at
        BEFORE UPDATE ON subtractor_part_group_param_groups
        FOR EACH ROW
        EXECUTE FUNCTION public.set_row_updated_at();
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_subtractor_part_group_param_defaults_updated_at
        BEFORE UPDATE ON subtractor_part_group_param_defaults
        FOR EACH ROW
        EXECUTE FUNCTION public.set_row_updated_at();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_subtractor_part_group_param_defaults_updated_at ON subtractor_part_group_param_defaults;")
    op.execute("DROP TRIGGER IF EXISTS trg_subtractor_part_group_param_groups_updated_at ON subtractor_part_group_param_groups;")
    op.execute("DROP TRIGGER IF EXISTS trg_subtractor_part_group_items_updated_at ON subtractor_part_group_items;")
    op.execute("DROP TRIGGER IF EXISTS trg_subtractor_part_groups_updated_at ON subtractor_part_groups;")

    op.drop_index(op.f("ix_subtractor_part_group_param_defaults_param_id"), table_name="subtractor_part_group_param_defaults")
    op.drop_index(
        op.f("ix_subtractor_part_group_param_defaults_subtractor_part_group_id"),
        table_name="subtractor_part_group_param_defaults",
    )
    op.drop_table("subtractor_part_group_param_defaults")

    op.drop_index(op.f("ix_subtractor_part_group_param_groups_param_group_id"), table_name="subtractor_part_group_param_groups")
    op.drop_index(op.f("ix_subtractor_part_group_param_groups_group_ref_id"), table_name="subtractor_part_group_param_groups")
    op.drop_table("subtractor_part_group_param_groups")

    op.drop_index(op.f("ix_subtractor_part_group_items_part_kind_id"), table_name="subtractor_part_group_items")
    op.drop_index(op.f("ix_subtractor_part_group_items_part_formula_id"), table_name="subtractor_part_group_items")
    op.drop_index(op.f("ix_subtractor_part_group_items_group_ref_id"), table_name="subtractor_part_group_items")
    op.drop_table("subtractor_part_group_items")

    op.drop_index(op.f("ix_subtractor_part_groups_code"), table_name="subtractor_part_groups")
    op.drop_index(op.f("ix_subtractor_part_groups_group_id"), table_name="subtractor_part_groups")
    op.drop_index(op.f("ix_subtractor_part_groups_admin_id"), table_name="subtractor_part_groups")
    op.drop_table("subtractor_part_groups")
