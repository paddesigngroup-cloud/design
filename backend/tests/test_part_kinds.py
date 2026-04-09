from __future__ import annotations

import asyncio
import uuid
from types import SimpleNamespace

import pytest

from designkp_backend.api.routers import part_kinds as router
from designkp_backend.api.routers.part_kinds import PartKindCreate, PartKindUpdate, create_part_kind, update_part_kind


class FakeSession:
    def __init__(self, item=None) -> None:
        self.item = item
        self.added = None

    def add(self, item) -> None:
        self.added = item

    async def commit(self) -> None:
        return None

    async def refresh(self, item) -> None:
        if getattr(item, "id", None) is None:
            item.id = uuid.uuid4()

    async def get(self, _model, _item_id):
        return self.item

    async def scalar(self, stmt):
        text = str(stmt)
        if "max(part_kinds.part_kind_id)" in text:
            return 9
        return None


def test_create_part_kind_accepts_part_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_require_admin_if_present(session, admin_id):
        return None

    monkeypatch.setattr(router, "require_admin_if_present", fake_require_admin_if_present)
    session = FakeSession()
    payload = PartKindCreate(
        admin_id=None,
        part_kind_id=10,
        part_kind_code="door",
        org_part_kind_title="درب",
        sort_order=10,
        part_scope="door",
        is_system=True,
    )

    result = asyncio.run(create_part_kind(payload, session))

    assert result.part_kind_id == 10
    assert result.part_scope == "door"
    assert session.added is not None
    assert session.added.part_scope == "door"


def test_update_part_kind_persists_part_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_require_admin_if_present(session, admin_id):
        return None

    monkeypatch.setattr(router, "require_admin_if_present", fake_require_admin_if_present)
    existing = SimpleNamespace(
        id=uuid.uuid4(),
        admin_id=None,
        part_kind_id=4,
        part_kind_code="drawer",
        org_part_kind_title="کشو",
        code="drawer",
        title="کشو",
        sort_order=4,
        part_scope="internal",
        is_system=True,
    )
    payload = PartKindUpdate(
        admin_id=None,
        part_kind_id=4,
        part_kind_code="drawer",
        org_part_kind_title="کشو",
        sort_order=4,
        part_scope="structural",
        is_system=True,
    )

    result = asyncio.run(update_part_kind(existing.id, payload, FakeSession(item=existing)))

    assert result.part_scope == "structural"
    assert existing.part_scope == "structural"
