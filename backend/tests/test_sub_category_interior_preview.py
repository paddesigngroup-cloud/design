from __future__ import annotations

import asyncio
from types import SimpleNamespace
from uuid import uuid4

from designkp_backend.services import sub_category_designs as service


def test_resolve_internal_instance_preview_falls_back_to_sub_category_defaults(monkeypatch) -> None:
    async def fake_get_sub_category_resolved_params(_session, _sub_category):
        raw = {
            "l_fl": "1",
            "r_fl": "1",
            "le_p": "0",
            "ri_p": "0",
            "p_th": "16",
            "u_th": "16",
            "le_g": "0",
            "ri_g": "0",
            "le_n": "0",
            "ri_n": "0",
        }
        numeric = {key: float(value) for key, value in raw.items()}
        return raw, numeric

    async def fake_collect_internal_group_param_codes(_session, **_kwargs):
        return {"u_th"}

    async def fake_build_internal_group_param_display_snapshot(_session, **_kwargs):
        return (
            {"u_th": "18"},
            {
                "u_th": {
                    "label": "ضخامت یونیت",
                    "group_id": 1,
                    "group_title": "گروه داخلی",
                    "group_ui_order": 1,
                    "param_ui_order": 1,
                }
            },
        )

    async def fake_get_auto_param_codes(_session, **_kwargs):
        return set()

    async def fake_list_accessible_base_formulas(_session, **_kwargs):
        return [
            SimpleNamespace(
                sort_order=1,
                fo_id=1,
                param_formula="f1",
                formula="((l_fl)*(u_th))+((r_fl)*(u_th))+((le_p)*(p_th))+((ri_p)*(p_th))+(le_g)+(ri_g)+(le_n)+(ri_n)",
            )
        ]

    async def fake_require_accessible_part_formulas(_session, **_kwargs):
        return [
            SimpleNamespace(
                part_formula_id=101,
                part_kind_id=201,
                part_code="inner-panel",
                part_title="قطعه داخلی",
                formula_l="0",
                formula_w="0",
                formula_width="f1",
                formula_depth="100",
                formula_height="50",
                formula_cx="0",
                formula_cy="0",
                formula_cz="0",
            )
        ]

    monkeypatch.setattr(service, "get_sub_category_resolved_params", fake_get_sub_category_resolved_params)
    monkeypatch.setattr(service, "collect_internal_group_param_codes", fake_collect_internal_group_param_codes)
    monkeypatch.setattr(service, "build_internal_group_param_display_snapshot", fake_build_internal_group_param_display_snapshot)
    monkeypatch.setattr(service, "get_auto_param_codes", fake_get_auto_param_codes)
    monkeypatch.setattr(service, "list_accessible_base_formulas", fake_list_accessible_base_formulas)
    monkeypatch.setattr(service, "require_accessible_part_formulas", fake_require_accessible_part_formulas)

    internal_group = SimpleNamespace(
        id=uuid4(),
        code="inner-group",
        group_title="گروه داخلی",
        title="گروه داخلی",
    )
    internal_group.__dict__["parts"] = [SimpleNamespace(part_formula_id=101, enabled=True, ui_order=0)]

    result = asyncio.run(
        service.resolve_internal_instance_preview(
            None,
            admin_id=uuid4(),
            sub_category=SimpleNamespace(id=uuid4()),
            internal_group=internal_group,
            instance_id=None,
            instance_code="inner-01",
            ui_order=0,
            placement_z=0,
            interior_box_snapshot={"width": 600, "depth": 500},
            param_values={},
            param_meta={},
        )
    )

    assert result.param_values["u_th"] == "18"
    assert result.part_snapshots[0]["resolved_part_formulas"]["formula_width"] == 36.0
