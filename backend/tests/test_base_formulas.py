from __future__ import annotations

import asyncio
import uuid
from types import SimpleNamespace

import pytest

from designkp_backend.api.routers import base_formulas as router
from designkp_backend.api.routers.base_formulas import (
    BaseFormulaCreate,
    BaseFormulaUpdate,
    create_base_formula,
    update_base_formula,
    validate_formula_structure,
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
            item.id = uuid.uuid4()

    async def get(self, _model, _item_id):
        return self.item


def test_validate_formula_structure_accepts_simple_formula() -> None:
    assert validate_formula_structure("(w*2)") == []


def test_validate_formula_structure_accepts_compound_formula() -> None:
    assert validate_formula_structure("((u_th)*(2))+(b_th)") == []


def test_validate_formula_structure_rejects_unbalanced_parentheses() -> None:
    assert validate_formula_structure("(w*2") == ["Parentheses are unbalanced."]


def test_validate_formula_structure_rejects_double_operator() -> None:
    assert validate_formula_structure("w++2") == ["Formula cannot start with an operator."]


def test_validate_formula_structure_rejects_trailing_operator() -> None:
    assert validate_formula_structure("(w*2)+") == ["Formula cannot end with an operator."]


def test_validate_formula_structure_accepts_number_only_formula() -> None:
    assert validate_formula_structure("2") == []


def test_validate_formula_structure_accepts_negative_decimal_formula() -> None:
    assert validate_formula_structure("(w*-2.5)+(-0.75)") == []


def test_create_base_formula_rejects_unknown_param(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_require_admin_if_present(session, admin_id):
        return None

    monkeypatch.setattr(router, "require_admin_if_present", fake_require_admin_if_present)

    async def fake_known_codes(session, admin_id):
        return {"w", "u_th", "b_th"}

    monkeypatch.setattr(router, "_known_param_codes", fake_known_codes)
    payload = BaseFormulaCreate(admin_id=None, fo_id=5, param_formula="f5", formula="(unknown*2)", sort_order=5, is_system=True)

    with pytest.raises(Exception) as exc_info:
        asyncio.run(create_base_formula(payload, FakeSession()))

    assert getattr(exc_info.value, "status_code", None) == 400
    assert "Unknown param codes in formula" in str(getattr(exc_info.value, "detail", ""))


def test_create_base_formula_rejects_unbalanced_parentheses(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_require_admin_if_present(session, admin_id):
        return None

    monkeypatch.setattr(router, "require_admin_if_present", fake_require_admin_if_present)

    async def fake_known_codes(session, admin_id):
        return {"w"}

    monkeypatch.setattr(router, "_known_param_codes", fake_known_codes)
    payload = BaseFormulaCreate(admin_id=None, fo_id=2, param_formula="f2", formula="(w*2", sort_order=2, is_system=True)

    with pytest.raises(Exception) as exc_info:
        asyncio.run(create_base_formula(payload, FakeSession()))

    assert getattr(exc_info.value, "status_code", None) == 400
    assert getattr(exc_info.value, "detail", "") == "Parentheses are unbalanced."


def test_create_base_formula_accepts_valid_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_require_admin_if_present(session, admin_id):
        return None

    monkeypatch.setattr(router, "require_admin_if_present", fake_require_admin_if_present)

    async def fake_known_codes(session, admin_id):
        return {"w", "b_th"}

    monkeypatch.setattr(router, "_known_param_codes", fake_known_codes)
    session = FakeSession()
    payload = BaseFormulaCreate(admin_id=None, fo_id=8, param_formula="f8", formula="(w*2)+(b_th)", sort_order=8, is_system=True)

    result = asyncio.run(create_base_formula(payload, session))

    assert result.param_formula == "f8"
    assert result.formula == "(w*2)+(b_th)"
    assert session.added is not None


def test_update_base_formula_rejects_unknown_param(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_require_admin_if_present(session, admin_id):
        return None

    monkeypatch.setattr(router, "require_admin_if_present", fake_require_admin_if_present)

    async def fake_known_codes(session, admin_id):
        return {"w"}

    monkeypatch.setattr(router, "_known_param_codes", fake_known_codes)
    existing = SimpleNamespace(
        id=uuid.uuid4(),
        admin_id=None,
        fo_id=1,
        param_formula="f1",
        formula="(w)",
        code="f1",
        title="f1",
        sort_order=1,
        is_system=True,
    )
    payload = BaseFormulaUpdate(admin_id=None, fo_id=1, param_formula="f1", formula="(missing*2)", sort_order=1, is_system=True)

    with pytest.raises(Exception) as exc_info:
        asyncio.run(update_base_formula(existing.id, payload, FakeSession(existing)))

    assert getattr(exc_info.value, "status_code", None) == 400
    assert "Unknown param codes in formula" in str(getattr(exc_info.value, "detail", ""))
