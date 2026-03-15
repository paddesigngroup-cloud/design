"""align param_groups seed data with excel

Revision ID: 20260315_0009
Revises: 20260315_0008
Create Date: 2026-03-15 06:45:00
"""
from __future__ import annotations

from alembic import op


revision = "20260315_0009"
down_revision = "20260315_0008"
branch_labels = None
depends_on = None


UPDATES = [
    (1, "attributes", "ویژگی ها", 0, "attributes", "ویژگی ها", 1),
    (2, "thicknesses", "ضخامت ها", 1, "thicknesses", "ضخامت ها", 2),
    (3, "floor properties", "تنظیمات کف", 2, "floor properties", "تنظیمات کف", 3),
    (4, "roof properties", "تنظیمات تاق", 3, "roof properties", "تنظیمات تاق", 4),
    (5, "left side properties", "تنظیمات بدنه چپ", 4, "left side properties", "تنظیمات بدنه چپ", 5),
    (6, "right side properties", "تنظیمات بدنه راست", 5, "right side properties", "تنظیمات بدنه راست", 6),
    (7, "door properties", "تنظیمات درب", 6, "door properties", "تنظیمات درب", 7),
    (8, "back properties", "تنظیمات پشت", 7, "back properties", "تنظیمات پشت", 8),
    (9, "panel properties", "تنظیمات نما", 8, "panel properties", "تنظیمات نما", 9),
    (10, "gap properties", "تنظیمات گپ", 9, "gap properties", "تنظیمات گپ", 10),
    (11, "counter properties", "تنظیمات صفحه", 10, "counter properties", "تنظیمات صفحه", 11),
    (12, "stretcher properties", "تنضیمات قید", 11, "stretcher properties", "تنضیمات قید", 12),
    (13, "toe kick properties", "تنظیمات پاخور", 12, "toe kick properties", "تنظیمات پاخور", 13),
]

DOWNGRADE_CODE_FIXES = [
    (3, "floor_properties"),
    (4, "roof_properties"),
    (5, "left_side_properties"),
    (6, "right_side_properties"),
    (7, "door_properties"),
    (8, "back_properties"),
    (9, "panel_properties"),
    (10, "gap_properties"),
    (11, "counter_properties"),
    (12, "stretcher_properties"),
    (13, "toe_kick_properties"),
]


def upgrade() -> None:
    for param_group_id, param_group_code, org_title, ui_order, code, title, sort_order in UPDATES:
        op.execute(
            f"""
            UPDATE param_groups
            SET
                param_group_code = '{param_group_code}',
                org_param_group_title = '{org_title}',
                param_group_icon_path = NULL,
                ui_order = {ui_order},
                code = '{code}',
                title = '{title}',
                sort_order = {sort_order},
                is_system = true,
                admin_id = NULL
            WHERE param_group_id = {param_group_id}
            """
        )


def downgrade() -> None:
    for param_group_id, normalized_code in DOWNGRADE_CODE_FIXES:
        op.execute(
            f"""
            UPDATE param_groups
            SET
                param_group_code = '{normalized_code}',
                code = '{normalized_code}'
            WHERE param_group_id = {param_group_id}
            """
        )
