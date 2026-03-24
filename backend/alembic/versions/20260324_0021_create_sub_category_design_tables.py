"""create sub category design tables

Revision ID: 20260324_0021
Revises: 20260324_0020
Create Date: 2026-03-24 22:45:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260324_0021"
down_revision = "20260324_0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sub_category_designs",
        sa.Column("admin_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sub_category_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("temp_id", sa.Integer(), nullable=False),
        sa.Column("cat_id", sa.Integer(), nullable=False),
        sa.Column("sub_cat_id", sa.Integer(), nullable=False),
        sa.Column("design_id", sa.Integer(), nullable=True),
        sa.Column("design_title", sa.String(length=255), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("is_system", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("timezone('utc', now())"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("timezone('utc', now())"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("row_version", sa.Integer(), server_default="1", nullable=False),
        sa.ForeignKeyConstraint(["admin_id"], ["admins.id"], name=op.f("fk_sub_category_designs_admin_id_admins"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sub_category_id"], ["sub_categories.id"], name=op.f("fk_sub_category_designs_sub_category_id_sub_categories"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["temp_id"], ["templates.temp_id"], name=op.f("fk_sub_category_designs_temp_id_templates"), ondelete="CASCADE", onupdate="CASCADE"),
        sa.ForeignKeyConstraint(["cat_id"], ["categories.cat_id"], name=op.f("fk_sub_category_designs_cat_id_categories"), ondelete="CASCADE", onupdate="CASCADE"),
        sa.ForeignKeyConstraint(["sub_cat_id"], ["sub_categories.sub_cat_id"], name=op.f("fk_sub_category_designs_sub_cat_id_sub_categories"), ondelete="CASCADE", onupdate="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sub_category_designs")),
        sa.UniqueConstraint("design_id", name=op.f("uq_sub_category_designs_design_id")),
    )
    op.create_index(op.f("ix_sub_category_designs_admin_id"), "sub_category_designs", ["admin_id"], unique=False)
    op.create_index(op.f("ix_sub_category_designs_sub_category_id"), "sub_category_designs", ["sub_category_id"], unique=False)
    op.create_index(op.f("ix_sub_category_designs_temp_id"), "sub_category_designs", ["temp_id"], unique=False)
    op.create_index(op.f("ix_sub_category_designs_cat_id"), "sub_category_designs", ["cat_id"], unique=False)
    op.create_index(op.f("ix_sub_category_designs_sub_cat_id"), "sub_category_designs", ["sub_cat_id"], unique=False)
    op.create_index(op.f("ix_sub_category_designs_design_id"), "sub_category_designs", ["design_id"], unique=False)

    op.create_table(
        "sub_category_design_parts",
        sa.Column("design_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("part_formula_id", sa.Integer(), nullable=False),
        sa.Column("part_kind_id", sa.Integer(), nullable=False),
        sa.Column("part_code", sa.String(length=64), nullable=False),
        sa.Column("part_title", sa.String(length=255), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("ui_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("timezone('utc', now())"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("timezone('utc', now())"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("row_version", sa.Integer(), server_default="1", nullable=False),
        sa.ForeignKeyConstraint(["design_id"], ["sub_category_designs.id"], name=op.f("fk_sub_category_design_parts_design_id_sub_category_designs"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["part_formula_id"], ["part_formulas.part_formula_id"], name=op.f("fk_sub_category_design_parts_part_formula_id_part_formulas"), ondelete="RESTRICT", onupdate="CASCADE"),
        sa.ForeignKeyConstraint(["part_kind_id"], ["part_kinds.part_kind_id"], name=op.f("fk_sub_category_design_parts_part_kind_id_part_kinds"), ondelete="RESTRICT", onupdate="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sub_category_design_parts")),
    )
    op.create_index(op.f("ix_sub_category_design_parts_design_id"), "sub_category_design_parts", ["design_id"], unique=False)
    op.create_index(op.f("ix_sub_category_design_parts_part_formula_id"), "sub_category_design_parts", ["part_formula_id"], unique=False)
    op.create_index(op.f("ix_sub_category_design_parts_part_kind_id"), "sub_category_design_parts", ["part_kind_id"], unique=False)
    op.create_index(
        "uq_sub_category_design_parts_design_formula",
        "sub_category_design_parts",
        ["design_id", "part_formula_id"],
        unique=True,
    )

    op.create_table(
        "sub_category_design_part_snapshots",
        sa.Column("design_part_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("resolved_params", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("resolved_base_formulas", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("resolved_part_formulas", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("width", sa.Float(), nullable=True),
        sa.Column("depth", sa.Float(), nullable=True),
        sa.Column("height", sa.Float(), nullable=True),
        sa.Column("cx", sa.Float(), nullable=True),
        sa.Column("cy", sa.Float(), nullable=True),
        sa.Column("cz", sa.Float(), nullable=True),
        sa.Column("viewer_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("timezone('utc', now())"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("timezone('utc', now())"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("row_version", sa.Integer(), server_default="1", nullable=False),
        sa.ForeignKeyConstraint(["design_part_id"], ["sub_category_design_parts.id"], name=op.f("fk_sub_category_design_part_snapshots_design_part_id_sub_category_design_parts"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sub_category_design_part_snapshots")),
        sa.UniqueConstraint("design_part_id", name=op.f("uq_sub_category_design_part_snapshots_design_part_id")),
    )
    op.create_index(op.f("ix_sub_category_design_part_snapshots_design_part_id"), "sub_category_design_part_snapshots", ["design_part_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_sub_category_design_part_snapshots_design_part_id"), table_name="sub_category_design_part_snapshots")
    op.drop_table("sub_category_design_part_snapshots")
    op.drop_index("uq_sub_category_design_parts_design_formula", table_name="sub_category_design_parts")
    op.drop_index(op.f("ix_sub_category_design_parts_part_kind_id"), table_name="sub_category_design_parts")
    op.drop_index(op.f("ix_sub_category_design_parts_part_formula_id"), table_name="sub_category_design_parts")
    op.drop_index(op.f("ix_sub_category_design_parts_design_id"), table_name="sub_category_design_parts")
    op.drop_table("sub_category_design_parts")
    op.drop_index(op.f("ix_sub_category_designs_design_id"), table_name="sub_category_designs")
    op.drop_index(op.f("ix_sub_category_designs_sub_cat_id"), table_name="sub_category_designs")
    op.drop_index(op.f("ix_sub_category_designs_cat_id"), table_name="sub_category_designs")
    op.drop_index(op.f("ix_sub_category_designs_temp_id"), table_name="sub_category_designs")
    op.drop_index(op.f("ix_sub_category_designs_sub_category_id"), table_name="sub_category_designs")
    op.drop_index(op.f("ix_sub_category_designs_admin_id"), table_name="sub_category_designs")
    op.drop_table("sub_category_designs")
