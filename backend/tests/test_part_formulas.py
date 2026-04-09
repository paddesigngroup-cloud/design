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
        if "max(part_formulas.part_formula_id)" in text:
            return 11
        return None


def _payload_kwargs() -> dict[str, object]:
    return {
        "part_kind_id": 6,
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
