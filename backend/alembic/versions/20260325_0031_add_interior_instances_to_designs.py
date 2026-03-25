"""add interior instances to designs

Revision ID: 20260325_0031
Revises: 20260325_0030
Create Date: 2026-03-25 23:30:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260325_0031"
down_revision = "20260325_0030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sub_category_design_interior_instances",
        sa.Column("design_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("internal_part_group_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("instance_code", sa.String(length=64), nullable=False),
        sa.Column("ui_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("placement_z", sa.Float(), nullable=False, server_default="0"),
        sa.Column("interior_box_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("param_values", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("param_meta", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("part_snapshots", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("viewer_boxes", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("timezone('utc', now())")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("timezone('utc', now())")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("row_version", sa.Integer(), nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(["design_id"], ["sub_category_designs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["internal_part_group_id"], ["internal_part_groups.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_sub_category_design_interior_instances_design_id"), "sub_category_design_interior_instances", ["design_id"], unique=False)
    op.create_index(op.f("ix_sub_category_design_interior_instances_internal_part_group_id"), "sub_category_design_interior_instances", ["internal_part_group_id"], unique=False)

    op.create_table(
        "order_design_interior_instances",
        sa.Column("order_design_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_instance_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("internal_part_group_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("instance_code", sa.String(length=64), nullable=False),
        sa.Column("ui_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("placement_z", sa.Float(), nullable=False, server_default="0"),
        sa.Column("interior_box_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("param_values", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("param_meta", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("part_snapshots", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("viewer_boxes", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("timezone('utc', now())")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("timezone('utc', now())")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("row_version", sa.Integer(), nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(["order_design_id"], ["order_designs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_instance_id"], ["sub_category_design_interior_instances.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["internal_part_group_id"], ["internal_part_groups.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_order_design_interior_instances_order_design_id"), "order_design_interior_instances", ["order_design_id"], unique=False)
    op.create_index(op.f("ix_order_design_interior_instances_source_instance_id"), "order_design_interior_instances", ["source_instance_id"], unique=False)
    op.create_index(op.f("ix_order_design_interior_instances_internal_part_group_id"), "order_design_interior_instances", ["internal_part_group_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_order_design_interior_instances_internal_part_group_id"), table_name="order_design_interior_instances")
    op.drop_index(op.f("ix_order_design_interior_instances_source_instance_id"), table_name="order_design_interior_instances")
    op.drop_index(op.f("ix_order_design_interior_instances_order_design_id"), table_name="order_design_interior_instances")
    op.drop_table("order_design_interior_instances")
    op.drop_index(op.f("ix_sub_category_design_interior_instances_internal_part_group_id"), table_name="sub_category_design_interior_instances")
    op.drop_index(op.f("ix_sub_category_design_interior_instances_design_id"), table_name="sub_category_design_interior_instances")
    op.drop_table("sub_category_design_interior_instances")
