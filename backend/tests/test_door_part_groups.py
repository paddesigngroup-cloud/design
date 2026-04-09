from __future__ import annotations

import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest

from designkp_backend.api.routers import door_part_groups as router
from designkp_backend.api.routers.door_part_groups import (
    DoorPartGroupCreate,
    DoorPartGroupPartSelectionPayload,
    DoorPartGroupUpdate,
    create_door_part_group,
    update_door_part_group,
)


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
            item.id = uuid4()

    async def get(self, _model, _item_id):
        return self.item

    async def flush(self) -> None:
        return None

    async def scalar(self, stmt):
        text = str(stmt)
        if "max(door_part_groups.group_id)" in text:
            return 3
        return self.item


def test_create_door_part_group_uses_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_require_admin_if_present(session, admin_id):
        return None

    async def fake_replace_group_parts(session, *, group, parts):
        group.__dict__["parts"] = [
            SimpleNamespace(
                id=uuid4(),
                part_formula_id=parts[0].part_formula_id,
                part_kind_id=6,
                part_code="door_left",
                part_title="درب چپ",
                enabled=True,
                ui_order=0,
            )
        ]

    async def fake_load_group(session, group_uuid):
        if getattr(session.added, "id", None) is None:
            session.added.id = uuid4()
        return session.added

    monkeypatch.setattr(router, "require_admin_if_present", fake_require_admin_if_present)
    monkeypatch.setattr(router, "_replace_group_parts", fake_replace_group_parts)
    monkeypatch.setattr(router, "_ensure_unique_group_code", lambda *args, **kwargs: asyncio.sleep(0))
    monkeypatch.setattr(router, "_load_group", fake_load_group)

    session = FakeSession()
    payload = DoorPartGroupCreate(
        admin_id=None,
        group_id=4,
        group_title="گروه درب",
        code="door_group",
        sort_order=4,
        is_system=True,
        parts=[DoorPartGroupPartSelectionPayload(part_formula_id=12, enabled=True, ui_order=0)],
    )

    result = asyncio.run(create_door_part_group(payload, session))

    assert result.group_id == 4
    assert result.parts[0].part_formula_id == 12


def test_update_door_part_group_updates_basic_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_require_admin_if_present(session, admin_id):
        return None

    async def fake_replace_group_parts(session, *, group, parts):
        group.__dict__["parts"] = []

    async def fake_load_group(session, group_uuid):
        return session.item

    monkeypatch.setattr(router, "require_admin_if_present", fake_require_admin_if_present)
    monkeypatch.setattr(router, "_replace_group_parts", fake_replace_group_parts)
    monkeypatch.setattr(router, "_ensure_unique_group_code", lambda *args, **kwargs: asyncio.sleep(0))
    monkeypatch.setattr(router, "_load_group", fake_load_group)

    existing = SimpleNamespace(
        id=uuid4(),
        admin_id=None,
        group_id=4,
        group_title="قدیمی",
        code="old_code",
        title="قدیمی",
        sort_order=4,
        is_system=True,
        parts=[],
    )
    session = FakeSession(item=existing)
    payload = DoorPartGroupUpdate(
        admin_id=None,
        group_id=4,
        group_title="جدید",
        code="new_code",
        sort_order=7,
        is_system=False,
        parts=[],
    )

    result = asyncio.run(update_door_part_group(existing.id, payload, session))

    assert result.group_title == "جدید"
    assert existing.code == "new_code"
    assert existing.sort_order == 7
