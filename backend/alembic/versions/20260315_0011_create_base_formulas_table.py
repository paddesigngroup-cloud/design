"""create base formulas table

Revision ID: 20260315_0011
Revises: 20260315_0010
Create Date: 2026-03-15 18:10:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "20260315_0011"
down_revision = "20260315_0010"
branch_labels = None
depends_on = None


FORMULA_ROWS = [
    ("f1", "((l_fl)*(u_th))+((r_fl)*(u_th))+((le_p)*(p_th))+((ri_p)*(p_th))+(le_g)+(ri_g)+(le_n)+(ri_n)"),
    ("f2", "((d_th_ca)*(d_th))+((f_th_ca)*(f_th))+((b_th_ca)*(b_th))+((fr_p)*(p_th))+((ba_p)*(p_th))+(fr_g)+(ba_g)+(fr_n)+(ba_n)+(p_f_f)+(p_b_f)"),
    ("f3", "((l_fl)*(u_th))+((le_p)*(p_th))+(le_g)+(le_n)"),
    ("f4", "((d_th_ca)*(d_th))+((f_th_ca)*(f_th))+((fr_p)*(p_th))+(fr_g)+(fr_n)+(p_f_f)"),
    ("f5", "((bo_p)*(p_th))+(bo_g)+(u_f_o)+(p_u_f)"),
    ("f6", "((l_ro)*(u_th))+((r_ro)*(u_th))+((le_p)*(p_th))+((ri_p)*(p_th))+(le_g)+(ri_g)+(le_n)+(ri_n)"),
    ("f7", "((d_th_ca)*(d_th))+((f_th_ca)*(f_th))+((b_th_ca)*(b_th))+((fr_p)*(p_th))+((ba_p)*(p_th))+(fr_g)+(ba_g)+(fr_n)+(ba_n)+(p_f_r)+(p_b_r)"),
    ("f8", "((l_ro)*(u_th))+((le_p)*(p_th))+(le_g)+(le_n)"),
    ("f9", "((d_th_ca)*(d_th))+((f_th_ca)*(f_th))+((fr_p)*(p_th))+(fr_g)+(fr_n)+(p_f_r)"),
    ("f10", "(c_th)+((to_p)*(p_th))+(to_g)+(c_g)+(p_d_r)"),
    ("f11", "((ls_t_k)*(u_f_o))+((bo_p)*(p_th))+(bo_g)+((ls_t_k)*(b_l_s)*(u_th))+(c_th)+((to_p)*(p_th))+(to_g)+(c_g)+((t_l_s)*(u_th))"),
    ("f12", "((d_th_ca)*(d_th))+((f_th_ca)*(f_th))+((b_th_ca)*(b_th))+((fr_p)*(p_th))+((ba_p)*(p_th))+(fr_g)+(ba_g)+(fr_n)+(ba_n)+(p_f_ls)+(p_b_ls)"),
    ("f13", "((le_p)*(p_th))+(le_g)+(le_n)"),
    ("f14", "((d_th_ca)*(d_th))+((f_th_ca)*(f_th))+((fr_p)*(p_th))+(fr_g)+(fr_n)+(p_f_ls)"),
    ("f15", "((bo_p)*(p_th))+(bo_g)+((ls_t_k)*(u_f_o))+((b_l_s)*(u_th))"),
    ("f16", "((rs_t_k)*(u_f_o))+((bo_p)*(p_th))+(bo_g)+((rs_t_k)*(b_r_s)*(u_th))+(c_th)+((to_p)*(p_th))+(to_g)+(c_g)+((t_r_s)*(u_th))"),
    ("f17", "((d_th_ca)*(d_th))+((f_th_ca)*(f_th))+((b_th_ca)*(b_th))+((fr_p)*(p_th))+((ba_p)*(p_th))+(fr_g)+(ba_g)+(fr_n)+(ba_n)+(p_f_rs)+(p_b_rs)"),
    ("f18", "((ri_p)*(p_th))+(ri_g)+(ri_n)"),
    ("f19", "((d_th_ca)*(d_th))+((f_th_ca)*(f_th))+((fr_p)*(p_th))+(fr_g)+(fr_n)+(p_f_rs)"),
    ("f20", "((bo_p)*(p_th))+(bo_g)+((rs_t_k)*(u_f_o))+((b_r_s)*(u_th))"),
    ("f21", "(u_f_o)+((bo_p)*(p_th))+(bo_g)+(c_th)+((to_p)*(p_th))+(to_g)+(c_g)+(b_b_r)+(b_t_r)+(p_d_r)"),
    ("f22", "((le_p)*(p_th))+((ri_p)*(p_th))+(le_g)+(ri_g)+(le_n)+(ri_n)+(b_l_r)+(b_r_r)"),
    ("f23", "((le_p)*(p_th))+(le_g)+(le_n)+(b_l_r)"),
    ("f24", "((b_th_ca)*(b_th))+((ba_p)*(p_th))+(ba_g)+(ba_n)+(pu_b)"),
    ("f25", "(u_f_o)+((bo_p)*(p_th))+(bo_g)+(b_b_r)"),
    ("f26", "((l_to_fr_h_st)*(u_th))+((r_to_fr_h_st)*(u_th))+((le_p)*(p_th))+((ri_p)*(p_th))+(le_g)+(ri_g)+(le_n)+(ri_n)"),
    ("f27", "((l_to_fr_h_st)*(u_th))+((le_p)*(p_th))+(le_g)+(le_n)"),
    ("f28", "((d_th_ca)*(d_th))+((f_th_ca)*(f_th))+((fr_p)*(p_th))+(fr_g)+(fr_n)+(p_f_to_fr_h_st)"),
    ("f29", "(c_th)+((to_p)*(p_th))+(to_g)+(c_g)+(p_d_to_fr_h_st)"),
    ("f30", "((l_to_ba_h_st)*(u_th))+((r_to_ba_h_st)*(u_th))+((le_p)*(p_th))+((ri_p)*(p_th))+(le_g)+(ri_g)+(le_n)+(ri_n)"),
    ("f31", "((l_to_ba_h_st)*(u_th))+((le_p)*(p_th))+(le_g)+(le_n)"),
    ("f32", "((b_th_ca)*(b_th))+((ba_p)*(p_th))+(ba_g)+(ba_n)+(p_b_to_ba_h_st)"),
    ("f33", "(c_th)+((to_p)*(p_th))+(to_g)+(c_g)+(p_d_to_ba_h_st)"),
    ("f34", "((l_to_v_st)*(u_th))+((r_to_v_st)*(u_th))+((le_p)*(p_th))+((ri_p)*(p_th))+(le_g)+(ri_g)+(le_n)+(ri_n)"),
    ("f35", "((l_to_v_st)*(u_th))+((le_p)*(p_th))+(le_g)+(le_n)"),
    ("f36", "((b_th_ca)*(b_th))+((ba_p)*(p_th))+(ba_g)+(ba_n)+(p_b_to_v_st)"),
    ("f37", "(c_th)+((to_p)*(p_th))+(to_g)+(c_g)+(p_d_to_v_st)"),
    ("f38", "((l_bo_v_st)*(u_th))+((r_bo_v_st)*(u_th))+((le_p)*(p_th))+((ri_p)*(p_th))+(le_g)+(ri_g)+(le_n)+(ri_n)"),
    ("f39", "((l_bo_v_st)*(u_th))+((le_p)*(p_th))+(le_g)+(le_n)"),
    ("f40", "((b_th_ca)*(b_th))+((ba_p)*(p_th))+(ba_g)+(ba_n)+(p_b_bo_v_st)"),
    ("f41", "(u_f_o)+((bo_p)*(p_th))+(bo_g)+(p_u_bo_v_st)"),
]

BASE_FORMULA_SEED_ROWS = [
    {
        "admin_id": None,
        "fo_id": index,
        "param_formula": code,
        "formula": formula,
        "code": code,
        "title": code,
        "sort_order": index,
        "is_system": True,
    }
    for index, (code, formula) in enumerate(FORMULA_ROWS, start=1)
]


def upgrade() -> None:
    op.create_table(
        "base_formulas",
        sa.Column("admin_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("fo_id", sa.Integer(), nullable=True),
        sa.Column("param_formula", sa.String(length=64), nullable=False),
        sa.Column("formula", sa.String(length=2048), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("is_system", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("timezone('utc', now())"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("timezone('utc', now())"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("row_version", sa.Integer(), server_default="1", nullable=False),
        sa.ForeignKeyConstraint(["admin_id"], ["admins.id"], name=op.f("fk_base_formulas_admin_id_admins"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_base_formulas")),
        sa.UniqueConstraint("fo_id", name=op.f("uq_base_formulas_fo_id")),
        sa.UniqueConstraint("param_formula", name=op.f("uq_base_formulas_param_formula")),
    )
    op.create_index(op.f("ix_base_formulas_admin_id"), "base_formulas", ["admin_id"], unique=False)
    op.create_index(op.f("ix_base_formulas_fo_id"), "base_formulas", ["fo_id"], unique=False)

    base_formulas_table = sa.table(
        "base_formulas",
        sa.column("admin_id", postgresql.UUID(as_uuid=True)),
        sa.column("fo_id", sa.Integer()),
        sa.column("param_formula", sa.String(length=64)),
        sa.column("formula", sa.String(length=2048)),
        sa.column("code", sa.String(length=64)),
        sa.column("title", sa.String(length=255)),
        sa.column("sort_order", sa.Integer()),
        sa.column("is_system", sa.Boolean()),
    )
    op.bulk_insert(base_formulas_table, BASE_FORMULA_SEED_ROWS)


def downgrade() -> None:
    op.drop_index(op.f("ix_base_formulas_fo_id"), table_name="base_formulas")
    op.drop_index(op.f("ix_base_formulas_admin_id"), table_name="base_formulas")
    op.drop_table("base_formulas")
