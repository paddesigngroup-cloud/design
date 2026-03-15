"""create account tables

Revision ID: 20260315_0002
Revises: 20260315_0001
Create Date: 2026-03-15 00:30:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260315_0002"
down_revision = "20260315_0001"
branch_labels = None
depends_on = None


def _attach_updated_at_trigger(table_name: str) -> None:
    op.execute(
        f"""
        CREATE TRIGGER trg_{table_name}_updated_at
        BEFORE UPDATE ON {table_name}
        FOR EACH ROW
        EXECUTE FUNCTION public.set_row_updated_at();
        """
    )


def _drop_updated_at_trigger(table_name: str) -> None:
    op.execute(f"DROP TRIGGER IF EXISTS trg_{table_name}_updated_at ON {table_name};")


def upgrade() -> None:
    op.create_table(
        "super_admins",
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("timezone('utc', now())"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("timezone('utc', now())"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("row_version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_super_admins")),
        sa.UniqueConstraint("email", name=op.f("uq_super_admins_email")),
    )
    op.create_index(op.f("ix_super_admins_email"), "super_admins", ["email"], unique=False)

    op.create_table(
        "admins",
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("timezone('utc', now())"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("timezone('utc', now())"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("row_version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_admins")),
        sa.UniqueConstraint("email", name=op.f("uq_admins_email")),
    )
    op.create_index(op.f("ix_admins_email"), "admins", ["email"], unique=False)

    op.create_table(
        "users",
        sa.Column("admin_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("timezone('utc', now())"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("timezone('utc', now())"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("row_version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.ForeignKeyConstraint(["admin_id"], ["admins.id"], name=op.f("fk_users_admin_id_admins"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
    )
    op.create_index(op.f("ix_users_admin_id"), "users", ["admin_id"], unique=False)
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=False)

    _attach_updated_at_trigger("super_admins")
    _attach_updated_at_trigger("admins")
    _attach_updated_at_trigger("users")


def downgrade() -> None:
    _drop_updated_at_trigger("users")
    _drop_updated_at_trigger("admins")
    _drop_updated_at_trigger("super_admins")

    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_index(op.f("ix_users_admin_id"), table_name="users")
    op.drop_table("users")

    op.drop_index(op.f("ix_admins_email"), table_name="admins")
    op.drop_table("admins")

    op.drop_index(op.f("ix_super_admins_email"), table_name="super_admins")
    op.drop_table("super_admins")
