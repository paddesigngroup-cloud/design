"""sync catalog seed snapshots with current csv

Revision ID: 20260323_0018
Revises: 20260316_0017
Create Date: 2026-03-23 12:00:00
"""

from __future__ import annotations

import csv
from pathlib import Path

from alembic import op
import sqlalchemy as sa


revision = "20260323_0018"
down_revision = "20260316_0017"
branch_labels = None
depends_on = None


DATA_DIR = (
    Path(__file__).resolve().parents[3]
    / "data"
    / "admins"
    / "00000000-0000-0000-0000-000000000001"
    / "tables"
)

LEGACY_PARAM_CODE_BY_CURRENT_CODE = {
    "t_fr_h_st_w": "w_st",
    "l_to_ba_v_st": "l_to_v_st",
    "r_to_ba_v_st": "r_to_v_st",
    "p_b_to_ba_v_st": "p_b_to_v_st",
    "p_d_to_ba_v_st": "p_d_to_v_st",
    "l_bo_ba_v_st": "l_bo_v_st",
    "r_bo_ba_v_st": "r_bo_v_st",
    "p_b_bo_ba_v_st": "p_b_bo_v_st",
    "p_u_bo_ba_v_st": "p_u_bo_v_st",
    "dr_b_h": "dr_h",
    "le_ri_s_dr_th": "dr_th_si",
    "fr_ba_s_dr_th": "dr_th_str",
    "bo_dr_th": "dr_th_bo",
    "le_f_s_dr": "le_f_d",
    "ri_f_s_dr": "ri_f_d",
    "p_t_f_s_dr": "p_t_f_d",
    "p_b_f_s_dr": "p_b_f_d",
}


def _load_csv(name: str) -> list[dict[str, str]]:
    with (DATA_DIR / name).open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _normalize_nullable_text(value: str | None) -> str | None:
    text = (value or "").strip()
    return text or None


def _sync_param_groups() -> None:
    rows = _load_csv("param_groups.csv")
    conn = op.get_bind()
    for index, row in enumerate(rows, start=1):
        conn.execute(
            sa.text(
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
                VALUES (
                    NULL,
                    :param_group_id,
                    :param_group_code,
                    :org_param_group_title,
                    :param_group_icon_path,
                    :ui_order,
                    :param_group_code,
                    :org_param_group_title,
                    :sort_order,
                    true
                )
                ON CONFLICT (param_group_id) DO UPDATE SET
                    admin_id = NULL,
                    param_group_code = EXCLUDED.param_group_code,
                    org_param_group_title = EXCLUDED.org_param_group_title,
                    param_group_icon_path = EXCLUDED.param_group_icon_path,
                    ui_order = EXCLUDED.ui_order,
                    code = EXCLUDED.code,
                    title = EXCLUDED.title,
                    sort_order = EXCLUDED.sort_order,
                    is_system = true
                """
            ),
            {
                "param_group_id": int(row["param_group_id"]),
                "param_group_code": row["param_group_code"].strip(),
                "org_param_group_title": row["org_param_group_title"].strip(),
                "param_group_icon_path": _normalize_nullable_text(row.get("param_group_icon_path")),
                "ui_order": int(row["ui_order"]),
                "sort_order": index,
            },
        )


def _find_system_row_id(table_name: str, code_column: str, code: str, legacy_code: str | None = None) -> str | None:
    conn = op.get_bind()
    for candidate in [code, legacy_code]:
        if not candidate:
            continue
        row = conn.execute(
            sa.text(
                f"""
                SELECT id
                FROM {table_name}
                WHERE admin_id IS NULL AND {code_column} = :code
                LIMIT 1
                """
            ),
            {"code": candidate},
        ).scalar_one_or_none()
        if row is not None:
            return str(row)
    return None


def _sync_params() -> None:
    rows = _load_csv("params.csv")
    conn = op.get_bind()
    conn.execute(sa.text("UPDATE params SET param_id = param_id + 1000 WHERE admin_id IS NULL"))
    for row in rows:
        param_code = row["param_code"].strip()
        row_id = _find_system_row_id("params", "param_code", param_code, LEGACY_PARAM_CODE_BY_CURRENT_CODE.get(param_code))
        payload = {
            "param_id": int(row["param_id"]),
            "part_kind_id": int(row["part_kind_id"]),
            "param_code": param_code,
            "param_title_en": row["param_title_en"].strip(),
            "param_title_fa": row["param_title_fa"].strip(),
            "param_group_id": int(row["param_group_id"]),
            "ui_order": int(row["ui_order"]),
            "code": param_code,
            "title": row["param_title_fa"].strip(),
            "sort_order": int(row["param_id"]),
        }
        if row_id:
            conn.execute(
                sa.text(
                    """
                    UPDATE params
                    SET
                        admin_id = NULL,
                        param_id = :param_id,
                        part_kind_id = :part_kind_id,
                        param_code = :param_code,
                        param_title_en = :param_title_en,
                        param_title_fa = :param_title_fa,
                        param_group_id = :param_group_id,
                        ui_order = :ui_order,
                        code = :code,
                        title = :title,
                        sort_order = :sort_order,
                        is_system = true
                    WHERE id = :id
                    """
                ),
                payload | {"id": row_id},
            )
        else:
            conn.execute(
                sa.text(
                    """
                    INSERT INTO params (
                        admin_id,
                        param_id,
                        part_kind_id,
                        param_code,
                        param_title_en,
                        param_title_fa,
                        param_group_id,
                        ui_order,
                        code,
                        title,
                        sort_order,
                        is_system
                    )
                    VALUES (
                        NULL,
                        :param_id,
                        :part_kind_id,
                        :param_code,
                        :param_title_en,
                        :param_title_fa,
                        :param_group_id,
                        :ui_order,
                        :code,
                        :title,
                        :sort_order,
                        true
                    )
                    """
                ),
                payload,
            )
    conn.execute(sa.text("DELETE FROM params WHERE admin_id IS NULL AND param_id >= 1000"))


def _sync_base_formulas() -> None:
    rows = _load_csv("base_formulas.csv")
    conn = op.get_bind()
    conn.execute(sa.text("UPDATE base_formulas SET fo_id = fo_id + 1000 WHERE admin_id IS NULL"))
    for row in rows:
        formula_code = row["param_formula"].strip()
        row_id = _find_system_row_id("base_formulas", "param_formula", formula_code)
        payload = {
            "fo_id": int(row["fo_id"]),
            "param_formula": formula_code,
            "formula": row["formula"].strip(),
            "code": formula_code,
            "title": formula_code,
            "sort_order": int(row["fo_id"]),
        }
        if row_id:
            conn.execute(
                sa.text(
                    """
                    UPDATE base_formulas
                    SET
                        admin_id = NULL,
                        fo_id = :fo_id,
                        param_formula = :param_formula,
                        formula = :formula,
                        code = :code,
                        title = :title,
                        sort_order = :sort_order,
                        is_system = true
                    WHERE id = :id
                    """
                ),
                payload | {"id": row_id},
            )
        else:
            conn.execute(
                sa.text(
                    """
                    INSERT INTO base_formulas (
                        admin_id,
                        fo_id,
                        param_formula,
                        formula,
                        code,
                        title,
                        sort_order,
                        is_system
                    )
                    VALUES (
                        NULL,
                        :fo_id,
                        :param_formula,
                        :formula,
                        :code,
                        :title,
                        :sort_order,
                        true
                    )
                    """
                ),
                payload,
            )
    conn.execute(sa.text("DELETE FROM base_formulas WHERE admin_id IS NULL AND fo_id >= 1000"))


def _sync_part_formulas() -> None:
    rows = _load_csv("part_formulas.csv")
    conn = op.get_bind()
    conn.execute(sa.text("UPDATE part_formulas SET part_formula_id = part_formula_id + 1000 WHERE admin_id IS NULL"))
    for row in rows:
        part_code = row["part_code"].strip()
        row_id = _find_system_row_id("part_formulas", "part_code", part_code)
        payload = {
            "part_formula_id": int(row["part_formula_id"]),
            "part_kind_id": int(row["part_kind_id"]),
            "part_sub_kind_id": int(row["part_sub_kind_id"]),
            "part_code": part_code,
            "part_title": row["part_title"].strip(),
            "formula_l": row["formula_l"].strip(),
            "formula_w": row["formula_w"].strip(),
            "formula_width": row["formula_width"].strip(),
            "formula_depth": row["formula_depth"].strip(),
            "formula_height": row["formula_height"].strip(),
            "formula_cx": row["formula_cx"].strip(),
            "formula_cy": row["formula_cy"].strip(),
            "formula_cz": row["formula_cz"].strip(),
            "code": part_code,
            "title": row["part_title"].strip(),
            "sort_order": int(row["part_formula_id"]),
        }
        if row_id:
            conn.execute(
                sa.text(
                    """
                    UPDATE part_formulas
                    SET
                        admin_id = NULL,
                        part_formula_id = :part_formula_id,
                        part_kind_id = :part_kind_id,
                        part_sub_kind_id = :part_sub_kind_id,
                        part_code = :part_code,
                        part_title = :part_title,
                        formula_l = :formula_l,
                        formula_w = :formula_w,
                        formula_width = :formula_width,
                        formula_depth = :formula_depth,
                        formula_height = :formula_height,
                        formula_cx = :formula_cx,
                        formula_cy = :formula_cy,
                        formula_cz = :formula_cz,
                        code = :code,
                        title = :title,
                        sort_order = :sort_order,
                        is_system = true
                    WHERE id = :id
                    """
                ),
                payload | {"id": row_id},
            )
        else:
            conn.execute(
                sa.text(
                    """
                    INSERT INTO part_formulas (
                        admin_id,
                        part_formula_id,
                        part_kind_id,
                        part_sub_kind_id,
                        part_code,
                        part_title,
                        formula_l,
                        formula_w,
                        formula_width,
                        formula_depth,
                        formula_height,
                        formula_cx,
                        formula_cy,
                        formula_cz,
                        code,
                        title,
                        sort_order,
                        is_system
                    )
                    VALUES (
                        NULL,
                        :part_formula_id,
                        :part_kind_id,
                        :part_sub_kind_id,
                        :part_code,
                        :part_title,
                        :formula_l,
                        :formula_w,
                        :formula_width,
                        :formula_depth,
                        :formula_height,
                        :formula_cx,
                        :formula_cy,
                        :formula_cz,
                        :code,
                        :title,
                        :sort_order,
                        true
                    )
                    """
                ),
                payload,
            )
    conn.execute(sa.text("DELETE FROM part_formulas WHERE admin_id IS NULL AND part_formula_id >= 1000"))


def upgrade() -> None:
    _sync_param_groups()
    _sync_params()
    _sync_base_formulas()
    _sync_part_formulas()


def downgrade() -> None:
    raise RuntimeError("Downgrade is not supported for 20260323_0018 because it normalizes live catalog data.")
