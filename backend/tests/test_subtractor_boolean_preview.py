from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from designkp_backend.services.sub_category_designs import build_boolean_preview_payload


def _snapshot(part_formula_id: int, *, door_dependent: bool, box: dict[str, float]) -> dict[str, object]:
    return {
        "part_formula_id": part_formula_id,
        "part_code": f"part_{part_formula_id}",
        "part_title": f"Part {part_formula_id}",
        "door_dependent": door_dependent,
        "viewer_payload": {
            "box": dict(box),
        },
    }


def test_build_boolean_preview_payload_targets_only_door_dependent_parts() -> None:
    door_id = uuid4()
    interior_id = uuid4()
    root_target = _snapshot(101, door_dependent=True, box={"width": 100, "depth": 20, "height": 200, "cx": 50, "cy": 10, "cz": 100})
    root_ignored = _snapshot(102, door_dependent=False, box={"width": 40, "depth": 20, "height": 40, "cx": 150, "cy": 10, "cz": 40})
    interior_target = _snapshot(201, door_dependent=True, box={"width": 60, "depth": 20, "height": 120, "cx": 30, "cy": 10, "cz": 60})

    payload = build_boolean_preview_payload(
        context=SimpleNamespace(part_formulas_by_id={}),
        root_part_snapshots=[root_target, root_ignored],
        interiors=[
            SimpleNamespace(
                instance_id=interior_id,
                instance_code="inner-1",
                line_color="#111111",
                part_snapshots=[interior_target],
            )
        ],
        subtractors=[
            SimpleNamespace(
                instance_id=uuid4(),
                subtractor_part_group_id=uuid4(),
                instance_code="sub-1",
                ui_order=0,
                viewer_boxes=[{"width": 20, "depth": 20, "height": 40, "cx": 50, "cy": 10, "cz": 100}],
            )
        ],
        doors=[
            SimpleNamespace(
                instance_id=door_id,
                instance_code="door-1",
                line_color="#222222",
                structural_part_formula_ids=[101, 102],
                dependent_interior_instance_ids=[str(interior_id)],
                controller_box_snapshot={},
            )
        ],
    )

    assert len(payload.boolean_targets) == 2
    assert {row["part_formula_id"] for row in payload.boolean_targets} == {101, 201}
    assert len(payload.boolean_cutters) == 1
    assert len(payload.boolean_result) == 2


def test_build_boolean_preview_payload_restores_original_box_when_no_overlap() -> None:
    target_box = {"width": 100, "depth": 20, "height": 200, "cx": 50, "cy": 10, "cz": 100}
    payload = build_boolean_preview_payload(
        context=SimpleNamespace(part_formulas_by_id={}),
        root_part_snapshots=[_snapshot(101, door_dependent=True, box=target_box)],
        interiors=[],
        subtractors=[
            SimpleNamespace(
                instance_id=uuid4(),
                subtractor_part_group_id=uuid4(),
                instance_code="sub-1",
                ui_order=0,
                viewer_boxes=[{"width": 10, "depth": 20, "height": 10, "cx": 300, "cy": 10, "cz": 300}],
            )
        ],
        doors=[
            SimpleNamespace(
                instance_id=uuid4(),
                instance_code="door-1",
                line_color="#222222",
                structural_part_formula_ids=[101],
                dependent_interior_instance_ids=[],
                controller_box_snapshot={},
            )
        ],
    )

    assert payload.boolean_result[0]["boxes"] == [target_box]
