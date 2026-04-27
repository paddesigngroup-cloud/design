from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from designkp_backend.db.dependencies import get_db_session
from designkp_backend.db.models.catalog import PartService
from designkp_backend.services.admin_access import require_admin_if_present
from designkp_backend.services.admin_storage import delete_final_icon, finalize_param_group_icon, normalize_icon_file_name

router = APIRouter(prefix="/part-services", tags=["part_services"])


class PartServiceItem(BaseModel):
    id: uuid.UUID
    admin_id: uuid.UUID | None
    service_type: str
    service_description: str
    service_code: str
    icon_path: str | None
    sort_order: int
    is_system: bool

    model_config = {"from_attributes": True}


class PartServiceCreate(BaseModel):
    admin_id: uuid.UUID | None = None
    service_type: str = Field(min_length=1, max_length=255)
    service_description: str = Field(min_length=1, max_length=4000)
    service_code: str = Field(min_length=1, max_length=64)
    icon_path: str | None = Field(default=None, max_length=255)
    sort_order: int | None = Field(default=None, ge=0)
    is_system: bool = False


class PartServiceUpdate(BaseModel):
    admin_id: uuid.UUID | None = None
    service_type: str = Field(min_length=1, max_length=255)
    service_description: str = Field(min_length=1, max_length=4000)
    service_code: str = Field(min_length=1, max_length=64)
    icon_path: str | None = Field(default=None, max_length=255)
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
    max_sort = await session.scalar(select(func.max(PartService.sort_order)))
    return int(max_sort or 0) + 1


async def _ensure_unique_service_code(
    session: AsyncSession,
    *,
    admin_id: uuid.UUID | None,
    service_code: str,
    exclude_id: uuid.UUID | None = None,
) -> None:
    normalized_code = str(service_code or "").strip().lower()
    if not normalized_code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Service code is required.")
    conditions = [
        func.lower(PartService.service_code) == normalized_code,
    ]
    if admin_id is None:
        conditions.append(PartService.admin_id.is_(None))
    else:
        conditions.append(PartService.admin_id == admin_id)
    stmt = select(PartService.id).where(and_(*conditions))
    if exclude_id is not None:
        stmt = stmt.where(PartService.id != exclude_id)
    existing_id = await session.scalar(stmt)
    if existing_id is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Part service code already exists in this owner scope.",
        )


def _to_response(item: PartService) -> PartServiceItem:
    payload = PartServiceItem.model_validate(item).model_dump()
    payload["icon_path"] = normalize_icon_file_name(payload.get("icon_path"))
    return PartServiceItem.model_validate(payload)


@router.get("", response_model=list[PartServiceItem])
async def list_part_services(
    admin_id: uuid.UUID | None = Query(default=None),
    session: AsyncSession = Depends(get_db_session),
) -> list[PartServiceItem]:
    await require_admin_if_present(session, admin_id)
    stmt = (
        select(PartService)
        .where(or_(PartService.admin_id.is_(None), PartService.admin_id == admin_id))
        .order_by(PartService.sort_order.asc(), PartService.id.asc())
    )
    items = (await session.scalars(stmt)).all()
    return [_to_response(item) for item in items]


@router.post("", response_model=PartServiceItem, status_code=status.HTTP_201_CREATED)
async def create_part_service(payload: PartServiceCreate, session: AsyncSession = Depends(get_db_session)) -> PartServiceItem:
    await require_admin_if_present(session, payload.admin_id)
    service_type = _normalize_required_text(payload.service_type, "Service type", 255)
    service_description = _normalize_required_text(payload.service_description, "Service description", 4000)
    service_code = _normalize_required_text(payload.service_code, "Service code", 64)
    await _ensure_unique_service_code(session, admin_id=payload.admin_id, service_code=service_code)
    final_icon_file_name = finalize_param_group_icon(payload.admin_id, payload.icon_path) if payload.admin_id else normalize_icon_file_name(payload.icon_path)

    item = PartService(
        admin_id=payload.admin_id,
        service_type=service_type,
        service_description=service_description,
        service_code=service_code,
        icon_path=final_icon_file_name,
        sort_order=payload.sort_order if payload.sort_order is not None else await _next_sort_order(session),
        is_system=payload.is_system,
    )
    session.add(item)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Part service code already exists in this owner scope.") from exc
    await session.refresh(item)
    return _to_response(item)


@router.patch("/{part_service_id}", response_model=PartServiceItem)
async def update_part_service(
    part_service_id: uuid.UUID,
    payload: PartServiceUpdate,
    session: AsyncSession = Depends(get_db_session),
) -> PartServiceItem:
    item = await session.get(PartService, part_service_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Part service not found.")

    await require_admin_if_present(session, payload.admin_id)
    service_type = _normalize_required_text(payload.service_type, "Service type", 255)
    service_description = _normalize_required_text(payload.service_description, "Service description", 4000)
    service_code = _normalize_required_text(payload.service_code, "Service code", 64)
    await _ensure_unique_service_code(
        session,
        admin_id=payload.admin_id,
        service_code=service_code,
        exclude_id=item.id,
    )
    previous_admin_id = item.admin_id
    previous_icon_file_name = item.icon_path
    next_admin_id = payload.admin_id
    if next_admin_id:
        next_icon_file_name = finalize_param_group_icon(
            next_admin_id,
            payload.icon_path,
            previous_file_name=previous_icon_file_name if previous_admin_id == next_admin_id else None,
        )
        if previous_admin_id and previous_admin_id != next_admin_id and previous_icon_file_name:
            delete_final_icon(previous_admin_id, previous_icon_file_name)
    else:
        next_icon_file_name = normalize_icon_file_name(payload.icon_path)
        if previous_admin_id and previous_icon_file_name:
            delete_final_icon(previous_admin_id, previous_icon_file_name)

    item.admin_id = next_admin_id
    item.service_type = service_type
    item.service_description = service_description
    item.service_code = service_code
    item.icon_path = next_icon_file_name
    item.sort_order = payload.sort_order
    item.is_system = payload.is_system
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Part service code already exists in this owner scope.") from exc
    await session.refresh(item)
    return _to_response(item)


@router.delete("/{part_service_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_part_service(part_service_id: uuid.UUID, session: AsyncSession = Depends(get_db_session)) -> Response:
    item = await session.get(PartService, part_service_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Part service not found.")

    await require_admin_if_present(session, item.admin_id)
    if item.admin_id and item.icon_path:
        delete_final_icon(item.admin_id, item.icon_path)
    await session.delete(item)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
