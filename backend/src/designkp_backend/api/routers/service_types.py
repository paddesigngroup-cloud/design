from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from designkp_backend.db.dependencies import get_db_session
from designkp_backend.db.models.catalog import PartServiceType
from designkp_backend.services.admin_access import require_admin_if_present

router = APIRouter(prefix="/service-types", tags=["service_types"])


class ServiceTypeItem(BaseModel):
    id: uuid.UUID
    admin_id: uuid.UUID | None
    service_type: str
    service_title: str
    short_code: str
    sort_order: int
    is_system: bool

    model_config = {"from_attributes": True}


class ServiceTypeCreate(BaseModel):
    admin_id: uuid.UUID | None = None
    service_type: str = Field(min_length=1, max_length=255)
    service_title: str = Field(min_length=1, max_length=255)
    short_code: str = Field(min_length=1, max_length=64)
    sort_order: int | None = Field(default=None, ge=0)
    is_system: bool = False


class ServiceTypeUpdate(BaseModel):
    admin_id: uuid.UUID | None = None
    service_type: str = Field(min_length=1, max_length=255)
    service_title: str = Field(min_length=1, max_length=255)
    short_code: str = Field(min_length=1, max_length=64)
    sort_order: int = Field(ge=0)
    is_system: bool


def _normalize_required_text(value: str, field: str, max_len: int) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{field} is required.")
    if len(normalized) > max_len:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{field} is too long.")
    return normalized


async def _next_sort_order(session: AsyncSession) -> int:
    max_sort = await session.scalar(select(func.max(PartServiceType.sort_order)))
    return int(max_sort or 0) + 1


async def _ensure_unique_short_code(
    session: AsyncSession,
    *,
    admin_id: uuid.UUID | None,
    service_type: str,
    short_code: str,
    exclude_id: uuid.UUID | None = None,
) -> None:
    normalized_service_type = str(service_type or "").strip().lower()
    normalized_short_code = str(short_code or "").strip().lower()
    if not normalized_service_type:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Service type is required.")
    if not normalized_short_code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Short code is required.")
    conditions = [
        func.lower(PartServiceType.service_type) == normalized_service_type,
        func.lower(PartServiceType.short_code) == normalized_short_code,
    ]
    if admin_id is None:
        conditions.append(PartServiceType.admin_id.is_(None))
    else:
        conditions.append(PartServiceType.admin_id == admin_id)
    stmt = select(PartServiceType.id).where(and_(*conditions))
    if exclude_id is not None:
        stmt = stmt.where(PartServiceType.id != exclude_id)
    existing_id = await session.scalar(stmt)
    if existing_id is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Service type short code already exists in this owner scope.",
        )


def _to_response(item: PartServiceType) -> ServiceTypeItem:
    return ServiceTypeItem.model_validate(item)


@router.get("", response_model=list[ServiceTypeItem])
async def list_service_types(
    admin_id: uuid.UUID | None = Query(default=None),
    session: AsyncSession = Depends(get_db_session),
) -> list[ServiceTypeItem]:
    await require_admin_if_present(session, admin_id)
    stmt = (
        select(PartServiceType)
        .where(or_(PartServiceType.admin_id.is_(None), PartServiceType.admin_id == admin_id))
        .order_by(PartServiceType.sort_order.asc(), PartServiceType.id.asc())
    )
    items = (await session.scalars(stmt)).all()
    return [_to_response(item) for item in items]


@router.post("", response_model=ServiceTypeItem, status_code=status.HTTP_201_CREATED)
async def create_service_type(payload: ServiceTypeCreate, session: AsyncSession = Depends(get_db_session)) -> ServiceTypeItem:
    await require_admin_if_present(session, payload.admin_id)
    service_type = _normalize_required_text(payload.service_type, "Service type", 255)
    service_title = _normalize_required_text(payload.service_title, "Service title", 255)
    short_code = _normalize_required_text(payload.short_code, "Short code", 64)
    await _ensure_unique_short_code(session, admin_id=payload.admin_id, service_type=service_type, short_code=short_code)

    item = PartServiceType(
        admin_id=payload.admin_id,
        service_type=service_type,
        service_title=service_title,
        short_code=short_code,
        sort_order=payload.sort_order if payload.sort_order is not None else await _next_sort_order(session),
        is_system=payload.is_system,
    )
    session.add(item)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Service type short code already exists in this owner scope.") from exc
    await session.refresh(item)
    return _to_response(item)


@router.patch("/{service_type_id}", response_model=ServiceTypeItem)
async def update_service_type(
    service_type_id: uuid.UUID,
    payload: ServiceTypeUpdate,
    session: AsyncSession = Depends(get_db_session),
) -> ServiceTypeItem:
    item = await session.get(PartServiceType, service_type_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service type not found.")

    await require_admin_if_present(session, payload.admin_id)
    service_type = _normalize_required_text(payload.service_type, "Service type", 255)
    service_title = _normalize_required_text(payload.service_title, "Service title", 255)
    short_code = _normalize_required_text(payload.short_code, "Short code", 64)
    await _ensure_unique_short_code(
        session,
        admin_id=payload.admin_id,
        service_type=service_type,
        short_code=short_code,
        exclude_id=item.id,
    )

    item.admin_id = payload.admin_id
    item.service_type = service_type
    item.service_title = service_title
    item.short_code = short_code
    item.sort_order = payload.sort_order
    item.is_system = payload.is_system
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Service type short code already exists in this owner scope.") from exc
    await session.refresh(item)
    return _to_response(item)


@router.delete("/{service_type_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_service_type(service_type_id: uuid.UUID, session: AsyncSession = Depends(get_db_session)) -> Response:
    item = await session.get(PartServiceType, service_type_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service type not found.")

    await require_admin_if_present(session, item.admin_id)
    await session.delete(item)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
