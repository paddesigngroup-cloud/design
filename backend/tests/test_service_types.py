from __future__ import annotations

import asyncio
import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from designkp_backend.api.routers import service_types as router
from designkp_backend.api.routers.service_types import (
    ServiceTypeCreate,
    ServiceTypeUpdate,
    create_service_type,
    delete_service_type,
    list_service_types,
    update_service_type,
)


class FakeSession:
    def __init__(self, item=None) -> None:
        self.item = item
        self.added = None
        self.last_scalars_stmt = None
        self.unique_exists_id = None

    def add(self, item) -> None:
        self.added = item

    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None

    async def refresh(self, item) -> None:
        if getattr(item, "id", None) is None:
            item.id = uuid.uuid4()

    async def delete(self, _item) -> None:
        return None

    async def get(self, _model, _item_id):
        return self.item

    async def scalar(self, stmt):
        text = str(stmt)
        if "max(part_service_types.sort_order)" in text:
            return 3
        if "lower(part_service_types.service_type)" in text and "lower(part_service_types.short_code)" in text:
            return self.unique_exists_id
        return None

    async def scalars(self, stmt):
        self.last_scalars_stmt = str(stmt)
        return SimpleNamespace(all=lambda: [])


def test_create_service_type_success_without_subtraction(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_require_admin_if_present(session, admin_id):
        return None

    monkeypatch.setattr(router, "require_admin_if_present", fake_require_admin_if_present)
    monkeypatch.setattr(router, "finalize_param_group_icon", lambda admin_id, icon_path, previous_file_name=None: f"final::{icon_path}")
    session = FakeSession()
    payload = ServiceTypeCreate(
        admin_id=None,
        service_type="  برش CNC  ",
        service_title="  دورو  ",
        short_code="  dr  ",
        icon_path=" icon.webp ",
        is_common=True,
        has_subtraction=False,
        service_location="back",
        subtraction_shape="circle",
        shape_angles=[],
        axis_to_opposite_edge_distance=12.5,
        axis_to_aligned_edge_distance=8,
        working_diameter=35,
        working_width=0,
        working_height=0,
        working_depth=14.25,
        working_depth_mode="to_end",
        working_depth_end_offset=2.5,
        preview_mirror_x=True,
        preview_mirror_y=False,
        sort_order=None,
        is_system=True,
    )

    result = asyncio.run(create_service_type(payload, session))

    assert result.service_type == "برش CNC"
    assert result.service_title == "دورو"
    assert result.short_code == "dr"
    assert result.icon_path == "icon.webp"
    assert result.is_common is True
    assert result.has_subtraction is False
    assert result.service_location is None
    assert result.subtraction_shape is None
    assert result.shape_angles is None
    assert result.axis_to_opposite_edge_distance == 12.5
    assert result.axis_to_aligned_edge_distance == 8
    assert result.working_diameter == 35
    assert result.working_width == 0
    assert result.working_height == 0
    assert result.working_depth == 14.2
    assert result.working_depth_mode == "to_end"
    assert result.working_depth_end_offset == 2.5
    assert result.preview_mirror_x is True
    assert result.preview_mirror_y is False
    assert result.sort_order == 4
    assert session.added is not None


def test_update_service_type_success_with_circle_subtraction(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_require_admin_if_present(session, admin_id):
        return None

    monkeypatch.setattr(router, "require_admin_if_present", fake_require_admin_if_present)
    monkeypatch.setattr(router, "finalize_param_group_icon", lambda admin_id, icon_path, previous_file_name=None: f"final::{icon_path}")
    existing = SimpleNamespace(
        id=uuid.uuid4(),
        admin_id=None,
        service_type="قدیمی",
        service_title="قدیمی",
        short_code="old_code",
        icon_path=None,
        is_common=False,
        has_subtraction=False,
        service_location=None,
        subtraction_shape=None,
        shape_angles=None,
        axis_to_opposite_edge_distance=0,
        axis_to_aligned_edge_distance=0,
        working_diameter=0,
        working_width=0,
        working_height=0,
        working_depth=0,
        working_depth_mode="fixed",
        working_depth_end_offset=0,
        preview_mirror_x=False,
        preview_mirror_y=False,
        sort_order=1,
        is_system=True,
    )
    session = FakeSession(item=existing)
    payload = ServiceTypeUpdate(
        admin_id=None,
        service_type="مونتاژ",
        service_title="مونتاژ بدنه",
        short_code="asm",
        icon_path="assembly.webp",
        is_common=True,
        has_subtraction=True,
        service_location="thickness",
        subtraction_shape="circle",
        shape_angles=[],
        axis_to_opposite_edge_distance=4,
        axis_to_aligned_edge_distance=6.5,
        working_diameter=12,
        working_width=0,
        working_height=0,
        working_depth=7,
        working_depth_mode="to_end",
        working_depth_end_offset=1.5,
        preview_mirror_x=True,
        preview_mirror_y=True,
        sort_order=8,
        is_system=False,
    )

    result = asyncio.run(update_service_type(existing.id, payload, session))

    assert result.service_type == "مونتاژ"
    assert existing.service_title == "مونتاژ بدنه"
    assert existing.short_code == "asm"
    assert existing.icon_path == "assembly.webp"
    assert existing.is_common is True
    assert existing.has_subtraction is True
    assert existing.service_location == "thickness"
    assert existing.subtraction_shape == "circle"
    assert existing.shape_angles == []
    assert existing.axis_to_opposite_edge_distance == 4
    assert existing.axis_to_aligned_edge_distance == 6.5
    assert existing.working_diameter == 12
    assert existing.working_width == 0
    assert existing.working_height == 0
    assert existing.working_depth == 7
    assert existing.working_depth_mode == "to_end"
    assert existing.working_depth_end_offset == 1.5
    assert existing.preview_mirror_x is True
    assert existing.preview_mirror_y is True
    assert existing.sort_order == 8
    assert existing.is_system is False


def test_create_service_type_rejects_blank_trimmed_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_require_admin_if_present(session, admin_id):
        return None

    monkeypatch.setattr(router, "require_admin_if_present", fake_require_admin_if_present)
    payload = ServiceTypeCreate(
        admin_id=None,
        service_type="   ",
        service_title="عنوان",
        short_code="code",
        icon_path=None,
        is_common=False,
        has_subtraction=False,
        sort_order=0,
        is_system=True,
    )

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(create_service_type(payload, FakeSession()))

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Service type is required."


def test_create_service_type_rejects_duplicate_short_code_in_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_require_admin_if_present(session, admin_id):
        return None

    monkeypatch.setattr(router, "require_admin_if_present", fake_require_admin_if_present)
    session = FakeSession()
    session.unique_exists_id = uuid.uuid4()
    payload = ServiceTypeCreate(
        admin_id=None,
        service_type="خدمات",
        service_title="توضیح",
        short_code="dup",
        icon_path=None,
        is_common=False,
        has_subtraction=False,
        sort_order=1,
        is_system=True,
    )

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(create_service_type(payload, session))

    assert exc_info.value.status_code == 409
    assert "already exists" in exc_info.value.detail


def test_list_service_types_scope_query_includes_system_and_admin(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_require_admin_if_present(session, admin_id):
        return None

    monkeypatch.setattr(router, "require_admin_if_present", fake_require_admin_if_present)
    session = FakeSession()
    admin_id = uuid.uuid4()

    asyncio.run(list_service_types(admin_id=admin_id, session=session))

    assert session.last_scalars_stmt is not None
    assert "part_service_types.admin_id IS NULL OR part_service_types.admin_id =" in session.last_scalars_stmt


def test_delete_service_type_checks_access_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    called = {"admin_id": None}

    async def fake_require_admin_if_present(session, admin_id):
        called["admin_id"] = admin_id
        return None

    monkeypatch.setattr(router, "require_admin_if_present", fake_require_admin_if_present)
    target_admin_id = uuid.uuid4()
    existing = SimpleNamespace(
        id=uuid.uuid4(),
        admin_id=target_admin_id,
        service_type="test",
        service_title="title",
        short_code="test",
        icon_path="icon.webp",
        has_subtraction=False,
        service_location=None,
        subtraction_shape=None,
        shape_angles=None,
        axis_to_opposite_edge_distance=0,
        axis_to_aligned_edge_distance=0,
        working_diameter=0,
        working_width=0,
        working_height=0,
        working_depth=0,
        working_depth_mode="fixed",
        working_depth_end_offset=0,
        preview_mirror_x=False,
        preview_mirror_y=False,
        sort_order=1,
        is_system=False,
    )
    session = FakeSession(item=existing)

    asyncio.run(delete_service_type(existing.id, session))

    assert called["admin_id"] == target_admin_id


def test_create_service_type_rejects_invalid_service_location(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_require_admin_if_present(session, admin_id):
        return None

    monkeypatch.setattr(router, "require_admin_if_present", fake_require_admin_if_present)
    payload = ServiceTypeCreate(
        admin_id=None,
        service_type="خدمات",
        service_title="توضیح",
        short_code="code",
        icon_path=None,
        has_subtraction=True,
        service_location="left",
        subtraction_shape="circle",
        shape_angles=[],
        sort_order=1,
        is_system=True,
    )

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(create_service_type(payload, FakeSession()))

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Service location must be front, back, or thickness."


def test_create_service_type_rejects_invalid_triangle_angles(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_require_admin_if_present(session, admin_id):
        return None

    monkeypatch.setattr(router, "require_admin_if_present", fake_require_admin_if_present)
    payload = ServiceTypeCreate(
        admin_id=None,
        service_type="خدمات",
        service_title="توضیح",
        short_code="tri",
        icon_path=None,
        has_subtraction=True,
        service_location="front",
        subtraction_shape="triangle",
        shape_angles=[
            {"index": 0, "angle_deg": 50},
            {"index": 1, "angle_deg": 50},
            {"index": 2, "angle_deg": 50},
        ],
        sort_order=1,
        is_system=True,
    )

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(create_service_type(payload, FakeSession()))

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Triangle shape angles must sum to 180."


def test_create_service_type_rejects_invalid_rectangle_angle_count(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_require_admin_if_present(session, admin_id):
        return None

    monkeypatch.setattr(router, "require_admin_if_present", fake_require_admin_if_present)
    payload = ServiceTypeCreate(
        admin_id=None,
        service_type="خدمات",
        service_title="توضیح",
        short_code="rect",
        icon_path=None,
        has_subtraction=True,
        service_location="back",
        subtraction_shape="rectangle",
        shape_angles=[
            {"index": 0, "angle_deg": 90},
            {"index": 1, "angle_deg": 90},
            {"index": 2, "angle_deg": 90},
        ],
        sort_order=1,
        is_system=True,
    )

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(create_service_type(payload, FakeSession()))

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Rectangle shape must contain exactly 4 angles."


def test_delete_service_type_removes_owned_icon(monkeypatch: pytest.MonkeyPatch) -> None:
    deleted = {"admin_id": None, "icon_path": None}

    async def fake_require_admin_if_present(session, admin_id):
        return None

    def fake_delete_final_icon(admin_id, icon_path):
        deleted["admin_id"] = admin_id
        deleted["icon_path"] = icon_path

    monkeypatch.setattr(router, "require_admin_if_present", fake_require_admin_if_present)
    monkeypatch.setattr(router, "delete_final_icon", fake_delete_final_icon)
    target_admin_id = uuid.uuid4()
    existing = SimpleNamespace(
        id=uuid.uuid4(),
        admin_id=target_admin_id,
        service_type="test",
        service_title="title",
        short_code="test",
        icon_path="icon.webp",
        has_subtraction=False,
        service_location=None,
        subtraction_shape=None,
        shape_angles=None,
        axis_to_opposite_edge_distance=0,
        axis_to_aligned_edge_distance=0,
        working_diameter=0,
        working_width=0,
        working_height=0,
        working_depth=0,
        working_depth_mode="fixed",
        working_depth_end_offset=0,
        sort_order=1,
        is_system=False,
    )
    session = FakeSession(item=existing)

    asyncio.run(delete_service_type(existing.id, session))

    assert deleted["admin_id"] == target_admin_id
    assert deleted["icon_path"] == "icon.webp"
