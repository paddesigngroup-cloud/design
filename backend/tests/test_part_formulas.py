from __future__ import annotations

import asyncio
import uuid
from types import SimpleNamespace

import pytest

from designkp_backend.api.routers import part_formulas as router
from designkp_backend.api.routers.part_formulas import PartFormulaCreate, PartFormulaUpdate, create_part_formula, update_part_formula


class FakeSession:
    def __init__(self, item=None) -> None:
        self.item = item
        self.added = None
        self.part_model = SimpleNamespace(id=uuid.uuid4(), title="مربع مستطیل", admin_id=None)

    def add(self, item) -> None:
        self.added = item

    async def commit(self) -> None:
        if self.added is not None and getattr(self.added, "id", None) is None:
            self.added.id = uuid.uuid4()
            self.added.part_model = self.part_model
        return None

    async def refresh(self, item) -> None:
        if getattr(item, "id", None) is None:
            item.id = uuid.uuid4()

    async def get(self, _model, _item_id):
        return self.item

    async def scalar(self, stmt):
        text = str(stmt)
        if "max(part_formulas.part_formula_id)" in text:
            return 11
        if "FROM part_models" in text:
            return self.part_model
        if "part_formulas.id" in text:
            target = self.added or self.item
            if target is not None and not getattr(target, "part_model", None):
                target.part_model = self.part_model
            return target
        return None


def _payload_kwargs() -> dict[str, object]:
    return {
        "part_kind_id": 6,
        "part_model_id": uuid.uuid4(),
        "part_sub_kind_id": 1,
        "part_code": "door_left",
        "part_title": "درب چپ",
        "formula_l": "(1)",
        "formula_w": "(1)",
        "formula_width": "(1)",
        "formula_depth": "(1)",
        "formula_height": "(1)",
        "formula_cx": "(1)",
        "formula_cy": "(1)",
        "formula_cz": "(1)",
        "sort_order": 12,
        "is_system": True,
    }


def test_create_part_formula_persists_door_dependent(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_require_admin_if_present(session, admin_id):
        return None

    async def fake_validate(*args, **kwargs):
        return None

    monkeypatch.setattr(router, "require_admin_if_present", fake_require_admin_if_present)
    monkeypatch.setattr(router, "_validate_part_formula_expressions", fake_validate)
    session = FakeSession()
    payload = PartFormulaCreate(
        admin_id=None,
        part_formula_id=12,
        door_dependent=True,
        **_payload_kwargs(),
    )

    result = asyncio.run(create_part_formula(payload, session))

    assert result.door_dependent is True
    assert session.added.door_dependent is True
    assert session.added.part_model_id == payload.part_model_id


def test_update_part_formula_persists_door_dependent(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_require_admin_if_present(session, admin_id):
        return None

    async def fake_validate(*args, **kwargs):
        return None

    monkeypatch.setattr(router, "require_admin_if_present", fake_require_admin_if_present)
    monkeypatch.setattr(router, "_validate_part_formula_expressions", fake_validate)
    existing = SimpleNamespace(
        id=uuid.uuid4(),
        admin_id=None,
        part_formula_id=12,
        part_kind_id=6,
        part_model_id=uuid.uuid4(),
        part_sub_kind_id=1,
        part_code="door_left",
        part_title="درب چپ",
        formula_l="(1)",
        formula_w="(1)",
        formula_width="(1)",
        formula_depth="(1)",
        formula_height="(1)",
        formula_cx="(1)",
        formula_cy="(1)",
        formula_cz="(1)",
        door_dependent=False,
        code="door_left",
        title="درب چپ",
        sort_order=12,
        is_system=True,
    )
    payload = PartFormulaUpdate(
        admin_id=None,
        part_formula_id=12,
        door_dependent=True,
        **_payload_kwargs(),
    )

    result = asyncio.run(update_part_formula(existing.id, payload, FakeSession(item=existing)))

    assert result.door_dependent is True
    assert existing.door_dependent is True
    assert existing.part_model_id == payload.part_model_id
