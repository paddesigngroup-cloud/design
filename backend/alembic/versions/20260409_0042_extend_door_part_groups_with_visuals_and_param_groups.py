"""extend door part groups with visuals and param groups

Revision ID: 20260409_0042
Revises: 20260409_0041
Create Date: 2026-04-09 19:45:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260409_0042"
down_revision = "20260409_0041"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "door_part_groups",
        sa.Column("line_color", sa.String(length=7), nullable=False, server_default="#8A98A3"),
    )
    op.add_column(
        "door_part_groups",
        sa.Column("controller_bindings", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )

    op.create_table(
        "door_part_group_param_groups",
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
        sa.ForeignKeyConstraint(["group_ref_id"], ["door_part_groups.id"], name=op.f("fk_door_part_group_param_groups_group_ref_id_door_part_groups"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["param_group_id"], ["param_groups.param_group_id"], name=op.f("fk_door_part_group_param_groups_param_group_id_param_groups"), ondelete="RESTRICT", onupdate="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_door_part_group_param_groups")),
    )
    op.create_index(op.f("ix_door_part_group_param_groups_group_ref_id"), "door_part_group_param_groups", ["group_ref_id"], unique=False)
    op.create_index(op.f("ix_door_part_group_param_groups_param_group_id"), "door_part_group_param_groups", ["param_group_id"], unique=False)

    op.execute(
        """
        CREATE TRIGGER trg_door_part_group_param_groups_updated_at
        BEFORE UPDATE ON door_part_group_param_groups
        FOR EACH ROW
        EXECUTE FUNCTION public.set_row_updated_at();
        """
    )

    op.execute(
        """
        UPDATE door_part_groups
        SET controller_selection = NULL
        WHERE controller_selection IS NOT NULL;
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_door_part_group_param_groups_updated_at ON door_part_group_param_groups;")
    op.drop_index(op.f("ix_door_part_group_param_groups_param_group_id"), table_name="door_part_group_param_groups")
    op.drop_index(op.f("ix_door_part_group_param_groups_group_ref_id"), table_name="door_part_group_param_groups")
    op.drop_table("door_part_group_param_groups")
    op.drop_column("door_part_groups", "controller_bindings")
    op.drop_column("door_part_groups", "line_color")
