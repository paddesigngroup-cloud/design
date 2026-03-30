"""add defaults for internal part group params

Revision ID: 20260330_0038
Revises: 20260330_0037
Create Date: 2026-03-30 11:35:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260330_0038"
down_revision = "20260330_0037"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "internal_part_group_param_defaults",
        sa.Column("internal_part_group_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("param_id", sa.Integer(), nullable=False),
        sa.Column("default_value", sa.Text(), nullable=True),
        sa.Column("display_title", sa.String(length=255), nullable=True),
        sa.Column("description_text", sa.Text(), nullable=True),
        sa.Column("icon_path", sa.String(length=255), nullable=True),
        sa.Column("input_mode", sa.String(length=16), server_default=sa.text("'value'"), nullable=False),
        sa.Column("binary_off_label", sa.String(length=255), nullable=True),
        sa.Column("binary_on_label", sa.String(length=255), nullable=True),
        sa.Column("binary_off_icon_path", sa.String(length=255), nullable=True),
        sa.Column("binary_on_icon_path", sa.String(length=255), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("timezone('utc', now())"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("timezone('utc', now())"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("row_version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.ForeignKeyConstraint(
            ["internal_part_group_id"],
            ["internal_part_groups.id"],
            name=op.f("fk_internal_part_group_param_defaults_internal_part_group_id_internal_part_groups"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["param_id"],
            ["params.param_id"],
            name=op.f("fk_internal_part_group_param_defaults_param_id_params"),
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_internal_part_group_param_defaults")),
    )
    op.create_index(
        op.f("ix_internal_part_group_param_defaults_internal_part_group_id"),
        "internal_part_group_param_defaults",
        ["internal_part_group_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_internal_part_group_param_defaults_param_id"),
        "internal_part_group_param_defaults",
        ["param_id"],
        unique=False,
    )
    op.execute(
        """
        CREATE TRIGGER trg_internal_part_group_param_defaults_updated_at
        BEFORE UPDATE ON internal_part_group_param_defaults
        FOR EACH ROW
        EXECUTE FUNCTION public.set_row_updated_at();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_internal_part_group_param_defaults_updated_at ON internal_part_group_param_defaults;")
    op.drop_index(op.f("ix_internal_part_group_param_defaults_param_id"), table_name="internal_part_group_param_defaults")
    op.drop_index(op.f("ix_internal_part_group_param_defaults_internal_part_group_id"), table_name="internal_part_group_param_defaults")
    op.drop_table("internal_part_group_param_defaults")
