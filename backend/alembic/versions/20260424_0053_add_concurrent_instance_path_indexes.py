"""add concurrent partial indexes for design instance save paths

Revision ID: 20260424_0053
Revises: 20260423_0052
Create Date: 2026-04-24 12:00:00
"""

from __future__ import annotations

from alembic import op


revision = "20260424_0053"
down_revision = "20260423_0052"
branch_labels = None
depends_on = None


def _create_concurrent_index(sql: str) -> None:
    with op.get_context().autocommit_block():
        op.execute(sql)


def _drop_concurrent_index(sql: str) -> None:
    with op.get_context().autocommit_block():
        op.execute(sql)


def upgrade() -> None:
    _create_concurrent_index(
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_odii_parent_code_order_live "
        "ON order_design_interior_instances (order_design_id, instance_code, ui_order) "
        "WHERE deleted_at IS NULL"
    )
    _create_concurrent_index(
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_oddi_parent_code_order_live "
        "ON order_design_door_instances (order_design_id, instance_code, ui_order) "
        "WHERE deleted_at IS NULL"
    )
    _create_concurrent_index(
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_odsi_parent_code_order_live "
        "ON order_design_subtractor_instances (order_design_id, instance_code, ui_order) "
        "WHERE deleted_at IS NULL"
    )
    _create_concurrent_index(
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_scdii_parent_code_order_live "
        "ON sub_category_design_interior_instances (design_id, instance_code, ui_order) "
        "WHERE deleted_at IS NULL"
    )
    _create_concurrent_index(
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_scddi_parent_code_order_live "
        "ON sub_category_design_door_instances (design_id, instance_code, ui_order) "
        "WHERE deleted_at IS NULL"
    )
    _create_concurrent_index(
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_scdsi_parent_code_order_live "
        "ON sub_category_design_subtractor_instances (design_id, instance_code, ui_order) "
        "WHERE deleted_at IS NULL"
    )


def downgrade() -> None:
    _drop_concurrent_index("DROP INDEX CONCURRENTLY IF EXISTS ix_scdsi_parent_code_order_live")
    _drop_concurrent_index("DROP INDEX CONCURRENTLY IF EXISTS ix_scddi_parent_code_order_live")
    _drop_concurrent_index("DROP INDEX CONCURRENTLY IF EXISTS ix_scdii_parent_code_order_live")
    _drop_concurrent_index("DROP INDEX CONCURRENTLY IF EXISTS ix_odsi_parent_code_order_live")
    _drop_concurrent_index("DROP INDEX CONCURRENTLY IF EXISTS ix_oddi_parent_code_order_live")
    _drop_concurrent_index("DROP INDEX CONCURRENTLY IF EXISTS ix_odii_parent_code_order_live")
