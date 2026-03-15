"""fix order tenant integrity and part kind admin naming

Revision ID: 20260315_0006
Revises: 20260315_0005
Create Date: 2026-03-15 02:30:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260315_0006"
down_revision = "20260315_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint("uq_users_id_admin_id", "users", ["id", "admin_id"])

    op.create_foreign_key(
        "fk_orders_user_id_admin_id_users",
        "orders",
        "users",
        ["user_id", "admin_id"],
        ["id", "admin_id"],
        ondelete="RESTRICT",
    )

    op.execute("UPDATE part_kinds SET admin_id = COALESCE(admin_id, admin_user_id);")

    op.drop_index("uq_part_kinds_admin_part_kind_code", table_name="part_kinds")
    op.drop_index("uq_part_kinds_system_part_kind_code", table_name="part_kinds")
    op.drop_index(op.f("ix_part_kinds_admin_user_id"), table_name="part_kinds")
    op.drop_constraint(op.f("fk_part_kinds_admin_user_id_admins"), "part_kinds", type_="foreignkey")
    op.drop_column("part_kinds", "admin_user_id")

    op.create_index(
        "uq_part_kinds_system_part_kind_code",
        "part_kinds",
        ["part_kind_code"],
        unique=True,
        postgresql_where=sa.text("admin_id IS NULL"),
    )
    op.create_index(
        "uq_part_kinds_admin_part_kind_code",
        "part_kinds",
        ["admin_id", "part_kind_code"],
        unique=True,
        postgresql_where=sa.text("admin_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.add_column("part_kinds", sa.Column("admin_user_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.execute("UPDATE part_kinds SET admin_user_id = admin_id;")
    op.create_foreign_key(
        op.f("fk_part_kinds_admin_user_id_admins"),
        "part_kinds",
        "admins",
        ["admin_user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(op.f("ix_part_kinds_admin_user_id"), "part_kinds", ["admin_user_id"], unique=False)

    op.drop_index("uq_part_kinds_admin_part_kind_code", table_name="part_kinds")
    op.drop_index("uq_part_kinds_system_part_kind_code", table_name="part_kinds")

    op.create_index(
        "uq_part_kinds_system_part_kind_code",
        "part_kinds",
        ["part_kind_code"],
        unique=True,
        postgresql_where=sa.text("admin_user_id IS NULL"),
    )
    op.create_index(
        "uq_part_kinds_admin_part_kind_code",
        "part_kinds",
        ["admin_user_id", "part_kind_code"],
        unique=True,
        postgresql_where=sa.text("admin_user_id IS NOT NULL"),
    )

    op.drop_constraint("fk_orders_user_id_admin_id_users", "orders", type_="foreignkey")
    op.drop_constraint("uq_users_id_admin_id", "users", type_="unique")
