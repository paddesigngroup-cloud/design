from __future__ import annotations

from typing import Iterable


ROUND_DIGITS = 6
EPSILON = 1e-6


def round_box_value(value: float | int) -> float:
    return round(float(value), ROUND_DIGITS)


def clone_box(box: dict[str, object] | None) -> dict[str, float]:
    payload = dict(box or {})
    return {
        "width": round_box_value(payload.get("width") or 0),
        "depth": round_box_value(payload.get("depth") or 0),
        "height": round_box_value(payload.get("height") or 0),
        "cx": round_box_value(payload.get("cx") or 0),
        "cy": round_box_value(payload.get("cy") or 0),
        "cz": round_box_value(payload.get("cz") or 0),
    }


def box_extents(box: dict[str, object] | None) -> dict[str, float]:
    payload = clone_box(box)
    half_w = float(payload["width"]) * 0.5
    half_d = float(payload["depth"]) * 0.5
    half_h = float(payload["height"]) * 0.5
    return {
        "min_x": round_box_value(float(payload["cx"]) - half_w),
        "max_x": round_box_value(float(payload["cx"]) + half_w),
        "min_y": round_box_value(float(payload["cy"]) - half_d),
        "max_y": round_box_value(float(payload["cy"]) + half_d),
        "min_z": round_box_value(float(payload["cz"]) - half_h),
        "max_z": round_box_value(float(payload["cz"]) + half_h),
    }


def extents_to_box(extents: dict[str, float]) -> dict[str, float] | None:
    width = float(extents["max_x"]) - float(extents["min_x"])
    depth = float(extents["max_y"]) - float(extents["min_y"])
    height = float(extents["max_z"]) - float(extents["min_z"])
    if width <= EPSILON or depth <= EPSILON or height <= EPSILON:
        return None
    return {
        "width": round_box_value(width),
        "depth": round_box_value(depth),
        "height": round_box_value(height),
        "cx": round_box_value((float(extents["min_x"]) + float(extents["max_x"])) * 0.5),
        "cy": round_box_value((float(extents["min_y"]) + float(extents["max_y"])) * 0.5),
        "cz": round_box_value((float(extents["min_z"]) + float(extents["max_z"])) * 0.5),
    }


def overlap_extents(
    target_box: dict[str, object] | None,
    cutter_box: dict[str, object] | None,
) -> dict[str, float] | None:
    target = box_extents(target_box)
    cutter = box_extents(cutter_box)
    min_x = max(float(target["min_x"]), float(cutter["min_x"]))
    max_x = min(float(target["max_x"]), float(cutter["max_x"]))
    min_y = max(float(target["min_y"]), float(cutter["min_y"]))
    max_y = min(float(target["max_y"]), float(cutter["max_y"]))
    min_z = max(float(target["min_z"]), float(cutter["min_z"]))
    max_z = min(float(target["max_z"]), float(cutter["max_z"]))
    if (max_x - min_x) <= EPSILON or (max_y - min_y) <= EPSILON or (max_z - min_z) <= EPSILON:
        return None
    return {
        "min_x": round_box_value(min_x),
        "max_x": round_box_value(max_x),
        "min_y": round_box_value(min_y),
        "max_y": round_box_value(max_y),
        "min_z": round_box_value(min_z),
        "max_z": round_box_value(max_z),
    }


def has_positive_overlap(target_box: dict[str, object] | None, cutter_box: dict[str, object] | None) -> bool:
    return overlap_extents(target_box, cutter_box) is not None


def subtract_box(target_box: dict[str, object] | None, cutter_box: dict[str, object] | None) -> list[dict[str, float]]:
    target_extents = box_extents(target_box)
    overlap = overlap_extents(target_box, cutter_box)
    if overlap is None:
        return [clone_box(target_box)]

    x_points = [
        float(target_extents["min_x"]),
        float(overlap["min_x"]),
        float(overlap["max_x"]),
        float(target_extents["max_x"]),
    ]
    y_points = [
        float(target_extents["min_y"]),
        float(overlap["min_y"]),
        float(overlap["max_y"]),
        float(target_extents["max_y"]),
    ]
    z_points = [
        float(target_extents["min_z"]),
        float(overlap["min_z"]),
        float(overlap["max_z"]),
        float(target_extents["max_z"]),
    ]
    segments: list[dict[str, float]] = []
    for xi in range(3):
        for yi in range(3):
            for zi in range(3):
                min_x = x_points[xi]
                max_x = x_points[xi + 1]
                min_y = y_points[yi]
                max_y = y_points[yi + 1]
                min_z = z_points[zi]
                max_z = z_points[zi + 1]
                if (max_x - min_x) <= EPSILON or (max_y - min_y) <= EPSILON or (max_z - min_z) <= EPSILON:
                    continue
                if (
                    min_x >= float(overlap["min_x"]) - EPSILON and max_x <= float(overlap["max_x"]) + EPSILON
                    and min_y >= float(overlap["min_y"]) - EPSILON and max_y <= float(overlap["max_y"]) + EPSILON
                    and min_z >= float(overlap["min_z"]) - EPSILON and max_z <= float(overlap["max_z"]) + EPSILON
                ):
                    continue
                next_box = extents_to_box(
                    {
                        "min_x": min_x,
                        "max_x": max_x,
                        "min_y": min_y,
                        "max_y": max_y,
                        "min_z": min_z,
                        "max_z": max_z,
                    }
                )
                if next_box:
                    segments.append(next_box)
    return dedupe_boxes(segments)


def subtract_box_many(
    target_box: dict[str, object] | None,
    cutter_boxes: Iterable[dict[str, object] | None],
) -> list[dict[str, float]]:
    current = [clone_box(target_box)]
    for cutter in list(cutter_boxes or []):
        next_segments: list[dict[str, float]] = []
        for segment in current:
            next_segments.extend(subtract_box(segment, cutter))
        current = dedupe_boxes(next_segments)
        if not current:
            break
    return current


def dedupe_boxes(boxes: Iterable[dict[str, object] | None]) -> list[dict[str, float]]:
    deduped: list[dict[str, float]] = []
    seen: set[tuple[float, float, float, float, float, float]] = set()
    for box in list(boxes or []):
        payload = clone_box(box)
        if payload["width"] <= EPSILON or payload["depth"] <= EPSILON or payload["height"] <= EPSILON:
            continue
        signature = (
            float(payload["width"]),
            float(payload["depth"]),
            float(payload["height"]),
            float(payload["cx"]),
            float(payload["cy"]),
            float(payload["cz"]),
        )
        if signature in seen:
            continue
        seen.add(signature)
        deduped.append(payload)
    return deduped
