"""add snapshot checksum to order designs

Revision ID: 20260326_0032
Revises: 20260325_0031
Create Date: 2026-03-26 09:00:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260326_0032"
down_revision = "20260325_0031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "order_designs",
        sa.Column("snapshot_checksum", sa.String(length=64), nullable=False, server_default=""),
    )
    op.execute(
        """
        UPDATE order_designs AS od
        SET snapshot_checksum = md5(
            coalesce(od.sub_category_design_id::text, '') || '|' ||
            coalesce(od.order_attr_values::text, '{}') || '|' ||
            coalesce((
                SELECT string_agg(
                    coalesce(odi.instance_code, '') || ':' ||
                    coalesce(odi.param_values::text, '{}') || ':' ||
                    coalesce(odi.ui_order::text, '0') || ':' ||
                    coalesce(odi.placement_z::text, '0'),
                    '|' ORDER BY odi.ui_order, odi.instance_code, odi.id::text
                )
                FROM order_design_interior_instances AS odi
                WHERE odi.order_design_id = od.id AND odi.deleted_at IS NULL
            ), '')
        )
        WHERE coalesce(od.snapshot_checksum, '') = ''
        """
    )


def downgrade() -> None:
    op.drop_column("order_designs", "snapshot_checksum")
