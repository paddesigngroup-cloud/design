"""add subtractor instances to designs and orders

Revision ID: 20260418_0051
Revises: 20260418_0050
Create Date: 2026-04-18 12:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260418_0051"
down_revision = "20260418_0050"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sub_category_design_subtractor_instances",
        sa.Column("design_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("subtractor_part_group_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("instance_code", sa.String(length=64), nullable=False),
        sa.Column("line_color", sa.String(length=7), nullable=True),
        sa.Column("ui_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("placement_z", sa.Float(), nullable=False),
        sa.Column("param_values", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("param_meta", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("part_snapshots", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("viewer_boxes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="draft", nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("row_version", sa.Integer(), server_default="1", nullable=False),
        sa.ForeignKeyConstraint(["design_id"], ["sub_category_designs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["subtractor_part_group_id"], ["subtractor_part_groups.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_sub_category_design_subtractor_instances_design_id"), "sub_category_design_subtractor_instances", ["design_id"], unique=False)
    op.create_index(op.f("ix_sub_category_design_subtractor_instances_subtractor_part_group_id"), "sub_category_design_subtractor_instances", ["subtractor_part_group_id"], unique=False)

    op.create_table(
        "order_design_subtractor_instances",
        sa.Column("order_design_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_instance_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("subtractor_part_group_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("instance_code", sa.String(length=64), nullable=False),
        sa.Column("line_color", sa.String(length=7), nullable=True),
        sa.Column("ui_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("placement_z", sa.Float(), nullable=False),
        sa.Column("param_values", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("param_meta", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("part_snapshots", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("viewer_boxes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="draft", nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("row_version", sa.Integer(), server_default="1", nullable=False),
        sa.ForeignKeyConstraint(["order_design_id"], ["order_designs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_instance_id"], ["sub_category_design_subtractor_instances.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["subtractor_part_group_id"], ["subtractor_part_groups.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_order_design_subtractor_instances_order_design_id"), "order_design_subtractor_instances", ["order_design_id"], unique=False)
    op.create_index(op.f("ix_order_design_subtractor_instances_source_instance_id"), "order_design_subtractor_instances", ["source_instance_id"], unique=False)
    op.create_index(op.f("ix_order_design_subtractor_instances_subtractor_part_group_id"), "order_design_subtractor_instances", ["subtractor_part_group_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_order_design_subtractor_instances_subtractor_part_group_id"), table_name="order_design_subtractor_instances")
    op.drop_index(op.f("ix_order_design_subtractor_instances_source_instance_id"), table_name="order_design_subtractor_instances")
    op.drop_index(op.f("ix_order_design_subtractor_instances_order_design_id"), table_name="order_design_subtractor_instances")
    op.drop_table("order_design_subtractor_instances")

    op.drop_index(op.f("ix_sub_category_design_subtractor_instances_subtractor_part_group_id"), table_name="sub_category_design_subtractor_instances")
    op.drop_index(op.f("ix_sub_category_design_subtractor_instances_design_id"), table_name="sub_category_design_subtractor_instances")
    op.drop_table("sub_category_design_subtractor_instances")
