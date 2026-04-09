from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from designkp_backend.db.dependencies import get_db_session
from designkp_backend.db.models.catalog import PartKind
from designkp_backend.services.admin_access import require_admin_if_present

router = APIRouter(prefix="/part-kinds", tags=["part_kinds"])
VALID_PART_SCOPES = {"structural", "internal", "door"}


class PartKindItem(BaseModel):
    id: uuid.UUID
    admin_id: uuid.UUID | None
    part_kind_id: int
    part_kind_code: str
    org_part_kind_title: str
    code: str
    title: str
    sort_order: int
    part_scope: str
    is_system: bool

    model_config = {"from_attributes": True}


class PartKindCreate(BaseModel):
    admin_id: uuid.UUID | None = None
    part_kind_id: int | None = Field(default=None, ge=1)
    part_kind_code: str = Field(min_length=1, max_length=64)
    org_part_kind_title: str = Field(min_length=1, max_length=255)
    sort_order: int | None = Field(default=None, ge=0)
    part_scope: str = Field(default="structural", pattern="^(structural|internal|door)$")
    is_system: bool = False


class PartKindUpdate(BaseModel):
    admin_id: uuid.UUID | None = None
    part_kind_id: int = Field(ge=1)
    part_kind_code: str = Field(min_length=1, max_length=64)
    org_part_kind_title: str = Field(min_length=1, max_length=255)
    sort_order: int = Field(ge=0)
    part_scope: str = Field(default="structural", pattern="^(structural|internal|door)$")
    is_system: bool


def _normalize_part_scope(value: str | None) -> str:
    normalized = str(value or "").strip().lower() or "structural"
    if normalized not in VALID_PART_SCOPES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid part scope.")
    return normalized


def _to_response(item: PartKind) -> PartKindItem:
    return PartKindItem.model_validate(item)


async def _next_part_kind_id(session: AsyncSession) -> int:
    max_id = await session.scalar(select(func.max(PartKind.part_kind_id)))
    return int(max_id or 0) + 1


@router.get("", response_model=list[PartKindItem])
async def list_part_kinds(
    admin_id: uuid.UUID | None = Query(default=None),
    session: AsyncSession = Depends(get_db_session),
) -> list[PartKindItem]:
    await require_admin_if_present(session, admin_id)
    stmt = (
        select(PartKind)
        .where(or_(PartKind.admin_id.is_(None), PartKind.admin_id == admin_id))
        .order_by(PartKind.sort_order.asc(), PartKind.part_kind_id.asc())
    )
    items = (await session.scalars(stmt)).all()
    return [_to_response(item) for item in items]


@router.post("", response_model=PartKindItem, status_code=status.HTTP_201_CREATED)
async def create_part_kind(payload: PartKindCreate, session: AsyncSession = Depends(get_db_session)) -> PartKindItem:
    await require_admin_if_present(session, payload.admin_id)
    next_id = payload.part_kind_id or await _next_part_kind_id(session)
    item = PartKind(
        admin_id=payload.admin_id,
        part_kind_id=next_id,
        part_kind_code=payload.part_kind_code.strip(),
        org_part_kind_title=payload.org_part_kind_title.strip(),
        code=payload.part_kind_code.strip(),
        title=payload.org_part_kind_title.strip(),
        sort_order=payload.sort_order if payload.sort_order is not None else next_id,
        part_scope=_normalize_part_scope(payload.part_scope),
        is_system=payload.is_system,
    )
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return _to_response(item)


@router.patch("/{part_kind_uuid}", response_model=PartKindItem)
async def update_part_kind(
    part_kind_uuid: uuid.UUID,
    payload: PartKindUpdate,
    session: AsyncSession = Depends(get_db_session),
) -> PartKindItem:
    item = await session.get(PartKind, part_kind_uuid)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Part kind not found.")
    await require_admin_if_present(session, payload.admin_id)

    item.admin_id = payload.admin_id
    item.part_kind_id = payload.part_kind_id
    item.part_kind_code = payload.part_kind_code.strip()
    item.org_part_kind_title = payload.org_part_kind_title.strip()
    item.code = payload.part_kind_code.strip()
    item.title = payload.org_part_kind_title.strip()
    item.sort_order = payload.sort_order
    item.part_scope = _normalize_part_scope(payload.part_scope)
    item.is_system = payload.is_system

    await session.commit()
    await session.refresh(item)
    return _to_response(item)


@router.delete("/{part_kind_uuid}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_part_kind(part_kind_uuid: uuid.UUID, session: AsyncSession = Depends(get_db_session)) -> Response:
    item = await session.get(PartKind, part_kind_uuid)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Part kind not found.")

    await session.delete(item)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
