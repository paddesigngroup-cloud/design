from __future__ import annotations

import asyncio
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest

from designkp_backend.api.routers import admin_storage as router
from designkp_backend.api.routers.admin_storage import export_part_models


class FakeSession:
    def __init__(self, items: list[object]) -> None:
        self.items = items
        self.last_scalars_stmt = None

    async def scalars(self, stmt):
        self.last_scalars_stmt = str(stmt)
        return SimpleNamespace(all=lambda: self.items)


def test_export_part_models_returns_csv_and_snapshot(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    called = {"table_name": None, "headers": None, "rows": None}

    async def fake_require_admin(session, admin_id):
        return None

    async def fake_write_table_snapshot_async(admin_id, table_name, headers, rows):
        called["table_name"] = table_name
        called["headers"] = headers
        called["rows"] = rows
        return tmp_path / "part_models.csv"

    monkeypatch.setattr(router, "require_admin", fake_require_admin)
    monkeypatch.setattr(router, "write_table_snapshot_async", fake_write_table_snapshot_async)
    admin_id = uuid.uuid4()
    session = FakeSession(
        [
            SimpleNamespace(
                admin_id=None,
                title="شش ضلعی",
                side_count=6,
                interior_angle_sum=720,
                default_angles=[
                    {"index": 0, "angle_deg": 120},
                    {"index": 1, "angle_deg": 120},
                    {"index": 2, "angle_deg": 120},
                    {"index": 3, "angle_deg": 120},
                    {"index": 4, "angle_deg": 120},
                    {"index": 5, "angle_deg": 120},
                ],
                sort_order=1,
                id=uuid.uuid4(),
            )
        ]
    )

    response = asyncio.run(export_part_models(admin_id, session))
    body = response.body.decode("utf-8-sig")

    assert response.headers["Content-Disposition"] == 'attachment; filename="part_models_excel_template.csv"'
    assert "title,side_count,interior_angle_sum,default_angles,admin_mode" in body
    assert "شش ضلعی,6,720,\"120,120,120,120,120,120\",system" in body
    assert called["table_name"] == "part_models"
    assert called["headers"] == ["title", "side_count", "interior_angle_sum", "default_angles", "admin_mode"]
    assert called["rows"] == [["شش ضلعی", 6, 720, "120,120,120,120,120,120", "system"]]
