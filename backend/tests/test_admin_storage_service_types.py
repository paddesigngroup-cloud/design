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
                sort_order=1,
                id=uuid.uuid4(),
            )
        ]
    )

    response = asyncio.run(export_service_types(admin_id, session))
    body = response.body.decode("utf-8-sig")

    assert response.headers["Content-Disposition"] == 'attachment; filename="service_types_excel_template.csv"'
    assert "service_type,service_title,short_code,admin_mode" in body
    assert "برش CNC,دورو,dr,system" in body
    assert called["table_name"] == "service_types"
    assert called["headers"] == ["service_type", "service_title", "short_code", "admin_mode"]
    assert called["rows"] == [["برش CNC", "دورو", "dr", "system"]]
