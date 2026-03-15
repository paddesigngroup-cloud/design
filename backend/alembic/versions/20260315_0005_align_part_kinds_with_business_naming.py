"""align part kinds with business naming

Revision ID: 20260315_0005
Revises: 20260315_0004
Create Date: 2026-03-15 02:00:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260315_0005"
down_revision = "20260315_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("part_kinds", sa.Column("admin_user_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("part_kinds", sa.Column("part_kind_id", sa.Integer(), nullable=True))
    op.add_column("part_kinds", sa.Column("part_kind_code", sa.String(length=64), nullable=True))
    op.add_column("part_kinds", sa.Column("org_part_kind_title", sa.String(length=255), nullable=True))

    op.create_foreign_key(
        op.f("fk_part_kinds_admin_user_id_admins"),
        "part_kinds",
        "admins",
        ["admin_user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(op.f("ix_part_kinds_admin_user_id"), "part_kinds", ["admin_user_id"], unique=False)
    op.create_index(op.f("ix_part_kinds_part_kind_id"), "part_kinds", ["part_kind_id"], unique=True)

    op.execute("UPDATE part_kinds SET admin_user_id = admin_id;")
    op.execute("UPDATE part_kinds SET part_kind_code = code;")
    op.execute("UPDATE part_kinds SET org_part_kind_title = title;")

    op.execute(
        """
        UPDATE part_kinds
        SET part_kind_id = CASE code
            WHEN 'unit' THEN 1
            WHEN 'stretcher' THEN 2
            WHEN 'shelf' THEN 3
            WHEN 'drawer' THEN 4
            WHEN 'partition' THEN 5
            WHEN 'door' THEN 6
            WHEN 'face_panel' THEN 7
            WHEN 'toe_kick' THEN 8
            WHEN 'frame' THEN 9
            ELSE NULL
        END;
        """
    )

    op.alter_column("part_kinds", "part_kind_id", nullable=False)
    op.alter_column("part_kinds", "part_kind_code", nullable=False)
    op.alter_column("part_kinds", "org_part_kind_title", nullable=False)

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


def downgrade() -> None:
    op.drop_index("uq_part_kinds_admin_part_kind_code", table_name="part_kinds")
    op.drop_index("uq_part_kinds_system_part_kind_code", table_name="part_kinds")
    op.drop_index(op.f("ix_part_kinds_part_kind_id"), table_name="part_kinds")
    op.drop_index(op.f("ix_part_kinds_admin_user_id"), table_name="part_kinds")
    op.drop_constraint(op.f("fk_part_kinds_admin_user_id_admins"), "part_kinds", type_="foreignkey")
    op.drop_column("part_kinds", "org_part_kind_title")
    op.drop_column("part_kinds", "part_kind_code")
    op.drop_column("part_kinds", "part_kind_id")
    op.drop_column("part_kinds", "admin_user_id")
