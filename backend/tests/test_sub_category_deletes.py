from __future__ import annotations

import asyncio
import uuid
from types import SimpleNamespace

from designkp_backend.api.routers.sub_categories import delete_sub_category
from designkp_backend.api.routers.sub_category_designs import delete_sub_category_design
from designkp_backend.api.routers import sub_category_designs as design_router


class DeleteSession:
    def __init__(self, item) -> None:
        self.item = item
        self.executed = []
        self.committed = False

    async def get(self, _model, _item_id):
        return self.item

    async def execute(self, stmt):
        self.executed.append(str(stmt))
        return None

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.committed = False


def test_delete_sub_category_soft_deletes_and_marks_designs() -> None:
    item = SimpleNamespace(id=uuid.uuid4(), deleted_at=None)
    session = DeleteSession(item)

    response = asyncio.run(delete_sub_category(item.id, session))

    assert response.status_code == 204
    assert item.deleted_at is not None
    assert session.committed is True
    assert any("UPDATE sub_category_designs" in stmt for stmt in session.executed)


def test_delete_sub_category_design_soft_deletes_and_cleans_children(monkeypatch) -> None:
    async def fake_interior_instance_tables_ready(_session) -> bool:
        return False

    monkeypatch.setattr(design_router, "interior_instance_tables_ready", fake_interior_instance_tables_ready)

    item = SimpleNamespace(id=uuid.uuid4(), deleted_at=None)
    session = DeleteSession(item)

    response = asyncio.run(delete_sub_category_design(item.id, session))

    assert response.status_code == 204
    assert item.deleted_at is not None
    assert session.committed is True
    assert any("DELETE FROM sub_category_design_parts" in stmt for stmt in session.executed)
