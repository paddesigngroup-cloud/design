from __future__ import annotations

import asyncio
import uuid
from types import SimpleNamespace

import pytest

from designkp_backend.api.routers import categories as router
from designkp_backend.api.routers.categories import CategoryCreate, CategoryUpdate, create_category, update_category


class FakeSession:
    def __init__(self, item=None, template=None) -> None:
        self.item = item
        self.template = template
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
        if "max(categories.cat_id)" in text:
            return 3
        return self.template


def test_create_category_rejects_missing_template(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_require_admin_if_present(session, admin_id):
        return None

    monkeypatch.setattr(router, "require_admin_if_present", fake_require_admin_if_present)
    payload = CategoryCreate(admin_id=None, temp_id=9, cat_id=4, cat_title="دسته جدید", sort_order=4, is_system=True)

    with pytest.raises(Exception) as exc_info:
        asyncio.run(create_category(payload, FakeSession(template=None)))

    assert getattr(exc_info.value, "status_code", None) == 400
    assert getattr(exc_info.value, "detail", "") == "Template not found for this admin scope."


def test_create_category_accepts_valid_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_require_admin_if_present(session, admin_id):
        return None

    monkeypatch.setattr(router, "require_admin_if_present", fake_require_admin_if_present)
    session = FakeSession(template=SimpleNamespace(temp_id=1, admin_id=None))
    payload = CategoryCreate(admin_id=None, temp_id=1, cat_id=4, cat_title="دسته جدید", sort_order=4, is_system=True)

    result = asyncio.run(create_category(payload, session))

    assert result.temp_id == 1
    assert result.cat_id == 4
    assert result.cat_title == "دسته جدید"
    assert session.added is not None


def test_update_category_rejects_missing_category(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_require_admin_if_present(session, admin_id):
        return None

    monkeypatch.setattr(router, "require_admin_if_present", fake_require_admin_if_present)
    payload = CategoryUpdate(admin_id=None, temp_id=1, cat_id=1, cat_title="زمینی", sort_order=1, is_system=True)

    with pytest.raises(Exception) as exc_info:
        asyncio.run(update_category(uuid.uuid4(), payload, FakeSession(item=None, template=SimpleNamespace(temp_id=1, admin_id=None))))

    assert getattr(exc_info.value, "status_code", None) == 404
    assert getattr(exc_info.value, "detail", "") == "Category not found."
