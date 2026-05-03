from __future__ import annotations

import math
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from designkp_backend.db.dependencies import get_db_session
from designkp_backend.db.models.catalog import PartServiceType
from designkp_backend.services.admin_access import require_admin_if_present
from designkp_backend.services.admin_storage import delete_final_icon, finalize_param_group_icon, normalize_icon_file_name

router = APIRouter(prefix="/service-types", tags=["service_types"])
ANGLE_EPSILON = 1e-4
ANGLE_PRECISION = 6


class ServiceTypeAngleItem(BaseModel):
    index: int = Field(ge=0, le=1000)
    angle_deg: float = Field(gt=0, le=360000)


class ServiceTypeItem(BaseModel):
    id: uuid.UUID
    admin_id: uuid.UUID | None
    service_type: str
    service_title: str
    short_code: str
    icon_path: str | None
    has_subtraction: bool
    service_location: str | None
    subtraction_shape: str | None
    shape_angles: list[ServiceTypeAngleItem] | None
    axis_to_opposite_edge_distance: float
    axis_to_aligned_edge_distance: float
    working_diameter: float
    working_width: float
    working_height: float
    working_depth: float
    working_depth_mode: str
    working_depth_end_offset: float
    preview_mirror_x: bool
    preview_mirror_y: bool
    sort_order: int
    is_system: bool

    model_config = {"from_attributes": True}


class ServiceTypeCreate(BaseModel):
    admin_id: uuid.UUID | None = None
    service_type: str = Field(min_length=1, max_length=255)
    service_title: str = Field(min_length=1, max_length=255)
    short_code: str = Field(min_length=1, max_length=64)
    icon_path: str | None = Field(default=None, max_length=255)
    has_subtraction: bool = False
    service_location: str | None = Field(default=None, min_length=1, max_length=16)
    subtraction_shape: str | None = Field(default=None, min_length=1, max_length=16)
    shape_angles: list[ServiceTypeAngleItem] | None = None
    axis_to_opposite_edge_distance: float = Field(default=0, ge=0)
    axis_to_aligned_edge_distance: float = Field(default=0, ge=0)
    working_diameter: float = Field(default=0, ge=0)
    working_width: float = Field(default=0, ge=0)
    working_height: float = Field(default=0, ge=0)
    working_depth: float = Field(default=0, ge=0)
    working_depth_mode: str = Field(default="fixed", min_length=1, max_length=16)
    working_depth_end_offset: float = Field(default=0, ge=0)
    preview_mirror_x: bool = False
    preview_mirror_y: bool = False
    sort_order: int | None = Field(default=None, ge=0)
    is_system: bool = False


class ServiceTypeUpdate(BaseModel):
    admin_id: uuid.UUID | None = None
    service_type: str = Field(min_length=1, max_length=255)
    service_title: str = Field(min_length=1, max_length=255)
    short_code: str = Field(min_length=1, max_length=64)
    icon_path: str | None = Field(default=None, max_length=255)
    has_subtraction: bool = False
    service_location: str | None = Field(default=None, min_length=1, max_length=16)
    subtraction_shape: str | None = Field(default=None, min_length=1, max_length=16)
    shape_angles: list[ServiceTypeAngleItem] | None = None
    axis_to_opposite_edge_distance: float = Field(default=0, ge=0)
    axis_to_aligned_edge_distance: float = Field(default=0, ge=0)
    working_diameter: float = Field(default=0, ge=0)
    working_width: float = Field(default=0, ge=0)
    working_height: float = Field(default=0, ge=0)
    working_depth: float = Field(default=0, ge=0)
    working_depth_mode: str = Field(default="fixed", min_length=1, max_length=16)
    working_depth_end_offset: float = Field(default=0, ge=0)
    preview_mirror_x: bool = False
    preview_mirror_y: bool = False
    sort_order: int = Field(ge=0)
    is_system: bool


def _normalize_required_text(value: str, field: str, max_len: int) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{field} is required.")
    if len(normalized) > max_len:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{field} is too long.")
    return normalized


def _round_angle(value: float) -> float:
    return round(float(value), ANGLE_PRECISION)


def _normalize_service_location(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = str(value or "").strip().lower()
    if not normalized:
        return None
    if normalized not in {"front", "back", "thickness"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Service location must be front, back, or thickness.",
        )
    return normalized


def _normalize_subtraction_shape(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = str(value or "").strip().lower()
    if not normalized:
        return None
    if normalized not in {"circle", "triangle", "rectangle"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Subtraction shape must be circle, triangle, or rectangle.",
        )
    return normalized


def _normalize_optional_measurement(value: float | None) -> float:
    if value is None:
        return 0.0
    normalized = float(value)
    if normalized < 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Measurements must be zero or greater.")
    return round(normalized, 1)


def _normalize_working_depth_mode(value: str | None) -> str:
    normalized = str(value or "").strip().lower()
    if normalized not in {"", "fixed", "to_end"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Working depth mode must be fixed or to_end.",
        )
    return "to_end" if normalized == "to_end" else "fixed"


def _normalize_shape_angles(
    shape: str | None,
    provided_angles: list[ServiceTypeAngleItem] | None,
) -> list[dict[str, float | int]] | None:
    if shape is None:
        return None
    if shape == "circle":
        return []
    expected_count = 3 if shape == "triangle" else 4
    expected_sum = 180 if shape == "triangle" else 360
    if provided_angles is None or len(provided_angles) != expected_count:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{shape.title()} shape must contain exactly {expected_count} angles.",
        )
    normalized: list[dict[str, float | int]] = []
    seen_indexes: set[int] = set()
    for item in provided_angles:
        index = int(item.index)
        if index in seen_indexes:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Shape angles must use unique indexes.")
        if index < 0 or index >= expected_count:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Shape angle index {index} is out of range for {shape}.",
            )
        angle_deg = float(item.angle_deg)
        if not math.isfinite(angle_deg) or angle_deg <= 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Shape angles must be positive finite numbers.")
        normalized.append({"index": index, "angle_deg": _round_angle(angle_deg)})
        seen_indexes.add(index)
    normalized.sort(key=lambda entry: int(entry["index"]))
    for expected_index, entry in enumerate(normalized):
        if int(entry["index"]) != expected_index:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Shape angle indexes must cover every side in ascending order.",
            )
    total = sum(float(entry["angle_deg"]) for entry in normalized)
    if abs(total - float(expected_sum)) > ANGLE_EPSILON:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{shape.title()} shape angles must sum to {expected_sum}.",
        )
    return normalized


def _normalize_subtraction_payload(payload: ServiceTypeCreate | ServiceTypeUpdate) -> dict[str, object]:
    has_subtraction = bool(payload.has_subtraction)
    axis_to_opposite_edge_distance = _normalize_optional_measurement(payload.axis_to_opposite_edge_distance)
    axis_to_aligned_edge_distance = _normalize_optional_measurement(payload.axis_to_aligned_edge_distance)
    working_diameter = _normalize_optional_measurement(payload.working_diameter)
    working_width = _normalize_optional_measurement(payload.working_width)
    working_height = _normalize_optional_measurement(payload.working_height)
    working_depth = _normalize_optional_measurement(payload.working_depth)
    working_depth_mode = _normalize_working_depth_mode(payload.working_depth_mode)
    working_depth_end_offset = _normalize_optional_measurement(payload.working_depth_end_offset)
    if not has_subtraction:
        return {
            "has_subtraction": False,
            "service_location": None,
            "subtraction_shape": None,
            "shape_angles": None,
            "axis_to_opposite_edge_distance": axis_to_opposite_edge_distance,
            "axis_to_aligned_edge_distance": axis_to_aligned_edge_distance,
            "working_diameter": working_diameter,
            "working_width": working_width,
            "working_height": working_height,
            "working_depth": working_depth,
            "working_depth_mode": working_depth_mode,
            "working_depth_end_offset": 0.0 if working_depth_mode != "to_end" else working_depth_end_offset,
            "preview_mirror_x": bool(payload.preview_mirror_x),
            "preview_mirror_y": bool(payload.preview_mirror_y),
        }
    service_location = _normalize_service_location(payload.service_location)
    subtraction_shape = _normalize_subtraction_shape(payload.subtraction_shape)
    if service_location is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Service location is required when subtraction is enabled.")
    if subtraction_shape is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Subtraction shape is required when subtraction is enabled.")
    shape_angles = _normalize_shape_angles(subtraction_shape, payload.shape_angles)
    return {
        "has_subtraction": True,
        "service_location": service_location,
        "subtraction_shape": subtraction_shape,
        "shape_angles": shape_angles,
        "axis_to_opposite_edge_distance": axis_to_opposite_edge_distance,
        "axis_to_aligned_edge_distance": axis_to_aligned_edge_distance,
        "working_diameter": working_diameter,
        "working_width": working_width,
        "working_height": working_height,
        "working_depth": working_depth,
        "working_depth_mode": working_depth_mode,
        "working_depth_end_offset": 0.0 if working_depth_mode != "to_end" else working_depth_end_offset,
        "preview_mirror_x": bool(payload.preview_mirror_x),
        "preview_mirror_y": bool(payload.preview_mirror_y),
    }


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
    payload = ServiceTypeItem.model_validate(item).model_dump()
    payload["icon_path"] = normalize_icon_file_name(payload.get("icon_path"))
    return ServiceTypeItem.model_validate(payload)


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
    subtraction_payload = _normalize_subtraction_payload(payload)
    await _ensure_unique_short_code(session, admin_id=payload.admin_id, service_type=service_type, short_code=short_code)
    final_icon_file_name = finalize_param_group_icon(payload.admin_id, payload.icon_path) if payload.admin_id else normalize_icon_file_name(payload.icon_path)

    item = PartServiceType(
        admin_id=payload.admin_id,
        service_type=service_type,
        service_title=service_title,
        short_code=short_code,
        icon_path=final_icon_file_name,
        has_subtraction=bool(subtraction_payload["has_subtraction"]),
        service_location=subtraction_payload["service_location"],
        subtraction_shape=subtraction_payload["subtraction_shape"],
        shape_angles=subtraction_payload["shape_angles"],
        axis_to_opposite_edge_distance=subtraction_payload["axis_to_opposite_edge_distance"],
        axis_to_aligned_edge_distance=subtraction_payload["axis_to_aligned_edge_distance"],
        working_diameter=subtraction_payload["working_diameter"],
        working_width=subtraction_payload["working_width"],
        working_height=subtraction_payload["working_height"],
        working_depth=subtraction_payload["working_depth"],
        working_depth_mode=subtraction_payload["working_depth_mode"],
        working_depth_end_offset=subtraction_payload["working_depth_end_offset"],
        preview_mirror_x=subtraction_payload["preview_mirror_x"],
        preview_mirror_y=subtraction_payload["preview_mirror_y"],
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
    subtraction_payload = _normalize_subtraction_payload(payload)
    await _ensure_unique_short_code(
        session,
        admin_id=payload.admin_id,
        service_type=service_type,
        short_code=short_code,
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
    item.service_title = service_title
    item.short_code = short_code
    item.icon_path = next_icon_file_name
    item.has_subtraction = bool(subtraction_payload["has_subtraction"])
    item.service_location = subtraction_payload["service_location"]
    item.subtraction_shape = subtraction_payload["subtraction_shape"]
    item.shape_angles = subtraction_payload["shape_angles"]
    item.axis_to_opposite_edge_distance = subtraction_payload["axis_to_opposite_edge_distance"]
    item.axis_to_aligned_edge_distance = subtraction_payload["axis_to_aligned_edge_distance"]
    item.working_diameter = subtraction_payload["working_diameter"]
    item.working_width = subtraction_payload["working_width"]
    item.working_height = subtraction_payload["working_height"]
    item.working_depth = subtraction_payload["working_depth"]
    item.working_depth_mode = subtraction_payload["working_depth_mode"]
    item.working_depth_end_offset = subtraction_payload["working_depth_end_offset"]
    item.preview_mirror_x = subtraction_payload["preview_mirror_x"]
    item.preview_mirror_y = subtraction_payload["preview_mirror_y"]
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
    if item.admin_id and item.icon_path:
        delete_final_icon(item.admin_id, item.icon_path)
    await session.delete(item)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
