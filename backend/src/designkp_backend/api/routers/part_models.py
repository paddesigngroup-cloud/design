from __future__ import annotations

import math
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
ANGLE_EPSILON = 1e-4
ANGLE_PRECISION = 6


class PartModelAngleItem(BaseModel):
    index: int = Field(ge=0, le=1000)
    angle_deg: float = Field(gt=0, le=360000)


class PartModelItem(BaseModel):
    id: uuid.UUID
    admin_id: uuid.UUID | None
    title: str
    side_count: int
    interior_angle_sum: int
    default_angles: list[PartModelAngleItem]
    sort_order: int
    is_system: bool

    model_config = {"from_attributes": True}


class PartModelCreate(BaseModel):
    admin_id: uuid.UUID | None = None
    title: str = Field(min_length=1, max_length=255)
    side_count: int = Field(ge=3, le=1000)
    interior_angle_sum: int | None = Field(default=None, ge=180, le=360000)
    default_angles: list[PartModelAngleItem] | None = None
    sort_order: int | None = Field(default=None, ge=0)
    is_system: bool = False


class PartModelUpdate(BaseModel):
    admin_id: uuid.UUID | None = None
    title: str = Field(min_length=1, max_length=255)
    side_count: int = Field(ge=3, le=1000)
    interior_angle_sum: int | None = Field(default=None, ge=180, le=360000)
    default_angles: list[PartModelAngleItem] | None = None
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


def _round_angle(value: float) -> float:
    return round(float(value), ANGLE_PRECISION)


def _build_equal_default_angles(side_count: int, interior_angle_sum: int) -> list[dict[str, float | int]]:
    if side_count <= 0:
        return []
    raw_angle = float(interior_angle_sum) / float(side_count)
    remaining = float(interior_angle_sum)
    normalized: list[dict[str, float | int]] = []
    for index in range(side_count):
        angle = remaining if index == side_count - 1 else _round_angle(raw_angle)
        angle = _round_angle(angle)
        remaining = _round_angle(remaining - angle)
        normalized.append({"index": index, "angle_deg": angle})
    return normalized


def _normalize_default_angles(
    side_count: int,
    interior_angle_sum: int,
    provided_angles: list[PartModelAngleItem] | None,
) -> list[dict[str, float | int]]:
    if provided_angles is None:
        return _build_equal_default_angles(side_count, interior_angle_sum)
    if len(provided_angles) != side_count:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Default angles must contain exactly {side_count} items.",
        )

    normalized: list[dict[str, float | int]] = []
    seen_indexes: set[int] = set()
    for item in provided_angles:
        index = int(item.index)
        if index in seen_indexes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Default angles must use unique indexes.",
            )
        if index < 0 or index >= side_count:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Default angle index {index} is out of range for side count {side_count}.",
            )
        angle_deg = float(item.angle_deg)
        if not math.isfinite(angle_deg) or angle_deg <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Default angles must be positive finite numbers.",
            )
        normalized.append({"index": index, "angle_deg": _round_angle(angle_deg)})
        seen_indexes.add(index)

    normalized.sort(key=lambda entry: int(entry["index"]))
    for expected_index, entry in enumerate(normalized):
        if int(entry["index"]) != expected_index:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Default angle indexes must cover every side in ascending order.",
            )

    total = sum(float(entry["angle_deg"]) for entry in normalized)
    if abs(total - float(interior_angle_sum)) > ANGLE_EPSILON:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Default angles must sum to {interior_angle_sum} for side count {side_count}.",
        )
    return normalized


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
    default_angles = _normalize_default_angles(payload.side_count, interior_angle_sum, payload.default_angles)
    await _ensure_unique_title(session, admin_id=payload.admin_id, title=title)

    item = PartModel(
        admin_id=payload.admin_id,
        title=title,
        side_count=payload.side_count,
        interior_angle_sum=interior_angle_sum,
        default_angles=default_angles,
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
    default_angles = _normalize_default_angles(payload.side_count, interior_angle_sum, payload.default_angles)
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
    item.default_angles = default_angles
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
