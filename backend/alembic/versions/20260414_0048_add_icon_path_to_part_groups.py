"""add icon path to internal and door part groups

Revision ID: 20260414_0048
Revises: 20260411_0047
Create Date: 2026-04-14 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260414_0048"
down_revision = "20260411_0047"
branch_labels = None
depends_on = None


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    if not _has_column("internal_part_groups", "icon_path"):
        op.add_column("internal_part_groups", sa.Column("icon_path", sa.String(length=255), nullable=True))

    if not _has_column("door_part_groups", "icon_path"):
        op.add_column("door_part_groups", sa.Column("icon_path", sa.String(length=255), nullable=True))


def downgrade() -> None:
    if _has_column("door_part_groups", "icon_path"):
        op.drop_column("door_part_groups", "icon_path")

    if _has_column("internal_part_groups", "icon_path"):
        op.drop_column("internal_part_groups", "icon_path")
