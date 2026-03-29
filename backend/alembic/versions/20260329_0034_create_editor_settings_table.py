"""create editor settings table

Revision ID: 20260329_0034
Revises: 20260326_0033
Create Date: 2026-03-29 03:20:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260329_0034"
down_revision = "20260326_0033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "editor_settings",
        sa.Column("admin_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("general_settings", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("grid_settings", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("snap_settings", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("drafting_settings", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("wall_defaults", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("beam_defaults", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("column_defaults", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("hidden_defaults", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("dimension_defaults", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("angle_defaults", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("offset_wall_settings", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("timezone('utc', now())")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("timezone('utc', now())")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("row_version", sa.Integer(), nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(["admin_id"], ["admins.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("admin_id", "user_id", name="uq_editor_settings_admin_user"),
    )
    op.create_index(op.f("ix_editor_settings_admin_id"), "editor_settings", ["admin_id"], unique=False)
    op.create_index(op.f("ix_editor_settings_user_id"), "editor_settings", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_editor_settings_user_id"), table_name="editor_settings")
    op.drop_index(op.f("ix_editor_settings_admin_id"), table_name="editor_settings")
    op.drop_table("editor_settings")
