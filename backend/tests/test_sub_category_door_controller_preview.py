from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from designkp_backend.services.sub_category_designs import (
    _collect_controller_selection_boxes_by_formula_id,
    _collect_dependent_interior_boxes_by_formula_id,
    _compute_door_controller_box_snapshot,
)


def test_compute_double_equal_hinged_controller_snapshot_and_params() -> None:
    snapshot, computed = _compute_door_controller_box_snapshot(
        structural_part_formula_ids=[101, 102, 103, 104],
        source_boxes_by_formula_id={
            101: {"width": 2, "height": 100, "cx": 1, "cz": 50},
            102: {"width": 2, "height": 100, "cx": 99, "cz": 50},
            103: {"width": 100, "height": 2, "cx": 50, "cz": 99},
            104: {"width": 100, "height": 2, "cx": 50, "cz": 1},
        },
    )

    assert snapshot["min_x"] == pytest.approx(0)
    assert snapshot["max_x"] == pytest.approx(100)
    assert snapshot["min_z"] == pytest.approx(0)
    assert snapshot["max_z"] == pytest.approx(100)
    assert computed["door_width"] == pytest.approx(100)
    assert computed["door_height"] == pytest.approx(100)
    assert computed["left"] == pytest.approx(0)
    assert computed["right"] == pytest.approx(0)
    assert computed["top"] == pytest.approx(0)
    assert computed["bottom_offset"] == pytest.approx(0)


def test_compute_double_equal_hinged_controller_uses_vertical_and_horizontal_outer_faces() -> None:
    snapshot, computed = _compute_door_controller_box_snapshot(
        structural_part_formula_ids=[101, 102, 103, 104],
        source_boxes_by_formula_id={
            101: {"width": 2, "height": 120, "cx": 1, "cz": 50},
            102: {"width": 2, "height": 120, "cx": 99, "cz": 50},
            103: {"width": 90, "height": 2, "cx": 50, "cz": 89},
            104: {"width": 90, "height": 2, "cx": 50, "cz": 19},
        },
    )

    assert snapshot["min_x"] == pytest.approx(0)
    assert snapshot["max_x"] == pytest.approx(100)
    assert snapshot["min_z"] == pytest.approx(18)
    assert snapshot["max_z"] == pytest.approx(90)
    assert snapshot["width"] == pytest.approx(100)
    assert snapshot["height"] == pytest.approx(72)
    assert computed["door_width"] == pytest.approx(100)
    assert computed["door_height"] == pytest.approx(72)
    assert computed["left"] == pytest.approx(0)
    assert computed["right"] == pytest.approx(0)
    assert computed["top"] == pytest.approx(20)
    assert computed["bottom_offset"] == pytest.approx(28)


def test_compute_double_equal_hinged_controller_offsets_against_outer_design_bounds() -> None:
    snapshot, computed = _compute_door_controller_box_snapshot(
        structural_part_formula_ids=[101, 102, 103, 104],
        source_boxes_by_formula_id={
            101: {"width": 2, "height": 100, "cx": 6, "cz": 55},
            102: {"width": 2, "height": 100, "cx": 94, "cz": 55},
            103: {"width": 88, "height": 2, "cx": 50, "cz": 89},
            104: {"width": 88, "height": 2, "cx": 50, "cz": 21},
            201: {"width": 100, "height": 2, "cx": 50, "cz": 109},
            202: {"width": 100, "height": 2, "cx": 50, "cz": 1},
        },
    )

    assert snapshot["min_x"] == pytest.approx(5)
    assert snapshot["max_x"] == pytest.approx(95)
    assert snapshot["min_z"] == pytest.approx(20)
    assert snapshot["max_z"] == pytest.approx(90)
    assert computed["door_width"] == pytest.approx(90)
    assert computed["door_height"] == pytest.approx(70)
    assert computed["left"] == pytest.approx(5)
    assert computed["right"] == pytest.approx(5)
    assert computed["top"] == pytest.approx(20)
    assert computed["bottom_offset"] == pytest.approx(20)


def test_compute_double_equal_hinged_controller_requires_two_vertical_and_two_horizontal() -> None:
    with pytest.raises(HTTPException) as exc_info:
        _compute_door_controller_box_snapshot(
            structural_part_formula_ids=[101, 102, 103, 104],
            source_boxes_by_formula_id={
                101: {"width": 2, "height": 100, "cx": 1, "cz": 50},
                102: {"width": 2, "height": 100, "cx": 99, "cz": 50},
                103: {"width": 2, "height": 100, "cx": 50, "cz": 50},
                104: {"width": 2, "height": 100, "cx": 60, "cz": 50},
            },
        )

    assert exc_info.value.status_code == 422


def test_collect_dependent_interior_boxes_prefers_selected_instance_for_same_formula() -> None:
    selected_id = uuid4()
    other_id = uuid4()

    selected_boxes = _collect_dependent_interior_boxes_by_formula_id(
        [
            SimpleNamespace(
                id=other_id,
                part_snapshots=[
                    {"part_formula_id": 501, "viewer_payload": {"box": {"cx": 90, "cz": 50, "width": 2, "height": 100}}},
                ],
            ),
            SimpleNamespace(
                id=selected_id,
                part_snapshots=[
                    {"part_formula_id": 501, "viewer_payload": {"box": {"cx": 10, "cz": 50, "width": 2, "height": 100}}},
                ],
            ),
        ],
        [str(selected_id)],
    )

    assert selected_boxes == {
        501: {"cx": 10, "cz": 50, "width": 2, "height": 100},
    }


def test_collect_controller_selection_boxes_uses_selected_snapshot_index() -> None:
    selected_id = uuid4()

    selected_boxes = _collect_controller_selection_boxes_by_formula_id(
        controller_box_snapshot={
            "selected_parts": [
                {
                    "source_type": "internal",
                    "source_id": str(selected_id),
                    "part_formula_id": 501,
                    "source_snapshot_index": 1,
                }
            ]
        },
        interiors=[
            SimpleNamespace(
                id=selected_id,
                part_snapshots=[
                    {"part_formula_id": 501, "viewer_payload": {"box": {"cx": 10, "cz": 50, "width": 2, "height": 100}}},
                    {"part_formula_id": 501, "viewer_payload": {"box": {"cx": 40, "cz": 50, "width": 2, "height": 100}}},
                ],
            ),
        ],
    )

    assert selected_boxes == {
        501: {"cx": 40, "cz": 50, "width": 2, "height": 100},
    }
