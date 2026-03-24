"""create order drawings table

Revision ID: 20260325_0025
Revises: 20260325_0024
Create Date: 2026-03-25 01:35:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260325_0025"
down_revision = "20260325_0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "order_drawings",
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("admin_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("drawing_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("walls_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("hidden_walls_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("dimensions_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("beams_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("columns_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("timezone('utc', now())")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("timezone('utc', now())")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("row_version", sa.Integer(), nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(["admin_id"], ["admins.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("order_id", name="uq_order_drawings_order_id"),
    )
    op.create_index(op.f("ix_order_drawings_order_id"), "order_drawings", ["order_id"], unique=False)
    op.create_index(op.f("ix_order_drawings_admin_id"), "order_drawings", ["admin_id"], unique=False)
    op.create_index(op.f("ix_order_drawings_user_id"), "order_drawings", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_order_drawings_user_id"), table_name="order_drawings")
    op.drop_index(op.f("ix_order_drawings_admin_id"), table_name="order_drawings")
    op.drop_index(op.f("ix_order_drawings_order_id"), table_name="order_drawings")
    op.drop_table("order_drawings")
