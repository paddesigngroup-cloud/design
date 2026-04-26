from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from designkp_backend.db.dependencies import get_db_session
from designkp_backend.db.models.catalog import PartModel
from designkp_backend.services.admin_access import require_admin_if_present

router = APIRouter(prefix="/part-models", tags=["part_models"])


class PartModelItem(BaseModel):
    id: uuid.UUID
    admin_id: uuid.UUID | None
    title: str
    side_count: int
    interior_angle_sum: int
    sort_order: int
    is_system: bool

    model_config = {"from_attributes": True}


class PartModelCreate(BaseModel):
    admin_id: uuid.UUID | None = None
    title: str = Field(min_length=1, max_length=255)
    side_count: int = Field(ge=3, le=1000)
    interior_angle_sum: int | None = Field(default=None, ge=180, le=360000)
    sort_order: int | None = Field(default=None, ge=0)
    is_system: bool = False


class PartModelUpdate(BaseModel):
    admin_id: uuid.UUID | None = None
    title: str = Field(min_length=1, max_length=255)
    side_count: int = Field(ge=3, le=1000)
    interior_angle_sum: int | None = Field(default=None, ge=180, le=360000)
    sort_order: int = Field(ge=0)
    is_system: bool


def _normalize_required_text(value: str, field: str, max_len: int) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{field} is required.")
    if len(normalized) > max_len:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{field} is too long.")
    return normalized


def _calculate_interior_angle_sum(side_count: int) -> int:
    return (int(side_count) - 2) * 180


def _normalize_interior_angle_sum(side_count: int, provided_value: int | None) -> int:
    expected = _calculate_interior_angle_sum(side_count)
    if provided_value is None:
        return expected
    normalized = int(provided_value)
    if normalized != expected:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Interior angle sum must equal {expected} for side count {side_count}.",
        )
    return normalized


async def _next_sort_order(session: AsyncSession) -> int:
    max_sort = await session.scalar(select(func.max(PartModel.sort_order)))
    return int(max_sort or 0) + 1


async def _ensure_unique_title(
    session: AsyncSession,
    *,
    admin_id: uuid.UUID | None,
    title: str,
    exclude_id: uuid.UUID | None = None,
) -> None:
    normalized_title = str(title or "").strip().lower()
    conditions = [func.lower(PartModel.title) == normalized_title]
    if admin_id is None:
        conditions.append(PartModel.admin_id.is_(None))
    else:
        conditions.append(PartModel.admin_id == admin_id)
    stmt = select(PartModel.id).where(and_(*conditions))
    if exclude_id is not None:
        stmt = stmt.where(PartModel.id != exclude_id)
    existing_id = await session.scalar(stmt)
    if existing_id is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Part model title already exists in this owner scope.",
        )


def _to_response(item: PartModel) -> PartModelItem:
    return PartModelItem.model_validate(item)


@router.get("", response_model=list[PartModelItem])
async def list_part_models(
    admin_id: uuid.UUID | None = Query(default=None),
    session: AsyncSession = Depends(get_db_session),
) -> list[PartModelItem]:
    await require_admin_if_present(session, admin_id)
    stmt = (
        select(PartModel)
        .where(or_(PartModel.admin_id.is_(None), PartModel.admin_id == admin_id))
        .order_by(PartModel.sort_order.asc(), PartModel.id.asc())
    )
    items = (await session.scalars(stmt)).all()
    return [_to_response(item) for item in items]


@router.post("", response_model=PartModelItem, status_code=status.HTTP_201_CREATED)
async def create_part_model(payload: PartModelCreate, session: AsyncSession = Depends(get_db_session)) -> PartModelItem:
    await require_admin_if_present(session, payload.admin_id)
    title = _normalize_required_text(payload.title, "Part model title", 255)
    interior_angle_sum = _normalize_interior_angle_sum(payload.side_count, payload.interior_angle_sum)
    await _ensure_unique_title(session, admin_id=payload.admin_id, title=title)

    item = PartModel(
        admin_id=payload.admin_id,
        title=title,
        side_count=payload.side_count,
        interior_angle_sum=interior_angle_sum,
        sort_order=payload.sort_order if payload.sort_order is not None else await _next_sort_order(session),
        is_system=payload.is_system,
    )
    session.add(item)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Part model title already exists in this owner scope.") from exc
    await session.refresh(item)
    return _to_response(item)


@router.patch("/{part_model_id}", response_model=PartModelItem)
async def update_part_model(
    part_model_id: uuid.UUID,
    payload: PartModelUpdate,
    session: AsyncSession = Depends(get_db_session),
) -> PartModelItem:
    item = await session.get(PartModel, part_model_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Part model not found.")

    await require_admin_if_present(session, payload.admin_id)
    title = _normalize_required_text(payload.title, "Part model title", 255)
    interior_angle_sum = _normalize_interior_angle_sum(payload.side_count, payload.interior_angle_sum)
    await _ensure_unique_title(
        session,
        admin_id=payload.admin_id,
        title=title,
        exclude_id=item.id,
    )

    item.admin_id = payload.admin_id
    item.title = title
    item.side_count = payload.side_count
    item.interior_angle_sum = interior_angle_sum
    item.sort_order = payload.sort_order
    item.is_system = payload.is_system
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Part model title already exists in this owner scope.") from exc
    await session.refresh(item)
    return _to_response(item)


@router.delete("/{part_model_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_part_model(part_model_id: uuid.UUID, session: AsyncSession = Depends(get_db_session)) -> Response:
    item = await session.get(PartModel, part_model_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Part model not found.")

    await require_admin_if_present(session, item.admin_id)
    await session.delete(item)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
