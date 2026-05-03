from __future__ import annotations

import asyncio
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest

from designkp_backend.api.routers import admin_storage as router
from designkp_backend.api.routers.admin_storage import export_service_types


class FakeSession:
    def __init__(self, items: list[object]) -> None:
        self.items = items
        self.last_scalars_stmt = None

    async def scalars(self, stmt):
        self.last_scalars_stmt = str(stmt)
        return SimpleNamespace(all=lambda: self.items)


def test_export_service_types_returns_csv_and_snapshot(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    called = {"table_name": None, "headers": None, "rows": None}

    async def fake_require_admin(session, admin_id):
        return None

    async def fake_write_table_snapshot_async(admin_id, table_name, headers, rows):
        called["table_name"] = table_name
        called["headers"] = headers
        called["rows"] = rows
        return tmp_path / "service_types.csv"

    monkeypatch.setattr(router, "require_admin", fake_require_admin)
    monkeypatch.setattr(router, "write_table_snapshot_async", fake_write_table_snapshot_async)
    admin_id = uuid.uuid4()
    session = FakeSession(
        [
            SimpleNamespace(
                admin_id=None,
                service_type="برش CNC",
                service_title="دورو",
                short_code="dr",
                has_subtraction=True,
                service_location="front",
                subtraction_shape="triangle",
                shape_angles=[
                    {"index": 0, "angle_deg": 60},
                    {"index": 1, "angle_deg": 60},
                    {"index": 2, "angle_deg": 60},
                ],
                axis_to_opposite_edge_distance=12,
                axis_to_aligned_edge_distance=8,
                working_diameter=35,
                working_depth=14,
                working_depth_mode="to_end",
                working_depth_end_offset=2,
                preview_mirror_x=True,
                preview_mirror_y=False,
                sort_order=1,
                id=uuid.uuid4(),
            )
        ]
    )

    response = asyncio.run(export_service_types(admin_id, session))
    body = response.body.decode("utf-8-sig")

    assert response.headers["Content-Disposition"] == 'attachment; filename="part_services_excel_template.csv"'
    assert "service_type,service_title,short_code,has_subtraction,service_location,subtraction_shape,shape_angles" in body
    assert "برش CNC,دورو,dr,1,front,triangle,\"60,60,60\",12,8,35,14,to_end,2,1,0,system" in body
    assert called["table_name"] == "service_types"
    assert called["headers"] == [
        "service_type",
        "service_title",
        "short_code",
        "has_subtraction",
        "service_location",
        "subtraction_shape",
        "shape_angles",
        "axis_to_opposite_edge_distance",
        "axis_to_aligned_edge_distance",
        "working_diameter",
        "working_depth",
        "working_depth_mode",
        "working_depth_end_offset",
        "preview_mirror_x",
        "preview_mirror_y",
        "admin_mode",
    ]
    assert called["rows"] == [[
        "برش CNC",
        "دورو",
        "dr",
        1,
        "front",
        "triangle",
        "60,60,60",
        12,
        8,
        35,
        14,
        "to_end",
        2,
        1,
        0,
        "system",
    ]]
