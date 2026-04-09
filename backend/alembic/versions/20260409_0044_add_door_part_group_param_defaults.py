"""add defaults for door part group params

Revision ID: 20260409_0044
Revises: 20260409_0043
Create Date: 2026-04-09 22:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260409_0044"
down_revision = "20260409_0043"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "door_part_group_param_defaults",
        sa.Column("door_part_group_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("param_id", sa.Integer(), nullable=False),
        sa.Column("default_value", sa.Text(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("timezone('utc', now())"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("timezone('utc', now())"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("row_version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.ForeignKeyConstraint(
            ["door_part_group_id"],
            ["door_part_groups.id"],
            name=op.f("fk_door_part_group_param_defaults_door_part_group_id_door_part_groups"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["param_id"],
            ["params.param_id"],
            name=op.f("fk_door_part_group_param_defaults_param_id_params"),
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_door_part_group_param_defaults")),
    )
    op.create_index(
        op.f("ix_door_part_group_param_defaults_door_part_group_id"),
        "door_part_group_param_defaults",
        ["door_part_group_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_door_part_group_param_defaults_param_id"),
        "door_part_group_param_defaults",
        ["param_id"],
        unique=False,
    )
    op.execute(
        """
        CREATE TRIGGER trg_door_part_group_param_defaults_updated_at
        BEFORE UPDATE ON door_part_group_param_defaults
        FOR EACH ROW
        EXECUTE FUNCTION public.set_row_updated_at();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_door_part_group_param_defaults_updated_at ON door_part_group_param_defaults;")
    op.drop_index(op.f("ix_door_part_group_param_defaults_param_id"), table_name="door_part_group_param_defaults")
    op.drop_index(op.f("ix_door_part_group_param_defaults_door_part_group_id"), table_name="door_part_group_param_defaults")
    op.drop_table("door_part_group_param_defaults")
