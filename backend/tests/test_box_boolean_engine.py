from __future__ import annotations

from designkp_backend.services.geometry.box_boolean import subtract_box_many


def _box(*, width: float, depth: float, height: float, cx: float, cy: float, cz: float) -> dict[str, float]:
    return {
        "width": width,
        "depth": depth,
        "height": height,
        "cx": cx,
        "cy": cy,
        "cz": cz,
    }


def test_subtract_box_many_keeps_box_without_overlap() -> None:
    target = _box(width=100, depth=20, height=200, cx=50, cy=10, cz=100)
    cutter = _box(width=10, depth=20, height=10, cx=200, cy=10, cz=200)

    result = subtract_box_many(target, [cutter])

    assert result == [target]


def test_subtract_box_many_removes_full_overlap() -> None:
    target = _box(width=100, depth=20, height=200, cx=50, cy=10, cz=100)
    cutter = _box(width=100, depth=20, height=200, cx=50, cy=10, cz=100)

    result = subtract_box_many(target, [cutter])

    assert result == []


def test_subtract_box_many_splits_partial_overlap_deterministically() -> None:
    target = _box(width=100, depth=20, height=200, cx=50, cy=10, cz=100)
    cutters = [
        _box(width=20, depth=20, height=40, cx=50, cy=10, cz=160),
        _box(width=20, depth=20, height=40, cx=50, cy=10, cz=40),
    ]

    result_a = subtract_box_many(target, cutters)
    result_b = subtract_box_many(target, cutters)

    assert result_a == result_b
    assert result_a
    assert all(box["width"] > 0 and box["depth"] > 0 and box["height"] > 0 for box in result_a)


def test_subtract_box_many_ignores_edge_touch() -> None:
    target = _box(width=100, depth=20, height=200, cx=50, cy=10, cz=100)
    cutter = _box(width=20, depth=20, height=40, cx=110, cy=10, cz=100)

    result = subtract_box_many(target, [cutter])

    assert result == [target]
