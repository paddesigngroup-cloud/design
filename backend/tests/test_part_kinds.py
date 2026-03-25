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


def test_create_part_kind_accepts_is_internal(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_require_admin_if_present(session, admin_id):
        return None

    monkeypatch.setattr(router, "require_admin_if_present", fake_require_admin_if_present)
    session = FakeSession()
    payload = PartKindCreate(
        admin_id=None,
        part_kind_id=10,
        part_kind_code="drawer",
        org_part_kind_title="کشو",
        sort_order=10,
        is_internal=True,
        is_system=True,
    )

    result = asyncio.run(create_part_kind(payload, session))

    assert result.part_kind_id == 10
    assert result.is_internal is True
    assert session.added is not None
    assert session.added.is_internal is True


def test_update_part_kind_persists_is_internal(monkeypatch: pytest.MonkeyPatch) -> None:
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
        is_internal=False,
        is_system=True,
    )
    payload = PartKindUpdate(
        admin_id=None,
        part_kind_id=4,
        part_kind_code="drawer",
        org_part_kind_title="کشو",
        sort_order=4,
        is_internal=True,
        is_system=True,
    )

    result = asyncio.run(update_part_kind(existing.id, payload, FakeSession(item=existing)))

    assert result.is_internal is True
    assert existing.is_internal is True
