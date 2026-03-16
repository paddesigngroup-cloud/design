"""create part formulas table

Revision ID: 20260316_0012
Revises: 20260315_0011
Create Date: 2026-03-16 12:00:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260316_0012"
down_revision = "20260315_0011"
branch_labels = None
depends_on = None


PART_FORMULA_SEED_ROWS = [
    {"admin_id": None, "part_formula_id": 1, "part_kind_id": 1, "part_sub_kind_id": 1, "part_code": "floor", "part_title": "کف", "formula_l": "w-f1", "formula_w": "d-f2", "formula_width": "w-f1", "formula_depth": "d-f2", "formula_height": "u_th", "formula_cx": "((w-f1)/2)+f3", "formula_cy": "((d-f2)/2)+f4", "formula_cz": "f5+((u_th)/2)", "code": "floor", "title": "کف", "sort_order": 1, "is_system": True},
    {"admin_id": None, "part_formula_id": 2, "part_kind_id": 1, "part_sub_kind_id": 2, "part_code": "roof", "part_title": "طاق", "formula_l": "w-f6", "formula_w": "d-f7", "formula_width": "w-f6", "formula_depth": "d-f7", "formula_height": "u_th", "formula_cx": "((w-f6)/2)+f8", "formula_cy": "((d-f7)/2)+f9", "formula_cz": "h-f10-((u_th)/2)", "code": "roof", "title": "طاق", "sort_order": 2, "is_system": True},
    {"admin_id": None, "part_formula_id": 3, "part_kind_id": 1, "part_sub_kind_id": 3, "part_code": "le_side", "part_title": "بدنه چپ", "formula_l": "h-f11", "formula_w": "d-f12", "formula_width": "u_th", "formula_depth": "d-f12", "formula_height": "h-f11", "formula_cx": "((u_th)/2)+f13", "formula_cy": "((d-f12)/2)+f14", "formula_cz": "f15+((h-f11)/2)", "code": "le_side", "title": "بدنه چپ", "sort_order": 3, "is_system": True},
    {"admin_id": None, "part_formula_id": 4, "part_kind_id": 1, "part_sub_kind_id": 4, "part_code": "ri_side", "part_title": "بدنه راست", "formula_l": "h-f16", "formula_w": "d-f17", "formula_width": "u_th", "formula_depth": "d-f17", "formula_height": "h-f16", "formula_cx": "w-f18-((u_th)/2)", "formula_cy": "((d-f17)/2)+f19", "formula_cz": "f20+((h-f16)/2)", "code": "ri_side", "title": "بدنه راست", "sort_order": 4, "is_system": True},
    {"admin_id": None, "part_formula_id": 5, "part_kind_id": 1, "part_sub_kind_id": 5, "part_code": "back", "part_title": "پشت", "formula_l": "h-f21", "formula_w": "w-f22", "formula_width": "w-f22", "formula_depth": "b_th", "formula_height": "h-f21", "formula_cx": "((w-f22)/2)+f23", "formula_cy": "d-f24-((b_th)/2)", "formula_cz": "((h-f21)/2)+f25", "code": "back", "title": "پشت", "sort_order": 5, "is_system": True},
    {"admin_id": None, "part_formula_id": 6, "part_kind_id": 2, "part_sub_kind_id": 3, "part_code": "top_fro_h_stre", "part_title": "تیرک افقی جلو بالا", "formula_l": "w-f26", "formula_w": "w_st", "formula_width": "w-f26", "formula_depth": "w_st", "formula_height": "u_th", "formula_cx": "((w-f26)/2)+f27", "formula_cy": "((w_st)/2)+f28", "formula_cz": "h-f29-((u_th)/2)", "code": "top_fro_h_stre", "title": "تیرک افقی جلو بالا", "sort_order": 6, "is_system": True},
    {"admin_id": None, "part_formula_id": 7, "part_kind_id": 2, "part_sub_kind_id": 1, "part_code": "top_bac_h_stre", "part_title": "تیرک افقی عقب بالا", "formula_l": "w-f30", "formula_w": "w_st", "formula_width": "w-f30", "formula_depth": "w_st", "formula_height": "u_th", "formula_cx": "((w-f30)/2)+f31", "formula_cy": "d-f32-((w_st)/2)", "formula_cz": "h-f33-((u_th)/2)", "code": "top_bac_h_stre", "title": "تیرک افقی عقب بالا", "sort_order": 7, "is_system": True},
    {"admin_id": None, "part_formula_id": 8, "part_kind_id": 2, "part_sub_kind_id": 2, "part_code": "top_bac_v_stre", "part_title": "تیرک عمودی عقب بالا", "formula_l": "w-f34", "formula_w": "w_st", "formula_width": "w-f34", "formula_depth": "u_th", "formula_height": "w_st", "formula_cx": "((w-f34)/2)+f35", "formula_cy": "d-f36-((u_th)/2)", "formula_cz": "h-f37-((w_st)/2)", "code": "top_bac_v_stre", "title": "تیرک عمودی عقب بالا", "sort_order": 8, "is_system": True},
    {"admin_id": None, "part_formula_id": 9, "part_kind_id": 2, "part_sub_kind_id": 6, "part_code": "bot_bac_v_stre", "part_title": "تیرک عمودی عقب پایین", "formula_l": "w-f38", "formula_w": "w_st", "formula_width": "w-f38", "formula_depth": "u_th", "formula_height": "w_st", "formula_cx": "((w-f38)/2)+f39", "formula_cy": "d-f40-((u_th)/2)", "formula_cz": "((w_st)/2)+f41", "code": "bot_bac_v_stre", "title": "تیرک عمودی عقب پایین", "sort_order": 9, "is_system": True},
]


def upgrade() -> None:
    op.create_table(
        "part_formulas",
        sa.Column("admin_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("part_formula_id", sa.Integer(), nullable=True),
        sa.Column("part_kind_id", sa.Integer(), nullable=False),
        sa.Column("part_sub_kind_id", sa.Integer(), nullable=False),
        sa.Column("part_code", sa.String(length=64), nullable=False),
        sa.Column("part_title", sa.String(length=255), nullable=False),
        sa.Column("formula_l", sa.String(length=2048), nullable=False),
        sa.Column("formula_w", sa.String(length=2048), nullable=False),
        sa.Column("formula_width", sa.String(length=2048), nullable=False),
        sa.Column("formula_depth", sa.String(length=2048), nullable=False),
        sa.Column("formula_height", sa.String(length=2048), nullable=False),
        sa.Column("formula_cx", sa.String(length=2048), nullable=False),
        sa.Column("formula_cy", sa.String(length=2048), nullable=False),
        sa.Column("formula_cz", sa.String(length=2048), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("is_system", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("timezone('utc', now())"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("timezone('utc', now())"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("row_version", sa.Integer(), server_default="1", nullable=False),
        sa.ForeignKeyConstraint(["admin_id"], ["admins.id"], name=op.f("fk_part_formulas_admin_id_admins"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["part_kind_id"], ["part_kinds.part_kind_id"], name=op.f("fk_part_formulas_part_kind_id_part_kinds"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_part_formulas")),
        sa.UniqueConstraint("part_formula_id", name=op.f("uq_part_formulas_part_formula_id")),
    )
    op.create_index(op.f("ix_part_formulas_admin_id"), "part_formulas", ["admin_id"], unique=False)
    op.create_index(op.f("ix_part_formulas_part_formula_id"), "part_formulas", ["part_formula_id"], unique=False)
    op.create_index(op.f("ix_part_formulas_part_kind_id"), "part_formulas", ["part_kind_id"], unique=False)
    op.create_index("uq_part_formulas_system_part_code", "part_formulas", ["part_code"], unique=True, postgresql_where=sa.text("admin_id IS NULL"))
    op.create_index("uq_part_formulas_admin_part_code", "part_formulas", ["admin_id", "part_code"], unique=True, postgresql_where=sa.text("admin_id IS NOT NULL"))
    op.create_index("uq_part_formulas_system_kind_sub_kind", "part_formulas", ["part_kind_id", "part_sub_kind_id"], unique=True, postgresql_where=sa.text("admin_id IS NULL"))
    op.create_index("uq_part_formulas_admin_kind_sub_kind", "part_formulas", ["admin_id", "part_kind_id", "part_sub_kind_id"], unique=True, postgresql_where=sa.text("admin_id IS NOT NULL"))

    part_formulas_table = sa.table(
        "part_formulas",
        sa.column("admin_id", postgresql.UUID(as_uuid=True)),
        sa.column("part_formula_id", sa.Integer()),
        sa.column("part_kind_id", sa.Integer()),
        sa.column("part_sub_kind_id", sa.Integer()),
        sa.column("part_code", sa.String(length=64)),
        sa.column("part_title", sa.String(length=255)),
        sa.column("formula_l", sa.String(length=2048)),
        sa.column("formula_w", sa.String(length=2048)),
        sa.column("formula_width", sa.String(length=2048)),
        sa.column("formula_depth", sa.String(length=2048)),
        sa.column("formula_height", sa.String(length=2048)),
        sa.column("formula_cx", sa.String(length=2048)),
        sa.column("formula_cy", sa.String(length=2048)),
        sa.column("formula_cz", sa.String(length=2048)),
        sa.column("code", sa.String(length=64)),
        sa.column("title", sa.String(length=255)),
        sa.column("sort_order", sa.Integer()),
        sa.column("is_system", sa.Boolean()),
    )
    op.bulk_insert(part_formulas_table, PART_FORMULA_SEED_ROWS)


def downgrade() -> None:
    op.drop_index("uq_part_formulas_admin_kind_sub_kind", table_name="part_formulas")
    op.drop_index("uq_part_formulas_system_kind_sub_kind", table_name="part_formulas")
    op.drop_index("uq_part_formulas_admin_part_code", table_name="part_formulas")
    op.drop_index("uq_part_formulas_system_part_code", table_name="part_formulas")
    op.drop_index(op.f("ix_part_formulas_part_kind_id"), table_name="part_formulas")
    op.drop_index(op.f("ix_part_formulas_part_formula_id"), table_name="part_formulas")
    op.drop_index(op.f("ix_part_formulas_admin_id"), table_name="part_formulas")
    op.drop_table("part_formulas")
