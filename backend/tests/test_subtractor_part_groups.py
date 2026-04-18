from __future__ import annotations

import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from designkp_backend.api.routers import subtractor_part_groups as router
from designkp_backend.api.routers.subtractor_part_groups import (
    SubtractorPartGroupControllerBindingPayload,
    SubtractorPartGroupCreate,
    SubtractorPartGroupParamGroupSelectionPayload,
    SubtractorPartGroupPartSelectionPayload,
    SubtractorPartGroupUpdate,
    create_subtractor_part_group,
    update_subtractor_part_group,
)


class FakeSession:
    def __init__(self, item=None) -> None:
        self.item = item
        self.added = None
        self.last_scalars_stmt = None

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
        if "max(subtractor_part_groups.group_id)" in text:
            return 3
        return self.item

    async def scalars(self, stmt):
        self.last_scalars_stmt = str(stmt)
        return SimpleNamespace(all=lambda: [])

    async def execute(self, stmt):
        text = str(stmt)
        if "to_regclass" in text:
            return SimpleNamespace(one=lambda: ("ok",))
        raise AssertionError(f"Unexpected execute call: {stmt}")


def test_create_subtractor_part_group_uses_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_require_admin_if_present(session, admin_id):
        return None

    async def fake_replace_group_parts(session, *, group, parts):
        group.__dict__["parts"] = [
            SimpleNamespace(
                id=uuid4(),
                part_formula_id=parts[0].part_formula_id,
                part_kind_id=6,
                part_code="handle_hidden",
                part_title="دستگیره مخفی",
                enabled=True,
                ui_order=0,
            )
        ]

    async def fake_replace_group_param_groups(session, *, group, param_groups):
        group.__dict__["param_groups"] = [
            SimpleNamespace(
                id=uuid4(),
                param_group_id=param_groups[0].param_group_id,
                param_group_code="u_th",
                param_group_title="گروه ضخامت",
                param_group_icon_path=None,
                enabled=True,
                ui_order=0,
            )
        ]

    async def fake_apply_group_controller_config(session, group, *, controller_type, controller_bindings):
        group.controller_type = controller_type
        group.controller_bindings = {
            key: {"param_code": str(value.param_code) if value.param_code is not None else None}
            for key, value in controller_bindings.items()
        }

    async def fake_load_group(session, group_uuid, **_kwargs):
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
    payload = SubtractorPartGroupCreate(
        admin_id=None,
        group_id=4,
        group_title="گروه دستگیره مخفی",
        code="hidden_handle_group",
        line_color="#8A98A3",
        sort_order=4,
        is_system=True,
        parts=[SubtractorPartGroupPartSelectionPayload(part_formula_id=12, enabled=True, ui_order=0)],
        param_groups=[SubtractorPartGroupParamGroupSelectionPayload(param_group_id=9, enabled=True, ui_order=0)],
        controller_type=router.SUBTRACTOR_GROUP_CONTROLLER_TYPE_WIDTH_NO_TOP,
        controller_bindings={
            "left": SubtractorPartGroupControllerBindingPayload(param_code="left_gap"),
            "top": SubtractorPartGroupControllerBindingPayload(param_code="top_gap"),
            "right": SubtractorPartGroupControllerBindingPayload(param_code="right_gap"),
            "bottom_offset": SubtractorPartGroupControllerBindingPayload(param_code="bottom_gap"),
        },
    )

    result = asyncio.run(create_subtractor_part_group(payload, session))

    assert result.group_id == 4
    assert result.line_color == "#8A98A3"
    assert result.parts[0].part_formula_id == 12
    assert result.param_groups[0].param_group_id == 9
    assert result.controller_type == router.SUBTRACTOR_GROUP_CONTROLLER_TYPE_WIDTH_NO_TOP
    assert result.controller_bindings["left"].param_code == "left_gap"


def test_update_subtractor_part_group_updates_basic_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_require_admin_if_present(session, admin_id):
        return None

    async def fake_replace_group_parts(session, *, group, parts):
        group.__dict__["parts"] = []

    async def fake_replace_group_param_groups(session, *, group, param_groups):
        group.__dict__["param_groups"] = []

    async def fake_apply_group_controller_config(session, group, *, controller_type, controller_bindings):
        group.controller_type = controller_type
        group.controller_bindings = {
            key: {"param_code": str(value.param_code) if value.param_code is not None else None}
            for key, value in controller_bindings.items()
        }

    async def fake_load_group(session, group_uuid, **_kwargs):
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
        param_defaults=[],
        controller_type=None,
        controller_bindings={},
    )
    session = FakeSession(item=existing)
    payload = SubtractorPartGroupUpdate(
        admin_id=None,
        group_id=4,
        group_title="جدید",
        code="new_code",
        line_color="#0091FF",
        sort_order=7,
        is_system=False,
        parts=[],
        param_groups=[],
        controller_type=router.SUBTRACTOR_GROUP_CONTROLLER_TYPE_WIDTH_NO_TOP,
        controller_bindings={
            "left": SubtractorPartGroupControllerBindingPayload(param_code="left_gap"),
            "top": SubtractorPartGroupControllerBindingPayload(param_code="top_gap"),
            "right": SubtractorPartGroupControllerBindingPayload(param_code="right_gap"),
            "bottom_offset": SubtractorPartGroupControllerBindingPayload(param_code="bottom_gap"),
        },
    )

    result = asyncio.run(update_subtractor_part_group(existing.id, payload, session))

    assert result.group_title == "جدید"
    assert existing.code == "new_code"
    assert existing.line_color == "#0091FF"
    assert existing.sort_order == 7
    assert result.controller_type == router.SUBTRACTOR_GROUP_CONTROLLER_TYPE_WIDTH_NO_TOP
    assert result.controller_bindings["left"].param_code == "left_gap"


def test_require_accessible_subtractor_part_formulas_enforces_scope_in_query() -> None:
    class _Session(FakeSession):
        async def scalars(self, stmt):
            self.last_scalars_stmt = str(stmt)
            return SimpleNamespace(
                all=lambda: [
                    SimpleNamespace(
                        part_formula_id=1,
                        part_kind_id=2,
                        part_code="handle_hidden",
                        part_title="دستگیره مخفی",
                    )
                ]
            )

    session = _Session()
    asyncio.run(
        router._require_accessible_subtractor_part_formulas(
            session,
            admin_id=None,
            part_formula_ids=[1],
        )
    )
    assert "part_kinds.part_scope" in str(session.last_scalars_stmt)


def test_apply_group_controller_config_rejects_param_out_of_group_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    group = SimpleNamespace(
        id=uuid4(),
        admin_id=None,
        controller_type=None,
        controller_bindings={},
    )

    async def fake_params_for_subtractor_group(_session, _group):
        return [SimpleNamespace(param_code="left_gap"), SimpleNamespace(param_code="right_gap")]

    monkeypatch.setattr(router, "_params_for_subtractor_group", fake_params_for_subtractor_group)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            router._apply_group_controller_config(
                FakeSession(),
                group,
                controller_type=router.SUBTRACTOR_GROUP_CONTROLLER_TYPE_WIDTH_NO_TOP,
                controller_bindings={
                    "left": SubtractorPartGroupControllerBindingPayload(param_code="outside_scope"),
                    "top": SubtractorPartGroupControllerBindingPayload(param_code=None),
                    "right": SubtractorPartGroupControllerBindingPayload(param_code="right_gap"),
                    "bottom_offset": SubtractorPartGroupControllerBindingPayload(param_code=None),
                },
            )
        )

    assert exc.value.status_code == 400
    assert "Unknown controller param code" in str(exc.value.detail)


def test_sync_group_param_defaults_only_seeds_default_values(monkeypatch: pytest.MonkeyPatch) -> None:
    param = SimpleNamespace(param_id=10, param_code="u_th", param_title_fa="ضخامت یونیت", title="Unit Thickness")
    seed_row = SimpleNamespace(
        param_id=10,
        display_title="ضخامت بدنه",
        default_value="18",
        icon_path="seed-icon.webp",
        input_mode="binary",
        binary_off_label="خاموش",
        binary_on_label="روشن",
        binary_off_icon_path="off.webp",
        binary_on_icon_path="on.webp",
        description_text="توضیح نمونه",
    )
    existing_row = SimpleNamespace(
        param_id=10,
        display_title="ضخامت یونیت",
        default_value=None,
        icon_path=None,
        input_mode="value",
        binary_off_label="0",
        binary_on_label="1",
        binary_off_icon_path=None,
        binary_on_icon_path=None,
        description_text=None,
    )
    group = SimpleNamespace(id=uuid4(), admin_id=None)
    group.__dict__["param_groups"] = [SimpleNamespace(param_group_id=1, enabled=True)]

    class _FakeScalarsResult:
        def __init__(self, rows):
            self._rows = rows

        def all(self):
            return list(self._rows)

    class _FakeDefaultsSession:
        def __init__(self, defaults):
            self.defaults = defaults
            self.deleted = []

        async def scalars(self, stmt):
            if "FROM subtractor_part_group_param_defaults" in str(stmt):
                return _FakeScalarsResult(self.defaults)
            return _FakeScalarsResult([])

        async def delete(self, row):
            self.deleted.append(row)

        async def flush(self):
            return None

        def add(self, _item):
            raise AssertionError("No new rows should be added in this test")

    async def fake_params_for_subtractor_group(_session, _group):
        return [param]

    async def fake_load_first_sub_category_default_seed(_session, *, admin_id, param_ids):
        assert admin_id is None
        assert param_ids == {10}
        return {10: seed_row}

    monkeypatch.setattr(router, "_params_for_subtractor_group", fake_params_for_subtractor_group)
    monkeypatch.setattr(router, "_load_first_sub_category_default_seed", fake_load_first_sub_category_default_seed)

    changed = asyncio.run(router._sync_group_param_defaults(_FakeDefaultsSession([existing_row]), group))

    assert changed is True
    assert existing_row.default_value == "18"
