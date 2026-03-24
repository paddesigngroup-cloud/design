"""add order designs and sub category design code unique

Revision ID: 20260324_0024
Revises: 20260325_0026
Create Date: 2026-03-25 00:40:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260324_0024"
down_revision = "20260325_0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "order_designs",
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("admin_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sub_category_design_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sub_category_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("design_code", sa.String(length=64), nullable=False),
        sa.Column("design_title", sa.String(length=255), nullable=False),
        sa.Column("instance_code", sa.String(length=64), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("status", sa.String(length=32), server_default="draft", nullable=False),
        sa.Column("order_attr_values", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("order_attr_meta", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("part_snapshots", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("viewer_boxes", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("timezone('utc', now())"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("timezone('utc', now())"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("row_version", sa.Integer(), server_default="1", nullable=False),
        sa.ForeignKeyConstraint(["admin_id"], ["admins.id"], name=op.f("fk_order_designs_admin_id_admins"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], name=op.f("fk_order_designs_order_id_orders"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sub_category_design_id"], ["sub_category_designs.id"], name=op.f("fk_order_designs_sub_category_design_id_sub_category_designs"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["sub_category_id"], ["sub_categories.id"], name=op.f("fk_order_designs_sub_category_id_sub_categories"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_order_designs_user_id_users"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_order_designs")),
        sa.UniqueConstraint("order_id", "instance_code", name="uq_order_designs_order_instance_code"),
    )
    op.create_index(op.f("ix_order_designs_order_id"), "order_designs", ["order_id"], unique=False)
    op.create_index(op.f("ix_order_designs_admin_id"), "order_designs", ["admin_id"], unique=False)
    op.create_index(op.f("ix_order_designs_user_id"), "order_designs", ["user_id"], unique=False)
    op.create_index(op.f("ix_order_designs_sub_category_design_id"), "order_designs", ["sub_category_design_id"], unique=False)
    op.create_index(op.f("ix_order_designs_sub_category_id"), "order_designs", ["sub_category_id"], unique=False)
    op.create_index(op.f("ix_order_designs_design_code"), "order_designs", ["design_code"], unique=False)

    op.create_index(op.f("ix_sub_category_designs_code"), "sub_category_designs", ["code"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_sub_category_designs_code"), table_name="sub_category_designs")
    op.drop_index(op.f("ix_order_designs_design_code"), table_name="order_designs")
    op.drop_index(op.f("ix_order_designs_sub_category_id"), table_name="order_designs")
    op.drop_index(op.f("ix_order_designs_sub_category_design_id"), table_name="order_designs")
    op.drop_index(op.f("ix_order_designs_user_id"), table_name="order_designs")
    op.drop_index(op.f("ix_order_designs_admin_id"), table_name="order_designs")
    op.drop_index(op.f("ix_order_designs_order_id"), table_name="order_designs")
    op.drop_table("order_designs")
