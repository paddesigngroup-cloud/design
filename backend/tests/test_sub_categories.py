from __future__ import annotations

import asyncio
import uuid
from types import SimpleNamespace

import pytest

from designkp_backend.api.routers import sub_categories as router
from designkp_backend.api.routers.sub_categories import SubCategoryCreate, create_sub_category


class FakeSession:
    def __init__(self) -> None:
        self.added = []
        self._get_item = None

    def add(self, item) -> None:
        self.added.append(item)

    async def flush(self) -> None:
        for item in self.added:
            if getattr(item, "id", None) is None:
                item.id = uuid.uuid4()

    async def commit(self) -> None:
        return None

    async def refresh(self, item) -> None:
        return None

    async def get(self, _model, _item_id):
        return self._get_item

    async def scalar(self, stmt):
        text = str(stmt)
        if "max(sub_categories.sub_cat_id)" in text:
            return 1
        if "FROM templates" in text:
            return SimpleNamespace(temp_id=1, admin_id=None)
        if "FROM categories" in text:
            return SimpleNamespace(temp_id=1, cat_id=1, admin_id=None)
        return None

    async def scalars(self, stmt):
        text = str(stmt)
        if "FROM params" in text:
            return SimpleNamespace(all=lambda: [SimpleNamespace(param_id=1, param_code="w", admin_id=None, sort_order=1)])
        if "FROM sub_category_param_defaults" in text:
            row = SimpleNamespace(sub_category_id=self.added[0].id, param_id=1, default_value=None)
            return SimpleNamespace(all=lambda: [row])
        return SimpleNamespace(all=lambda: [])


def test_create_sub_category_accepts_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_require_admin_if_present(session, admin_id):
        return None

    monkeypatch.setattr(router, "require_admin_if_present", fake_require_admin_if_present)
    session = FakeSession()
    payload = SubCategoryCreate(
        admin_id=None,
        temp_id=1,
        cat_id=1,
        sub_cat_id=2,
        sub_cat_title="مدل جدید",
        design_outline_color="#123ABC",
        sort_order=2,
        is_system=True,
        param_defaults={"w": 720},
    )

    result = asyncio.run(create_sub_category(payload, session))

    assert result.sub_cat_title == "مدل جدید"
    assert result.design_outline_color == "#123ABC"
    assert result.param_defaults["w"] in {"720", None}
