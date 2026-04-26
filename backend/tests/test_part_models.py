from __future__ import annotations

import asyncio
import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from designkp_backend.api.routers import part_models as router
from designkp_backend.api.routers.part_models import (
    PartModelCreate,
    PartModelUpdate,
    create_part_model,
    delete_part_model,
    list_part_models,
    update_part_model,
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
        if "max(part_models.sort_order)" in text:
            return 6
        if "lower(part_models.title)" in text:
            return self.unique_exists_id
        return None

    async def scalars(self, stmt):
        self.last_scalars_stmt = str(stmt)
        return SimpleNamespace(all=lambda: [])


def test_create_part_model_success(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_require_admin_if_present(session, admin_id):
        return None

    monkeypatch.setattr(router, "require_admin_if_present", fake_require_admin_if_present)
    session = FakeSession()
    payload = PartModelCreate(
        admin_id=None,
        title="  شش ضلعی  ",
        side_count=6,
        interior_angle_sum=720,
        default_angles=[
            {"index": 0, "angle_deg": 120},
            {"index": 1, "angle_deg": 120},
            {"index": 2, "angle_deg": 120},
            {"index": 3, "angle_deg": 120},
            {"index": 4, "angle_deg": 120},
            {"index": 5, "angle_deg": 120},
        ],
        sort_order=None,
        is_system=True,
    )

    result = asyncio.run(create_part_model(payload, session))

    assert result.title == "شش ضلعی"
    assert result.side_count == 6
    assert result.interior_angle_sum == 720
    assert len(result.default_angles) == 6
    assert result.default_angles[0].angle_deg == 120
    assert result.sort_order == 7
    assert session.added is not None


def test_create_part_model_calculates_angle_sum_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_require_admin_if_present(session, admin_id):
        return None

    monkeypatch.setattr(router, "require_admin_if_present", fake_require_admin_if_present)
    result = asyncio.run(create_part_model(
        PartModelCreate(admin_id=None, title="پنج ضلعی", side_count=5, interior_angle_sum=None, sort_order=1, is_system=True),
        FakeSession(),
    ))

    assert result.interior_angle_sum == 540
    assert len(result.default_angles) == 5
    assert sum(item.angle_deg for item in result.default_angles) == pytest.approx(540)


def test_update_part_model_success(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_require_admin_if_present(session, admin_id):
        return None

    monkeypatch.setattr(router, "require_admin_if_present", fake_require_admin_if_present)
    existing = SimpleNamespace(
        id=uuid.uuid4(),
        admin_id=None,
        title="قدیمی",
        side_count=4,
        interior_angle_sum=360,
        sort_order=1,
        is_system=True,
    )
    session = FakeSession(item=existing)
    payload = PartModelUpdate(
        admin_id=None,
        title="هشت ضلعی",
        side_count=8,
        interior_angle_sum=1080,
        default_angles=[
            {"index": 0, "angle_deg": 120},
            {"index": 1, "angle_deg": 120},
            {"index": 2, "angle_deg": 120},
            {"index": 3, "angle_deg": 120},
            {"index": 4, "angle_deg": 150},
            {"index": 5, "angle_deg": 150},
            {"index": 6, "angle_deg": 150},
            {"index": 7, "angle_deg": 150},
        ],
        sort_order=9,
        is_system=False,
    )

    result = asyncio.run(update_part_model(existing.id, payload, session))

    assert result.title == "هشت ضلعی"
    assert existing.side_count == 8
    assert existing.interior_angle_sum == 1080
    assert len(existing.default_angles) == 8
    assert existing.sort_order == 9
    assert existing.is_system is False


def test_create_part_model_rejects_invalid_angle_sum(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_require_admin_if_present(session, admin_id):
        return None

    monkeypatch.setattr(router, "require_admin_if_present", fake_require_admin_if_present)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(create_part_model(
            PartModelCreate(admin_id=None, title="مثلث", side_count=3, interior_angle_sum=999, sort_order=0, is_system=True),
            FakeSession(),
        ))

    assert exc_info.value.status_code == 400
    assert "Interior angle sum must equal 180" in exc_info.value.detail


def test_create_part_model_rejects_invalid_default_angle_count(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_require_admin_if_present(session, admin_id):
        return None

    monkeypatch.setattr(router, "require_admin_if_present", fake_require_admin_if_present)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(create_part_model(
            PartModelCreate(
                admin_id=None,
                title="چهارضلعی",
                side_count=4,
                interior_angle_sum=360,
                default_angles=[
                    {"index": 0, "angle_deg": 90},
                    {"index": 1, "angle_deg": 90},
                ],
                sort_order=0,
                is_system=True,
            ),
            FakeSession(),
        ))

    assert exc_info.value.status_code == 400
    assert "exactly 4 items" in exc_info.value.detail


def test_create_part_model_rejects_invalid_default_angle_sum(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_require_admin_if_present(session, admin_id):
        return None

    monkeypatch.setattr(router, "require_admin_if_present", fake_require_admin_if_present)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(create_part_model(
            PartModelCreate(
                admin_id=None,
                title="پنج ضلعی نامعتبر",
                side_count=5,
                interior_angle_sum=540,
                default_angles=[
                    {"index": 0, "angle_deg": 100},
                    {"index": 1, "angle_deg": 100},
                    {"index": 2, "angle_deg": 100},
                    {"index": 3, "angle_deg": 100},
                    {"index": 4, "angle_deg": 100},
                ],
                sort_order=0,
                is_system=True,
            ),
            FakeSession(),
        ))

    assert exc_info.value.status_code == 400
    assert "must sum to 540" in exc_info.value.detail


def test_create_part_model_rejects_non_positive_default_angle() -> None:
    with pytest.raises(ValidationError) as exc_info:
        PartModelCreate(
            admin_id=None,
            title="چهارضلعی صفر",
            side_count=4,
            interior_angle_sum=360,
            default_angles=[
                {"index": 0, "angle_deg": 0},
                {"index": 1, "angle_deg": 120},
                {"index": 2, "angle_deg": 120},
                {"index": 3, "angle_deg": 120},
            ],
            sort_order=0,
            is_system=True,
        )

    assert "greater than 0" in str(exc_info.value)


def test_list_part_models_scope_query_includes_system_and_admin(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_require_admin_if_present(session, admin_id):
        return None

    monkeypatch.setattr(router, "require_admin_if_present", fake_require_admin_if_present)
    session = FakeSession()
    admin_id = uuid.uuid4()

    asyncio.run(list_part_models(admin_id=admin_id, session=session))

    assert session.last_scalars_stmt is not None
    assert "part_models.admin_id IS NULL OR part_models.admin_id =" in session.last_scalars_stmt


def test_delete_part_model_checks_access_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    called = {"admin_id": None}

    async def fake_require_admin_if_present(session, admin_id):
        called["admin_id"] = admin_id
        return None

    monkeypatch.setattr(router, "require_admin_if_present", fake_require_admin_if_present)
    target_admin_id = uuid.uuid4()
    existing = SimpleNamespace(
        id=uuid.uuid4(),
        admin_id=target_admin_id,
        title="test",
        side_count=4,
        interior_angle_sum=360,
        default_angles=[
            {"index": 0, "angle_deg": 90},
            {"index": 1, "angle_deg": 90},
            {"index": 2, "angle_deg": 90},
            {"index": 3, "angle_deg": 90},
        ],
        sort_order=1,
        is_system=False,
    )
    session = FakeSession(item=existing)

    asyncio.run(delete_part_model(existing.id, session))

    assert called["admin_id"] == target_admin_id
