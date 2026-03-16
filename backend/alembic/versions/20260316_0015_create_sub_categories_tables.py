"""create sub categories tables

Revision ID: 20260316_0015
Revises: 20260316_0014
Create Date: 2026-03-16 07:00:00
"""
from __future__ import annotations

import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260316_0015"
down_revision = "20260316_0014"
branch_labels = None
depends_on = None


SEEDED_SUB_CATEGORY_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
SEEDED_DEFAULTS = {
    "w": "900",
    "d": "600",
    "h": "890",
    "u_f_o": "138",
    "u_th": "16",
    "b_th": "3",
    "l_fl": "16",
    "r_fl": "0",
    "p_f_f": "16",
    "p_b_f": "32",
    "p_u_f": "0",
    "l_ro": "0",
    "r_ro": "0",
    "p_f_r": "0",
    "p_b_r": "0",
    "p_d_r": "0",
    "b_l_s": "0",
    "b_r_s": "0",
    "t_l_s": "0",
    "p_f_ls": "0",
    "p_b_ls": "1",
    "ls_t_k": "0",
    "t_r_s": "0",
    "p_f_rs": "0",
    "p_b_rs": "1",
    "rs_t_k": "0",
    "b_th_ca": "0",
    "pu_b": "0",
    "b_l_r": "1",
    "b_r_r": "0",
    "b_b_r": "0",
    "b_t_r": "0",
    "le_g": "0",
    "ri_g": "0",
    "fr_g": "0",
    "ba_g": "0",
    "bo_g": "16",
    "to_g": "9",
    "w_st": "9",
    "l_to_fr_h_st": "9",
    "r_to_fr_h_st": "0",
    "p_f_to_fr_h_st": "0",
    "p_d_to_fr_h_st": "0",
    "l_to_ba_h_st": "0",
    "r_to_ba_h_st": "0",
    "p_b_to_ba_h_st": "0",
    "p_d_to_ba_h_st": "0",
    "l_to_v_st": "0",
    "r_to_v_st": "0",
    "p_b_to_v_st": "0",
    "p_d_to_v_st": "0",
    "l_bo_v_st": "0",
    "r_bo_v_st": "0",
    "p_b_bo_v_st": "0",
    "p_u_bo_v_st": "0",
    "d_th": "0",
    "f_th": "34",
    "d_th_ca": "0",
    "f_th_ca": "1",
    "pu_d": "1",
    "d_l_r": "80",
    "d_r_r": "1",
    "d_b_r": "1",
    "d_t_r": "0",
    "p_th": "0",
    "le_p": "1",
    "ri_p": "1",
    "fr_p": "19",
    "ba_p": "0",
    "bo_p": "1",
    "to_p": "1",
    "c_th": "0",
    "c_g": "0",
    "le_n": "1",
    "ri_n": "1",
    "fr_n": "0",
    "ba_n": "16",
}


def upgrade() -> None:
    op.create_table(
        "sub_categories",
        sa.Column("admin_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("temp_id", sa.Integer(), nullable=False),
        sa.Column("cat_id", sa.Integer(), nullable=False),
        sa.Column("sub_cat_id", sa.Integer(), nullable=True),
        sa.Column("sub_cat_title", sa.String(length=255), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("is_system", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("timezone('utc', now())"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("timezone('utc', now())"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("row_version", sa.Integer(), server_default="1", nullable=False),
        sa.ForeignKeyConstraint(["admin_id"], ["admins.id"], name=op.f("fk_sub_categories_admin_id_admins"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["temp_id"], ["templates.temp_id"], name=op.f("fk_sub_categories_temp_id_templates"), ondelete="CASCADE", onupdate="CASCADE"),
        sa.ForeignKeyConstraint(["cat_id"], ["categories.cat_id"], name=op.f("fk_sub_categories_cat_id_categories"), ondelete="CASCADE", onupdate="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sub_categories")),
        sa.UniqueConstraint("sub_cat_id", name=op.f("uq_sub_categories_sub_cat_id")),
    )
    op.create_index(op.f("ix_sub_categories_admin_id"), "sub_categories", ["admin_id"], unique=False)
    op.create_index(op.f("ix_sub_categories_temp_id"), "sub_categories", ["temp_id"], unique=False)
    op.create_index(op.f("ix_sub_categories_cat_id"), "sub_categories", ["cat_id"], unique=False)
    op.create_index(op.f("ix_sub_categories_sub_cat_id"), "sub_categories", ["sub_cat_id"], unique=False)
    op.create_index(
        "uq_sub_categories_system_title",
        "sub_categories",
        ["cat_id", "sub_cat_title"],
        unique=True,
        postgresql_where=sa.text("admin_id IS NULL"),
    )
    op.create_index(
        "uq_sub_categories_admin_title",
        "sub_categories",
        ["admin_id", "cat_id", "sub_cat_title"],
        unique=True,
        postgresql_where=sa.text("admin_id IS NOT NULL"),
    )

    op.create_table(
        "sub_category_param_defaults",
        sa.Column("sub_category_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("param_id", sa.Integer(), nullable=False),
        sa.Column("default_value", sa.Text(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("timezone('utc', now())"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("timezone('utc', now())"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("row_version", sa.Integer(), server_default="1", nullable=False),
        sa.ForeignKeyConstraint(["sub_category_id"], ["sub_categories.id"], name=op.f("fk_sub_category_param_defaults_sub_category_id_sub_categories"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["param_id"], ["params.param_id"], name=op.f("fk_sub_category_param_defaults_param_id_params"), ondelete="CASCADE", onupdate="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sub_category_param_defaults")),
        sa.UniqueConstraint("sub_category_id", "param_id", name="uq_sub_category_param_defaults_sub_category_param"),
    )
    op.create_index(op.f("ix_sub_category_param_defaults_sub_category_id"), "sub_category_param_defaults", ["sub_category_id"], unique=False)
    op.create_index(op.f("ix_sub_category_param_defaults_param_id"), "sub_category_param_defaults", ["param_id"], unique=False)

    sub_categories_table = sa.table(
        "sub_categories",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("admin_id", postgresql.UUID(as_uuid=True)),
        sa.column("temp_id", sa.Integer()),
        sa.column("cat_id", sa.Integer()),
        sa.column("sub_cat_id", sa.Integer()),
        sa.column("sub_cat_title", sa.String(length=255)),
        sa.column("code", sa.String(length=64)),
        sa.column("title", sa.String(length=255)),
        sa.column("sort_order", sa.Integer()),
        sa.column("is_system", sa.Boolean()),
    )
    op.bulk_insert(
        sub_categories_table,
        [
            {
                "id": SEEDED_SUB_CATEGORY_ID,
                "admin_id": None,
                "temp_id": 1,
                "cat_id": 1,
                "sub_cat_id": 1,
                "sub_cat_title": "کاربردی",
                "code": "sub_category_1",
                "title": "کاربردی",
                "sort_order": 1,
                "is_system": True,
            }
        ],
    )

    conn = op.get_bind()
    param_rows = conn.execute(sa.text("SELECT param_id, param_code FROM params")).mappings().all()
    default_rows = [
        {
            "sub_category_id": SEEDED_SUB_CATEGORY_ID,
            "param_id": row["param_id"],
            "default_value": SEEDED_DEFAULTS[row["param_code"]],
        }
        for row in param_rows
        if row["param_code"] in SEEDED_DEFAULTS
    ]
    defaults_table = sa.table(
        "sub_category_param_defaults",
        sa.column("sub_category_id", postgresql.UUID(as_uuid=True)),
        sa.column("param_id", sa.Integer()),
        sa.column("default_value", sa.Text()),
    )
    if default_rows:
        op.bulk_insert(defaults_table, default_rows)


def downgrade() -> None:
    op.drop_index(op.f("ix_sub_category_param_defaults_param_id"), table_name="sub_category_param_defaults")
    op.drop_index(op.f("ix_sub_category_param_defaults_sub_category_id"), table_name="sub_category_param_defaults")
    op.drop_table("sub_category_param_defaults")
    op.drop_index("uq_sub_categories_admin_title", table_name="sub_categories")
    op.drop_index("uq_sub_categories_system_title", table_name="sub_categories")
    op.drop_index(op.f("ix_sub_categories_sub_cat_id"), table_name="sub_categories")
    op.drop_index(op.f("ix_sub_categories_cat_id"), table_name="sub_categories")
    op.drop_index(op.f("ix_sub_categories_temp_id"), table_name="sub_categories")
    op.drop_index(op.f("ix_sub_categories_admin_id"), table_name="sub_categories")
    op.drop_table("sub_categories")
