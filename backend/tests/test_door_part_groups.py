from __future__ import annotations

import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest

from designkp_backend.api.routers import door_part_groups as router
from designkp_backend.api.routers.door_part_groups import (
    DOOR_PART_GROUP_CONTROLLER_TYPE_BACK_TO_BACK_OPENING,
    DOOR_PART_GROUP_CONTROLLER_TYPE_DOUBLE_EQUAL_HINGED,
    DoorPartGroupControllerBindingPayload,
    DoorPartGroupControllerSelectionPayload,
    DoorPartGroupCreate,
    DoorPartGroupParamGroupSelectionPayload,
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

    async def delete(self, _item) -> None:
        return None

    async def scalar(self, stmt):
        text = str(stmt)
        if "max(door_part_groups.group_id)" in text:
            return 3
        return self.item

    async def scalars(self, stmt):
        return SimpleNamespace(all=lambda: [])

    async def execute(self, stmt):
        if "to_regclass" in str(stmt):
            return SimpleNamespace(one=lambda: ("door_part_group_param_groups",))
        raise AssertionError(f"Unexpected execute call: {stmt}")


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

    async def fake_replace_group_param_groups(session, *, group, param_groups):
        group.__dict__["param_groups"] = [
            SimpleNamespace(
                id=uuid4(),
                param_group_id=param_groups[0].param_group_id,
                param_group_code="door_width",
                param_group_title="گروه عرض درب",
                param_group_icon_path=None,
                enabled=True,
                ui_order=0,
            )
        ]

    async def fake_apply_group_controller_config(session, *, group, controller_type, controller_selection, controller_bindings):
        group.controller_type = controller_type
        group.controller_selection = [
            {"axis": str(item.axis), "part_formula_id": int(item.part_formula_id)}
            for item in controller_selection
        ]
        group.controller_bindings = {
            key: {"param_code": str(value.param_code) if value.param_code is not None else None}
            for key, value in controller_bindings.items()
        }

    async def fake_load_group(session, group_uuid):
        if getattr(session.added, "id", None) is None:
            session.added.id = uuid4()
        return session.added

    monkeypatch.setattr(router, "require_admin_if_present", fake_require_admin_if_present)
    monkeypatch.setattr(router, "_replace_group_parts", fake_replace_group_parts)
    monkeypatch.setattr(router, "_replace_group_param_groups", fake_replace_group_param_groups)
    monkeypatch.setattr(router, "_apply_group_controller_config", fake_apply_group_controller_config)
    monkeypatch.setattr(router, "_ensure_unique_group_code", lambda *args, **kwargs: asyncio.sleep(0))
    monkeypatch.setattr(router, "_load_group", fake_load_group)

    session = FakeSession()
    payload = DoorPartGroupCreate(
        admin_id=None,
        group_id=4,
        group_title="گروه درب",
        code="door_group",
        line_color="#8A98A3",
        sort_order=4,
        is_system=True,
        parts=[DoorPartGroupPartSelectionPayload(part_formula_id=12, enabled=True, ui_order=0)],
        param_groups=[DoorPartGroupParamGroupSelectionPayload(param_group_id=9, enabled=True, ui_order=0)],
        controller_type=DOOR_PART_GROUP_CONTROLLER_TYPE_DOUBLE_EQUAL_HINGED,
        controller_selection=[
            DoorPartGroupControllerSelectionPayload(axis="vertical", part_formula_id=12),
            DoorPartGroupControllerSelectionPayload(axis="horizontal", part_formula_id=13),
        ],
        controller_bindings={
            "door_width": DoorPartGroupControllerBindingPayload(param_code="door_width"),
            "door_height": DoorPartGroupControllerBindingPayload(param_code="door_height"),
            "left": DoorPartGroupControllerBindingPayload(param_code="left_gap"),
            "right": DoorPartGroupControllerBindingPayload(param_code="right_gap"),
            "top": DoorPartGroupControllerBindingPayload(param_code="top_gap"),
            "bottom_offset": DoorPartGroupControllerBindingPayload(param_code="bottom_gap"),
        },
    )

    result = asyncio.run(create_door_part_group(payload, session))

    assert result.group_id == 4
    assert result.line_color == "#8A98A3"
    assert result.parts[0].part_formula_id == 12
    assert result.param_groups[0].param_group_id == 9
    assert result.controller_type == DOOR_PART_GROUP_CONTROLLER_TYPE_DOUBLE_EQUAL_HINGED
    assert len(result.controller_selection) == 2
    assert result.controller_bindings["door_width"].param_code == "door_width"
    assert result.controller_bindings["door_height"].param_code == "door_height"
    assert result.controller_bindings["left"].param_code == "left_gap"
    assert result.controller_bindings["right"].param_code == "right_gap"
    assert result.controller_bindings["top"].param_code == "top_gap"
    assert result.controller_bindings["bottom_offset"].param_code == "bottom_gap"


def test_update_door_part_group_updates_basic_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_require_admin_if_present(session, admin_id):
        return None

    async def fake_replace_group_parts(session, *, group, parts):
        group.__dict__["parts"] = []

    async def fake_replace_group_param_groups(session, *, group, param_groups):
        group.__dict__["param_groups"] = []

    async def fake_apply_group_controller_config(session, *, group, controller_type, controller_selection, controller_bindings):
        group.controller_type = controller_type
        group.controller_selection = [
            {"axis": str(item.axis), "part_formula_id": int(item.part_formula_id)}
            for item in controller_selection
        ]
        group.controller_bindings = {
            key: {"param_code": str(value.param_code) if value.param_code is not None else None}
            for key, value in controller_bindings.items()
        }

    async def fake_load_group(session, group_uuid):
        return session.item

    monkeypatch.setattr(router, "require_admin_if_present", fake_require_admin_if_present)
    monkeypatch.setattr(router, "_replace_group_parts", fake_replace_group_parts)
    monkeypatch.setattr(router, "_replace_group_param_groups", fake_replace_group_param_groups)
    monkeypatch.setattr(router, "_apply_group_controller_config", fake_apply_group_controller_config)
    monkeypatch.setattr(router, "_ensure_unique_group_code", lambda *args, **kwargs: asyncio.sleep(0))
    monkeypatch.setattr(router, "_load_group", fake_load_group)

    existing = SimpleNamespace(
        id=uuid4(),
        admin_id=None,
        group_id=4,
        group_title="قدیمی",
        code="old_code",
        title="قدیمی",
        line_color="#8A98A3",
        sort_order=4,
        is_system=True,
        parts=[],
        param_groups=[],
        controller_type=None,
        controller_selection=[],
        controller_bindings={},
    )
    session = FakeSession(item=existing)
    payload = DoorPartGroupUpdate(
        admin_id=None,
        group_id=4,
        group_title="جدید",
        code="new_code",
        line_color="#0091FF",
        sort_order=7,
        is_system=False,
        parts=[],
        param_groups=[],
        controller_type=DOOR_PART_GROUP_CONTROLLER_TYPE_DOUBLE_EQUAL_HINGED,
        controller_selection=[
            DoorPartGroupControllerSelectionPayload(axis="vertical", part_formula_id=21),
            DoorPartGroupControllerSelectionPayload(axis="horizontal", part_formula_id=22),
        ],
        controller_bindings={
            "door_width": DoorPartGroupControllerBindingPayload(param_code="door_width"),
            "door_height": DoorPartGroupControllerBindingPayload(param_code="door_height"),
            "left": DoorPartGroupControllerBindingPayload(param_code="left_gap"),
            "right": DoorPartGroupControllerBindingPayload(param_code="right_gap"),
            "top": DoorPartGroupControllerBindingPayload(param_code="top_gap"),
            "bottom_offset": DoorPartGroupControllerBindingPayload(param_code="bottom_gap"),
        },
    )

    result = asyncio.run(update_door_part_group(existing.id, payload, session))

    assert result.group_title == "جدید"
    assert existing.code == "new_code"
    assert existing.line_color == "#0091FF"
    assert existing.sort_order == 7
    assert result.controller_type == DOOR_PART_GROUP_CONTROLLER_TYPE_DOUBLE_EQUAL_HINGED
    assert len(result.controller_selection) == 2
    assert result.controller_bindings["door_width"].param_code == "door_width"
    assert result.controller_bindings["door_height"].param_code == "door_height"
