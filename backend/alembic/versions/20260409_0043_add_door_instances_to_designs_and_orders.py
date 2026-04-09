"""add door instances to designs and orders

Revision ID: 20260409_0043
Revises: 20260409_0042
Create Date: 2026-04-09 00:43:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "20260409_0043"
down_revision = "20260409_0042"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sub_category_design_door_instances",
        sa.Column("design_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("door_part_group_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("instance_code", sa.String(length=64), nullable=False),
        sa.Column("line_color", sa.String(length=7), nullable=True),
        sa.Column("ui_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("structural_part_formula_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("dependent_interior_instance_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("controller_box_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("param_values", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("param_meta", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("part_snapshots", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("viewer_boxes", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version_id", sa.Integer(), nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(["design_id"], ["sub_category_designs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["door_part_group_id"], ["door_part_groups.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_sub_category_design_door_instances_design_id"), "sub_category_design_door_instances", ["design_id"], unique=False)
    op.create_index(op.f("ix_sub_category_design_door_instances_door_part_group_id"), "sub_category_design_door_instances", ["door_part_group_id"], unique=False)

    op.create_table(
        "order_design_door_instances",
        sa.Column("order_design_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_instance_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("door_part_group_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("instance_code", sa.String(length=64), nullable=False),
        sa.Column("line_color", sa.String(length=7), nullable=True),
        sa.Column("ui_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("structural_part_formula_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("dependent_interior_instance_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("controller_box_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("param_values", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("param_meta", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("part_snapshots", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("viewer_boxes", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version_id", sa.Integer(), nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(["order_design_id"], ["order_designs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_instance_id"], ["sub_category_design_door_instances.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["door_part_group_id"], ["door_part_groups.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_order_design_door_instances_order_design_id"), "order_design_door_instances", ["order_design_id"], unique=False)
    op.create_index(op.f("ix_order_design_door_instances_source_instance_id"), "order_design_door_instances", ["source_instance_id"], unique=False)
    op.create_index(op.f("ix_order_design_door_instances_door_part_group_id"), "order_design_door_instances", ["door_part_group_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_order_design_door_instances_door_part_group_id"), table_name="order_design_door_instances")
    op.drop_index(op.f("ix_order_design_door_instances_source_instance_id"), table_name="order_design_door_instances")
    op.drop_index(op.f("ix_order_design_door_instances_order_design_id"), table_name="order_design_door_instances")
    op.drop_table("order_design_door_instances")
    op.drop_index(op.f("ix_sub_category_design_door_instances_door_part_group_id"), table_name="sub_category_design_door_instances")
    op.drop_index(op.f("ix_sub_category_design_door_instances_design_id"), table_name="sub_category_design_door_instances")
    op.drop_table("sub_category_design_door_instances")
