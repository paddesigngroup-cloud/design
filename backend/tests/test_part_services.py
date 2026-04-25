from __future__ import annotations

import asyncio
import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from designkp_backend.api.routers import part_services as router
from designkp_backend.api.routers.part_services import (
    PartServiceCreate,
    PartServiceUpdate,
    create_part_service,
    delete_part_service,
    list_part_services,
    update_part_service,
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
        if "max(part_services.sort_order)" in text:
            return 4
        if "lower(part_services.service_code)" in text:
            return self.unique_exists_id
        return None

    async def scalars(self, stmt):
        self.last_scalars_stmt = str(stmt)
        return SimpleNamespace(all=lambda: [])


def test_create_part_service_success(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_require_admin_if_present(session, admin_id):
        return None

    monkeypatch.setattr(router, "require_admin_if_present", fake_require_admin_if_present)
    session = FakeSession()
    payload = PartServiceCreate(
        admin_id=None,
        service_type="  برش CNC  ",
        service_description="  برش دقیق ورق MDF  ",
        service_code="  svc_cut_01  ",
        sort_order=None,
        is_system=True,
    )

    result = asyncio.run(create_part_service(payload, session))

    assert result.service_type == "برش CNC"
    assert result.service_description == "برش دقیق ورق MDF"
    assert result.service_code == "svc_cut_01"
    assert result.sort_order == 5
    assert session.added is not None


def test_update_part_service_success(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_require_admin_if_present(session, admin_id):
        return None

    monkeypatch.setattr(router, "require_admin_if_present", fake_require_admin_if_present)
    existing = SimpleNamespace(
        id=uuid.uuid4(),
        admin_id=None,
        service_type="قدیمی",
        service_description="قدیمی",
        service_code="old_code",
        sort_order=1,
        is_system=True,
    )
    session = FakeSession(item=existing)
    payload = PartServiceUpdate(
        admin_id=None,
        service_type="مونتاژ",
        service_description="مونتاژ کامل قطعات",
        service_code="service_assembly",
        sort_order=9,
        is_system=False,
    )

    result = asyncio.run(update_part_service(existing.id, payload, session))

    assert result.service_type == "مونتاژ"
    assert existing.service_code == "service_assembly"
    assert existing.sort_order == 9
    assert existing.is_system is False


def test_create_part_service_rejects_blank_trimmed_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_require_admin_if_present(session, admin_id):
        return None

    monkeypatch.setattr(router, "require_admin_if_present", fake_require_admin_if_present)
    payload = PartServiceCreate(
        admin_id=None,
        service_type="   ",
        service_description="توضیح",
        service_code="code",
        sort_order=0,
        is_system=True,
    )

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(create_part_service(payload, FakeSession()))

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Service type is required."


def test_create_part_service_rejects_duplicate_code_in_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_require_admin_if_present(session, admin_id):
        return None

    monkeypatch.setattr(router, "require_admin_if_present", fake_require_admin_if_present)
    session = FakeSession()
    session.unique_exists_id = uuid.uuid4()
    payload = PartServiceCreate(
        admin_id=None,
        service_type="خدمات",
        service_description="توضیح",
        service_code="dup_code",
        sort_order=1,
        is_system=True,
    )

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(create_part_service(payload, session))

    assert exc_info.value.status_code == 409
    assert "already exists" in exc_info.value.detail


def test_list_part_services_scope_query_includes_system_and_admin(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_require_admin_if_present(session, admin_id):
        return None

    monkeypatch.setattr(router, "require_admin_if_present", fake_require_admin_if_present)
    session = FakeSession()
    admin_id = uuid.uuid4()

    asyncio.run(list_part_services(admin_id=admin_id, session=session))

    assert session.last_scalars_stmt is not None
    assert "part_services.admin_id IS NULL OR part_services.admin_id =" in session.last_scalars_stmt


def test_delete_part_service_checks_access_scope(monkeypatch: pytest.MonkeyPatch) -> None:
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
        service_description="test",
        service_code="test",
        sort_order=1,
        is_system=False,
    )
    session = FakeSession(item=existing)

    asyncio.run(delete_part_service(existing.id, session))

    assert called["admin_id"] == target_admin_id
