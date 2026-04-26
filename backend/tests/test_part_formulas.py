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
        self.part_model = SimpleNamespace(id=uuid.uuid4(), title="مربع مستطیل", admin_id=None, side_count=4)
        self.service_type = SimpleNamespace(id=uuid.uuid4(), service_type="edge", service_title="نوار", part_side="front", admin_id=None)

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
        if "FROM part_service_types" in text:
            return self.service_type
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
        "lw_frame_mapping": {"l_axis": "horizontal", "w_axis": "vertical"},
        "part_model_side_services": [],
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
    assert result.lw_frame_mapping == {"l_axis": "horizontal", "w_axis": "vertical"}
    assert result.part_model_side_services == []


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
        lw_frame_mapping={"l_axis": "horizontal", "w_axis": "vertical"},
        part_model_side_services=[],
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
    assert existing.lw_frame_mapping == {"l_axis": "horizontal", "w_axis": "vertical"}
    assert existing.part_model_side_services == []


def test_create_part_formula_persists_model_editor_fields(monkeypatch: pytest.MonkeyPatch) -> None:
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
        **{
            **_payload_kwargs(),
            "lw_frame_mapping": {"l_axis": "vertical", "w_axis": "horizontal"},
            "part_model_side_services": [
                {"side_index": 0, "service_type_id": str(session.service_type.id)},
            ],
        },
    )

    result = asyncio.run(create_part_formula(payload, session))

    assert result.lw_frame_mapping == {"l_axis": "vertical", "w_axis": "horizontal"}
    assert result.part_model_side_services == [{"side_index": 0, "service_type_id": str(session.service_type.id)}]
    assert session.added.part_model_side_services == [{"side_index": 0, "service_type_id": str(session.service_type.id)}]


def test_create_part_formula_rejects_invalid_lw_mapping(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_require_admin_if_present(session, admin_id):
        return None

    async def fake_validate(*args, **kwargs):
        return None

    monkeypatch.setattr(router, "require_admin_if_present", fake_require_admin_if_present)
    monkeypatch.setattr(router, "_validate_part_formula_expressions", fake_validate)

    payload = PartFormulaCreate(
        admin_id=None,
        part_formula_id=12,
        **{
            **_payload_kwargs(),
            "lw_frame_mapping": {"l_axis": "horizontal", "w_axis": "horizontal"},
        },
    )

    with pytest.raises(router.HTTPException) as exc_info:
        asyncio.run(create_part_formula(payload, FakeSession()))

    assert exc_info.value.status_code == 400
    assert "opposite horizontal/vertical axes" in exc_info.value.detail


def test_create_part_formula_rejects_invalid_side_index(monkeypatch: pytest.MonkeyPatch) -> None:
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
        **{
            **_payload_kwargs(),
            "part_model_side_services": [
                {"side_index": 8, "service_type_id": str(session.service_type.id)},
            ],
        },
    )

    with pytest.raises(router.HTTPException) as exc_info:
        asyncio.run(create_part_formula(payload, session))

    assert exc_info.value.status_code == 400
    assert "out of range" in exc_info.value.detail


def test_create_part_formula_rejects_unknown_service_type(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_require_admin_if_present(session, admin_id):
        return None

    async def fake_validate(*args, **kwargs):
        return None

    monkeypatch.setattr(router, "require_admin_if_present", fake_require_admin_if_present)
    monkeypatch.setattr(router, "_validate_part_formula_expressions", fake_validate)
    session = FakeSession()
    session.service_type = None
    payload = PartFormulaCreate(
        admin_id=None,
        part_formula_id=12,
        **{
            **_payload_kwargs(),
            "part_model_side_services": [
                {"side_index": 1, "service_type_id": str(uuid.uuid4())},
            ],
        },
    )

    with pytest.raises(router.HTTPException) as exc_info:
        asyncio.run(create_part_formula(payload, session))

    assert exc_info.value.status_code == 400
    assert "Unknown service type" in exc_info.value.detail
