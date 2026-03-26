"""backfill order design snapshot checksum state in metadata

Revision ID: 20260326_0033
Revises: 20260326_0032
Create Date: 2026-03-26 10:30:00
"""
from __future__ import annotations

from alembic import op


revision = "20260326_0033"
down_revision = "20260326_0032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE order_designs AS od
        SET order_attr_meta = jsonb_set(
            coalesce(od.order_attr_meta, '{}'::jsonb),
            '{__snapshot_state}',
            jsonb_build_object(
                'version', 1,
                'checksum', md5(
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
            ),
            true
        )
        WHERE coalesce(od.order_attr_meta, '{}'::jsonb) ? '__snapshot_state' = false
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE order_designs
        SET order_attr_meta = coalesce(order_attr_meta, '{}'::jsonb) - '__snapshot_state'
        WHERE coalesce(order_attr_meta, '{}'::jsonb) ? '__snapshot_state'
        """
    )
