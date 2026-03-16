"""create categories table

Revision ID: 20260316_0014
Revises: 20260316_0013
Create Date: 2026-03-16 05:10:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260316_0014"
down_revision = "20260316_0013"
branch_labels = None
depends_on = None


CATEGORY_SEED_ROWS = [
    {
        "admin_id": None,
        "temp_id": 1,
        "cat_id": 1,
        "cat_title": "زمینی",
        "code": "category_1",
        "title": "زمینی",
        "sort_order": 1,
        "is_system": True,
    },
    {
        "admin_id": None,
        "temp_id": 1,
        "cat_id": 2,
        "cat_title": "هوایی",
        "code": "category_2",
        "title": "هوایی",
        "sort_order": 2,
        "is_system": True,
    },
    {
        "admin_id": None,
        "temp_id": 1,
        "cat_id": 3,
        "cat_title": "ایستاده",
        "code": "category_3",
        "title": "ایستاده",
        "sort_order": 3,
        "is_system": True,
    },
]


def upgrade() -> None:
    op.create_table(
        "categories",
        sa.Column("admin_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("temp_id", sa.Integer(), nullable=False),
        sa.Column("cat_id", sa.Integer(), nullable=True),
        sa.Column("cat_title", sa.String(length=255), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("is_system", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("timezone('utc', now())"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("timezone('utc', now())"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("row_version", sa.Integer(), server_default="1", nullable=False),
        sa.ForeignKeyConstraint(["admin_id"], ["admins.id"], name=op.f("fk_categories_admin_id_admins"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["temp_id"], ["templates.temp_id"], name=op.f("fk_categories_temp_id_templates"), ondelete="CASCADE", onupdate="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_categories")),
        sa.UniqueConstraint("cat_id", name=op.f("uq_categories_cat_id")),
    )
    op.create_index(op.f("ix_categories_admin_id"), "categories", ["admin_id"], unique=False)
    op.create_index(op.f("ix_categories_temp_id"), "categories", ["temp_id"], unique=False)
    op.create_index(op.f("ix_categories_cat_id"), "categories", ["cat_id"], unique=False)
    op.create_index(
        "uq_categories_system_template_title",
        "categories",
        ["temp_id", "cat_title"],
        unique=True,
        postgresql_where=sa.text("admin_id IS NULL"),
    )
    op.create_index(
        "uq_categories_admin_template_title",
        "categories",
        ["admin_id", "temp_id", "cat_title"],
        unique=True,
        postgresql_where=sa.text("admin_id IS NOT NULL"),
    )

    categories_table = sa.table(
        "categories",
        sa.column("admin_id", postgresql.UUID(as_uuid=True)),
        sa.column("temp_id", sa.Integer()),
        sa.column("cat_id", sa.Integer()),
        sa.column("cat_title", sa.String(length=255)),
        sa.column("code", sa.String(length=64)),
        sa.column("title", sa.String(length=255)),
        sa.column("sort_order", sa.Integer()),
        sa.column("is_system", sa.Boolean()),
    )
    op.bulk_insert(categories_table, CATEGORY_SEED_ROWS)


def downgrade() -> None:
    op.drop_index("uq_categories_admin_template_title", table_name="categories")
    op.drop_index("uq_categories_system_template_title", table_name="categories")
    op.drop_index(op.f("ix_categories_cat_id"), table_name="categories")
    op.drop_index(op.f("ix_categories_temp_id"), table_name="categories")
    op.drop_index(op.f("ix_categories_admin_id"), table_name="categories")
    op.drop_table("categories")
