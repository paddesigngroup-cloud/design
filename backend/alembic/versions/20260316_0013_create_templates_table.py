"""create templates table

Revision ID: 20260316_0013
Revises: 20260316_0012
Create Date: 2026-03-16 03:30:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260316_0013"
down_revision = "20260316_0012"
branch_labels = None
depends_on = None


TEMPLATE_SEED_ROWS = [
    {
        "admin_id": None,
        "temp_id": 1,
        "temp_title": "کابینت",
        "code": "template_1",
        "title": "کابینت",
        "sort_order": 1,
        "is_system": True,
    },
]


def upgrade() -> None:
    op.create_table(
        "templates",
        sa.Column("admin_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("temp_id", sa.Integer(), nullable=True),
        sa.Column("temp_title", sa.String(length=255), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("is_system", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("timezone('utc', now())"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("timezone('utc', now())"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("row_version", sa.Integer(), server_default="1", nullable=False),
        sa.ForeignKeyConstraint(["admin_id"], ["admins.id"], name=op.f("fk_templates_admin_id_admins"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_templates")),
        sa.UniqueConstraint("temp_id", name=op.f("uq_templates_temp_id")),
    )
    op.create_index(op.f("ix_templates_admin_id"), "templates", ["admin_id"], unique=False)
    op.create_index(op.f("ix_templates_temp_id"), "templates", ["temp_id"], unique=False)
    op.create_index("uq_templates_system_title", "templates", ["temp_title"], unique=True, postgresql_where=sa.text("admin_id IS NULL"))
    op.create_index("uq_templates_admin_title", "templates", ["admin_id", "temp_title"], unique=True, postgresql_where=sa.text("admin_id IS NOT NULL"))

    templates_table = sa.table(
        "templates",
        sa.column("admin_id", postgresql.UUID(as_uuid=True)),
        sa.column("temp_id", sa.Integer()),
        sa.column("temp_title", sa.String(length=255)),
        sa.column("code", sa.String(length=64)),
        sa.column("title", sa.String(length=255)),
        sa.column("sort_order", sa.Integer()),
        sa.column("is_system", sa.Boolean()),
    )
    op.bulk_insert(templates_table, TEMPLATE_SEED_ROWS)


def downgrade() -> None:
    op.drop_index("uq_templates_admin_title", table_name="templates")
    op.drop_index("uq_templates_system_title", table_name="templates")
    op.drop_index(op.f("ix_templates_temp_id"), table_name="templates")
    op.drop_index(op.f("ix_templates_admin_id"), table_name="templates")
    op.drop_table("templates")
