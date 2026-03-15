"""create param_groups table

Revision ID: 20260315_0008
Revises: 20260315_0007
Create Date: 2026-03-15 06:20:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260315_0008"
down_revision = "20260315_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "param_groups",
        sa.Column("admin_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("param_group_id", sa.Integer(), nullable=True),
        sa.Column("param_group_code", sa.String(length=64), nullable=True),
        sa.Column("org_param_group_title", sa.String(length=255), nullable=True),
        sa.Column("param_group_icon_path", sa.String(length=255), nullable=True),
        sa.Column("ui_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("is_system", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("timezone('utc', now())"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("timezone('utc', now())"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("row_version", sa.Integer(), server_default="1", nullable=False),
        sa.ForeignKeyConstraint(["admin_id"], ["admins.id"], name=op.f("fk_param_groups_admin_id_admins"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_param_groups")),
        sa.UniqueConstraint("param_group_id", name=op.f("uq_param_groups_param_group_id")),
    )
    op.create_index(op.f("ix_param_groups_admin_id"), "param_groups", ["admin_id"], unique=False)
    op.create_index(op.f("ix_param_groups_param_group_id"), "param_groups", ["param_group_id"], unique=False)

    op.execute(
        """
        INSERT INTO param_groups (
            admin_id,
            param_group_id,
            param_group_code,
            org_param_group_title,
            param_group_icon_path,
            ui_order,
            code,
            title,
            sort_order,
            is_system
        )
        VALUES
            (NULL, 1,  'attributes',              'ویژگی ها',            NULL, 0,  'attributes',              'ویژگی ها',            1,  true),
            (NULL, 2,  'thicknesses',            'ضخامت ها',            NULL, 1,  'thicknesses',            'ضخامت ها',            2,  true),
            (NULL, 3,  'floor_properties',       'تنظیمات کف',          NULL, 2,  'floor_properties',       'تنظیمات کف',          3,  true),
            (NULL, 4,  'roof_properties',        'تنظیمات تاق',         NULL, 3,  'roof_properties',        'تنظیمات تاق',         4,  true),
            (NULL, 5,  'left_side_properties',   'تنظیمات بدنه چپ',     NULL, 4,  'left_side_properties',   'تنظیمات بدنه چپ',     5,  true),
            (NULL, 6,  'right_side_properties',  'تنظیمات بدنه راست',   NULL, 5,  'right_side_properties',  'تنظیمات بدنه راست',   6,  true),
            (NULL, 7,  'door_properties',        'تنظیمات درب',         NULL, 6,  'door_properties',        'تنظیمات درب',         7,  true),
            (NULL, 8,  'back_properties',        'تنظیمات پشت',         NULL, 7,  'back_properties',        'تنظیمات پشت',         8,  true),
            (NULL, 9,  'panel_properties',       'تنظیمات نما',         NULL, 8,  'panel_properties',       'تنظیمات نما',         9,  true),
            (NULL, 10, 'gap_properties',         'تنظیمات گپ',          NULL, 9,  'gap_properties',         'تنظیمات گپ',          10, true),
            (NULL, 11, 'counter_properties',     'تنظیمات صفحه',        NULL, 10, 'counter_properties',     'تنظیمات صفحه',        11, true),
            (NULL, 12, 'stretcher_properties',   'تنضیمات قید',         NULL, 11, 'stretcher_properties',   'تنضیمات قید',         12, true),
            (NULL, 13, 'toe_kick_properties',    'تنظیمات پاخور',       NULL, 12, 'toe_kick_properties',    'تنظیمات پاخور',       13, true);
        """
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_param_groups_param_group_id"), table_name="param_groups")
    op.drop_index(op.f("ix_param_groups_admin_id"), table_name="param_groups")
    op.drop_table("param_groups")
