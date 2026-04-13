from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import IntegrityError

from designkp_backend.db.dependencies import get_db_session
from designkp_backend.db.models.catalog import Category, SubCategory, SubCategoryDesign, SubCategoryDesignDoorInstance, SubCategoryDesignInteriorInstance, SubCategoryDesignPart
from designkp_backend.services.admin_access import require_admin_if_present
from designkp_backend.services.sub_category_designs import (
    _collect_controller_selection_boxes,
    _collect_controller_selection_boxes_by_formula_id,
    build_sub_category_param_display_snapshot,
    compose_sub_category_design_preview,
    door_instance_tables_ready,
    derive_interior_box_snapshot,
    interior_instance_tables_ready,
    rebuild_design_snapshots,
    require_accessible_door_part_group,
    require_accessible_internal_part_group,
    require_accessible_sub_category,
    resolve_door_instance_preview,
    resolve_internal_instance_preview,
    serialize_resolved_part_snapshot,
)

router = APIRouter(prefix="/sub-category-designs", tags=["sub_category_designs"])
DEFAULT_INTERIOR_LINE_COLOR = "#8A98A3"


def _normalize_hex_color(value: str | None, fallback: str = DEFAULT_INTERIOR_LINE_COLOR) -> str:
    raw = str(value or "").strip()
    if not raw:
        return fallback
    normalized = raw if raw.startswith("#") else f"#{raw}"
    if not normalized or len(normalized) != 7 or not all(ch in "0123456789ABCDEFabcdef#" for ch in normalized):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Interior line color must be a HEX value like #8A98A3.")
    return normalized.upper()


class SubCategoryDesignPartSelectionPayload(BaseModel):
    part_formula_id: int = Field(ge=1)
    enabled: bool = True
    ui_order: int = Field(default=0, ge=0)


class SubCategoryDesignPartItem(BaseModel):
    id: uuid.UUID
    part_formula_id: int
    part_kind_id: int
    part_code: str
    part_title: str
    enabled: bool
    ui_order: int

    model_config = {"from_attributes": True}


class SubCategoryDesignPartPreviewItem(BaseModel):
    id: uuid.UUID | None = None
    part_formula_id: int
    part_kind_id: int
    part_code: str
    part_title: str
    enabled: bool
    ui_order: int
    resolved_part_formulas: dict[str, float]
    viewer_payload: dict[str, object]


class SubCategoryDesignInteriorInstanceItem(BaseModel):
    id: uuid.UUID
    internal_part_group_id: uuid.UUID
    controller_type: str | None = None
    controller_bindings: dict[str, dict[str, str | None]] = Field(default_factory=dict)
    instance_code: str
    line_color: str | None = None
    ui_order: int
    placement_z: float
    interior_box_snapshot: dict[str, object]
    param_values: dict[str, str | None]
    param_meta: dict[str, dict[str, object]]
    part_snapshots: list[dict[str, object]]
    viewer_boxes: list[dict[str, object]]
    status: str

    model_config = {"from_attributes": True}


class SubCategoryDesignInteriorInstancePreviewItem(BaseModel):
    id: uuid.UUID | None = None
    internal_part_group_id: uuid.UUID
    internal_part_group_code: str
    internal_part_group_title: str
    controller_type: str | None = None
    controller_bindings: dict[str, dict[str, str | None]] = Field(default_factory=dict)
    instance_code: str
    line_color: str | None = None
    ui_order: int
    placement_z: float
    interior_box_snapshot: dict[str, object]
    param_values: dict[str, str | None]
    param_meta: dict[str, dict[str, object]]
    auto_params: dict[str, float]
    part_snapshots: list[dict[str, object]]
    viewer_boxes: list[dict[str, object]]


class SubCategoryDesignPreviewResponse(BaseModel):
    design_id: uuid.UUID | None = None
    sub_category_id: uuid.UUID
    design_outline_color: str = "#7A4A2B"
    resolved_params: dict[str, str | None]
    resolved_base_formulas: dict[str, float]
    viewer_boxes: list[dict[str, object]]
    parts: list[SubCategoryDesignPartPreviewItem]
    interior_instances: list[SubCategoryDesignInteriorInstancePreviewItem]
    door_instances: list[dict[str, object]] = Field(default_factory=list)


class SubCategoryDesignItem(BaseModel):
    id: uuid.UUID
    admin_id: uuid.UUID | None
    sub_category_id: uuid.UUID
    design_outline_color: str = "#7A4A2B"
    temp_id: int
    cat_id: int
    sub_cat_id: int
    design_id: int
    design_title: str
    code: str
    title: str
    sort_order: int
    is_system: bool
    parts: list[SubCategoryDesignPartItem]
    interior_instances: list[SubCategoryDesignInteriorInstanceItem]
    door_instances: list[dict[str, object]] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class SubCategoryDesignCreate(BaseModel):
    admin_id: uuid.UUID | None = None
    sub_category_id: uuid.UUID
    design_id: int | None = Field(default=None, ge=1)
    design_title: str = Field(min_length=1, max_length=255)
    code: str = Field(min_length=1, max_length=64)
    sort_order: int | None = Field(default=None, ge=0)
    is_system: bool = False
    parts: list[SubCategoryDesignPartSelectionPayload] = Field(default_factory=list)
    interior_instances: list["SubCategoryDesignInteriorInstanceDraftPayload"] = Field(default_factory=list)
    door_instances: list["SubCategoryDesignDoorInstanceDraftPayload"] = Field(default_factory=list)


class SubCategoryDesignUpdate(BaseModel):
    admin_id: uuid.UUID | None = None
    sub_category_id: uuid.UUID
    design_id: int = Field(ge=1)
    design_title: str = Field(min_length=1, max_length=255)
    code: str = Field(min_length=1, max_length=64)
    sort_order: int = Field(ge=0)
    is_system: bool
    parts: list[SubCategoryDesignPartSelectionPayload] = Field(default_factory=list)
    interior_instances: list["SubCategoryDesignInteriorInstanceDraftPayload"] = Field(default_factory=list)
    door_instances: list["SubCategoryDesignDoorInstanceDraftPayload"] = Field(default_factory=list)


class SubCategoryDesignPreviewDraftRequest(BaseModel):
    admin_id: uuid.UUID
    sub_category_id: uuid.UUID
    parts: list[SubCategoryDesignPartSelectionPayload] = Field(default_factory=list)
    interior_instances: list["SubCategoryDesignInteriorInstanceDraftPayload"] = Field(default_factory=list)
    door_instances: list["SubCategoryDesignDoorInstanceDraftPayload"] = Field(default_factory=list)


class SubCategoryDesignInteriorInstanceDraftPayload(BaseModel):
    id: uuid.UUID | None = None
    internal_part_group_id: uuid.UUID
    instance_code: str = Field(min_length=1, max_length=64)
    line_color: str | None = Field(default=None, min_length=7, max_length=7)
    ui_order: int = Field(ge=0)
    placement_z: float = 0
    interior_box_snapshot: dict[str, object] = Field(default_factory=dict)
    param_values: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
    param_meta: dict[str, dict[str, object]] = Field(default_factory=dict)


class SubCategoryDesignDoorInstanceDraftPayload(BaseModel):
    id: uuid.UUID | None = None
    door_part_group_id: uuid.UUID
    instance_code: str = Field(min_length=1, max_length=64)
    line_color: str | None = Field(default=None, min_length=7, max_length=7)
    ui_order: int = Field(ge=0)
    structural_part_formula_ids: list[int] = Field(default_factory=list)
    dependent_interior_instance_ids: list[uuid.UUID | str] = Field(default_factory=list)
    controller_box_snapshot: dict[str, object] = Field(default_factory=dict)
    param_values: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
    param_meta: dict[str, dict[str, object]] = Field(default_factory=dict)


SubCategoryDesignPreviewDraftRequest.model_rebuild()


class SubCategoryDesignInteriorInstanceCreate(BaseModel):
    internal_part_group_id: uuid.UUID
    placement_z: float = 0
    ui_order: int | None = Field(default=None, ge=0)
    instance_code: str | None = Field(default=None, max_length=64)
    line_color: str | None = Field(default=None, min_length=7, max_length=7)
    param_values: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class SubCategoryDesignInteriorInstanceUpdate(BaseModel):
    placement_z: float
    ui_order: int = Field(ge=0)
    instance_code: str = Field(min_length=1, max_length=64)
    line_color: str | None = Field(default=None, min_length=7, max_length=7)
    param_values: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class SubCategoryDesignDoorInstanceItem(BaseModel):
    id: uuid.UUID
    door_part_group_id: uuid.UUID
    controller_type: str | None = None
    controller_bindings: dict[str, dict[str, str | None]] = Field(default_factory=dict)
    instance_code: str
    line_color: str | None = None
    ui_order: int
    structural_part_formula_ids: list[int] = Field(default_factory=list)
    dependent_interior_instance_ids: list[str] = Field(default_factory=list)
    controller_box_snapshot: dict[str, object] = Field(default_factory=dict)
    param_values: dict[str, str | None] = Field(default_factory=dict)
    param_meta: dict[str, dict[str, object]] = Field(default_factory=dict)
    part_snapshots: list[dict[str, object]] = Field(default_factory=list)
    viewer_boxes: list[dict[str, object]] = Field(default_factory=list)
    status: str


class SubCategoryDesignDoorInstanceCreate(BaseModel):
    door_part_group_id: uuid.UUID
    ui_order: int | None = Field(default=None, ge=0)
    instance_code: str | None = Field(default=None, max_length=64)
    line_color: str | None = Field(default=None, min_length=7, max_length=7)
    structural_part_formula_ids: list[int] = Field(default_factory=list)
    dependent_interior_instance_ids: list[uuid.UUID | str] = Field(default_factory=list)
    controller_box_snapshot: dict[str, object] = Field(default_factory=dict)
    param_values: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class SubCategoryDesignDoorInstanceUpdate(BaseModel):
    ui_order: int = Field(ge=0)
    instance_code: str = Field(min_length=1, max_length=64)
    line_color: str | None = Field(default=None, min_length=7, max_length=7)
    structural_part_formula_ids: list[int] = Field(default_factory=list)
    dependent_interior_instance_ids: list[uuid.UUID | str] = Field(default_factory=list)
    param_values: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


async def _next_design_id(session: AsyncSession) -> int:
    max_id = await session.scalar(select(func.max(SubCategoryDesign.design_id)))
    return int(max_id or 0) + 1


async def _resolve_available_design_id(
    session: AsyncSession,
    requested_id: int | None,
    *,
    exclude_uuid: uuid.UUID | None = None,
) -> int:
    candidate = int(requested_id or 0)
    if candidate >= 1:
        stmt = select(SubCategoryDesign.id).where(SubCategoryDesign.design_id == candidate)
        if exclude_uuid is not None:
            stmt = stmt.where(SubCategoryDesign.id != exclude_uuid)
        existing = await session.scalar(stmt.limit(1))
        if not existing:
            return candidate
    return await _next_design_id(session)


async def _ensure_unique_design_code(
    session: AsyncSession,
    *,
    code: str,
    exclude_id: uuid.UUID | None = None,
) -> None:
    stmt = select(SubCategoryDesign).where(SubCategoryDesign.code == code)
    if exclude_id is not None:
        stmt = stmt.where(SubCategoryDesign.id != exclude_id)
    duplicate = await session.scalar(stmt)
    if duplicate:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Design code is already used.")


def _serialize_design(item: SubCategoryDesign, *, include_interior: bool = True, design_outline_color: str = "#7A4A2B") -> SubCategoryDesignItem:
    loaded_door_instances = list(getattr(item, "__dict__", {}).get("door_instances") or [])
    return SubCategoryDesignItem(
        id=item.id,
        admin_id=item.admin_id,
        sub_category_id=item.sub_category_id,
        design_outline_color=str(design_outline_color or "#7A4A2B").strip() or "#7A4A2B",
        temp_id=item.temp_id,
        cat_id=item.cat_id,
        sub_cat_id=item.sub_cat_id,
        design_id=int(item.design_id or 0),
        design_title=item.design_title,
        code=item.code,
        title=item.title,
        sort_order=item.sort_order,
        is_system=item.is_system,
        parts=[
            SubCategoryDesignPartItem.model_validate(part)
            for part in sorted(item.parts, key=lambda part: (int(part.ui_order), int(part.part_formula_id)))
        ],
        interior_instances=(
            [
                SubCategoryDesignInteriorInstanceItem(
                    id=instance.id,
                    internal_part_group_id=instance.internal_part_group_id,
                    controller_type=None,
                    controller_bindings={},
                    instance_code=str(instance.instance_code or "").strip(),
                    line_color=str(getattr(instance, "line_color", "") or "").strip() or None,
                    ui_order=int(instance.ui_order or 0),
                    placement_z=float(instance.placement_z or 0),
                    interior_box_snapshot=dict(instance.interior_box_snapshot or {}),
                    param_values={str(key): (None if value is None else str(value)) for key, value in dict(instance.param_values or {}).items()},
                    param_meta={str(key): dict(value or {}) for key, value in dict(instance.param_meta or {}).items()},
                    part_snapshots=[dict(row or {}) for row in list(instance.part_snapshots or [])],
                    viewer_boxes=[dict(row or {}) for row in list(instance.viewer_boxes or [])],
                    status=str(instance.status or "draft").strip() or "draft",
                )
                for instance in sorted(item.interior_instances, key=lambda row: (int(row.ui_order), str(row.instance_code or "")))
            ]
            if include_interior else []
        ),
        door_instances=[
            {
                "id": instance.id,
                "door_part_group_id": instance.door_part_group_id,
                "controller_type": None,
                "controller_bindings": {},
                "instance_code": str(instance.instance_code or "").strip(),
                "line_color": str(getattr(instance, "line_color", "") or "").strip() or None,
                "ui_order": int(instance.ui_order or 0),
                "structural_part_formula_ids": [int(row) for row in list(instance.structural_part_formula_ids or []) if int(row) > 0],
                "dependent_interior_instance_ids": [str(row).strip() for row in list(instance.dependent_interior_instance_ids or []) if str(row).strip()],
                "controller_box_snapshot": dict(instance.controller_box_snapshot or {}),
                "param_values": {str(key): (None if value is None else str(value)) for key, value in dict(instance.param_values or {}).items()},
                "param_meta": {str(key): dict(value or {}) for key, value in dict(instance.param_meta or {}).items()},
                "part_snapshots": [dict(row or {}) for row in list(instance.part_snapshots or [])],
                "viewer_boxes": [dict(row or {}) for row in list(instance.viewer_boxes or [])],
                "status": str(instance.status or "draft").strip() or "draft",
            }
            for instance in sorted(loaded_door_instances, key=lambda row: (int(row.ui_order or 0), str(row.instance_code or "")))
        ] if include_interior else [],
    )


def _serialize_preview(
    *,
    design_id: uuid.UUID | None,
    sub_category_id: uuid.UUID,
    design_outline_color: str,
    raw_params: dict[str, str | None],
    resolved_base_formulas: dict[str, float],
    snapshots: list,
    interior_instances: list,
    door_instances: list | None = None,
) -> SubCategoryDesignPreviewResponse:
    parts = [
        SubCategoryDesignPartPreviewItem(
            part_formula_id=int(item.part_formula.part_formula_id),
            part_kind_id=int(item.part_formula.part_kind_id),
            part_code=item.part_formula.part_code,
            part_title=item.part_formula.part_title,
            enabled=item.enabled,
            ui_order=item.ui_order,
            resolved_part_formulas=item.resolved_part_formulas,
            viewer_payload=item.viewer_payload,
        )
        for item in snapshots
    ]
    interior_preview_items = [
        SubCategoryDesignInteriorInstancePreviewItem(
            id=item.instance_id,
            internal_part_group_id=item.internal_part_group_id,
            internal_part_group_code=item.internal_part_group_code,
            internal_part_group_title=item.internal_part_group_title,
            controller_type=item.controller_type,
            controller_bindings=item.controller_bindings,
            instance_code=item.instance_code,
            line_color=str(getattr(item, "line_color", "") or "").strip() or None,
            ui_order=item.ui_order,
            placement_z=item.placement_z,
            interior_box_snapshot=item.interior_box_snapshot,
            param_values=item.param_values,
            param_meta=item.param_meta,
            auto_params=item.auto_params,
            part_snapshots=item.part_snapshots,
            viewer_boxes=item.viewer_boxes,
        )
        for item in interior_instances
    ]
    return SubCategoryDesignPreviewResponse(
        design_id=design_id,
        sub_category_id=sub_category_id,
        design_outline_color=str(design_outline_color or "#7A4A2B").strip() or "#7A4A2B",
        resolved_params=raw_params,
        resolved_base_formulas=resolved_base_formulas,
        viewer_boxes=[
            *[item.viewer_payload["box"] for item in snapshots],
            *[
                dict(box or {})
                for item in interior_preview_items
                for box in list(item.viewer_boxes or [])
            ],
            *[
                dict(box or {})
                for item in list(door_instances or [])
                for box in list(getattr(item, "viewer_boxes", []) or [])
            ],
        ],
        parts=parts,
        interior_instances=interior_preview_items,
        door_instances=[
            {
                "id": item.instance_id,
                "door_part_group_id": item.door_part_group_id,
                "door_part_group_code": item.door_part_group_code,
                "door_part_group_title": item.door_part_group_title,
                "controller_type": item.controller_type,
                "controller_bindings": item.controller_bindings,
                "instance_code": item.instance_code,
                "line_color": str(getattr(item, "line_color", "") or "").strip() or None,
                "ui_order": int(item.ui_order or 0),
                "structural_part_formula_ids": [int(row) for row in list(item.structural_part_formula_ids or []) if int(row) > 0],
                "dependent_interior_instance_ids": [str(row).strip() for row in list(item.dependent_interior_instance_ids or []) if str(row).strip()],
                "controller_box_snapshot": dict(item.controller_box_snapshot or {}),
                "param_values": dict(item.param_values or {}),
                "param_meta": dict(item.param_meta or {}),
                "computed_params": dict(item.computed_params or {}),
                "part_snapshots": [dict(row or {}) for row in list(item.part_snapshots or [])],
                "viewer_boxes": [dict(row or {}) for row in list(item.viewer_boxes or [])],
            }
            for item in list(door_instances or [])
        ],
    )


def _deleted_design_code(code: str, design_uuid: uuid.UUID) -> str:
    suffix = f"__deleted__{str(design_uuid).replace('-', '')[:12]}"
    base = (code or "design").strip() or "design"
    max_base_len = max(1, 64 - len(suffix))
    return f"{base[:max_base_len]}{suffix}"


async def _category_outline_color(session: AsyncSession, cat_id: int) -> str:
    value = await session.scalar(select(Category.design_outline_color).where(Category.cat_id == cat_id).limit(1))
    return str(value or "#7A4A2B").strip() or "#7A4A2B"


async def _load_design(session: AsyncSession, design_uuid: uuid.UUID) -> SubCategoryDesign:
    stmt = select(SubCategoryDesign).options(
        selectinload(SubCategoryDesign.parts).selectinload(SubCategoryDesignPart.snapshots),
        selectinload(SubCategoryDesign.sub_category).selectinload(SubCategory.category),
    )
    if await interior_instance_tables_ready(session):
        stmt = stmt.options(selectinload(SubCategoryDesign.interior_instances))
    if await door_instance_tables_ready(session):
        stmt = stmt.options(selectinload(SubCategoryDesign.door_instances))
    item = await session.scalar(
        stmt.where(
            and_(
                SubCategoryDesign.id == design_uuid,
                SubCategoryDesign.deleted_at.is_(None),
            )
        )
    )
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sub-category design not found.")
    return item


async def _replace_parts(
    session: AsyncSession,
    *,
    design: SubCategoryDesign,
    sub_category: SubCategory,
    parts: list[SubCategoryDesignPartSelectionPayload],
) -> None:
    from designkp_backend.services.sub_category_designs import require_accessible_part_formulas

    next_formulas = await require_accessible_part_formulas(
        session,
        admin_id=design.admin_id,
        part_formula_ids=[int(item.part_formula_id) for item in parts if item.enabled],
    )
    by_formula_id = {int(item.part_formula_id): item for item in next_formulas}

    existing_parts = list(design.__dict__.get("parts") or [])
    existing_by_formula_id = {int(item.part_formula_id): item for item in existing_parts}
    next_formula_ids = {int(item.part_formula_id) for item in parts}
    for formula_id, row in list(existing_by_formula_id.items()):
        if formula_id not in next_formula_ids:
            await session.delete(row)

    for selection in parts:
        formula_id = int(selection.part_formula_id)
        formula = by_formula_id.get(formula_id)
        existing = existing_by_formula_id.get(formula_id)
        if not formula:
            if existing is not None:
                existing.enabled = False
                existing.ui_order = int(selection.ui_order)
            continue
        if existing is None:
            existing = SubCategoryDesignPart(
                design=design,
                part_formula_id=formula_id,
                part_kind_id=int(formula.part_kind_id),
                part_code=formula.part_code,
                part_title=formula.part_title,
                enabled=selection.enabled,
                ui_order=int(selection.ui_order),
            )
            session.add(existing)
        else:
            existing.part_kind_id = int(formula.part_kind_id)
            existing.part_code = formula.part_code
            existing.part_title = formula.part_title
            existing.enabled = selection.enabled
            existing.ui_order = int(selection.ui_order)


@router.get("", response_model=list[SubCategoryDesignItem])
async def list_sub_category_designs(
    admin_id: uuid.UUID | None = Query(default=None),
    sub_cat_id: int | None = Query(default=None),
    session: AsyncSession = Depends(get_db_session),
) -> list[SubCategoryDesignItem]:
    await require_admin_if_present(session, admin_id)
    include_interior = await interior_instance_tables_ready(session)
    include_doors = await door_instance_tables_ready(session)
    stmt = select(SubCategoryDesign).options(
        selectinload(SubCategoryDesign.parts),
        selectinload(SubCategoryDesign.sub_category).selectinload(SubCategory.category),
    )
    if include_interior:
        stmt = stmt.options(selectinload(SubCategoryDesign.interior_instances))
    if include_doors:
        stmt = stmt.options(selectinload(SubCategoryDesign.door_instances))
    if admin_id is None:
        stmt = stmt.where(
            and_(
                SubCategoryDesign.admin_id.is_(None),
                SubCategoryDesign.deleted_at.is_(None),
            )
        )
    else:
        stmt = stmt.where(
            and_(
                or_(SubCategoryDesign.admin_id.is_(None), SubCategoryDesign.admin_id == admin_id),
                SubCategoryDesign.deleted_at.is_(None),
            )
        )
    stmt = stmt.order_by(
        SubCategoryDesign.is_system.desc(),
        SubCategoryDesign.sort_order.asc(),
        SubCategoryDesign.design_id.asc(),
    )
    if sub_cat_id is not None:
        stmt = stmt.where(SubCategoryDesign.sub_cat_id == sub_cat_id)
    items = (await session.scalars(stmt)).all()
    return [
        _serialize_design(
            item,
            include_interior=(include_interior or include_doors),
            design_outline_color=getattr(getattr(item.sub_category, "category", None), "design_outline_color", "#7A4A2B"),
        )
        for item in items
    ]


@router.post("", response_model=SubCategoryDesignItem, status_code=status.HTTP_201_CREATED)
async def create_sub_category_design(payload: SubCategoryDesignCreate, session: AsyncSession = Depends(get_db_session)) -> SubCategoryDesignItem:
    await require_admin_if_present(session, payload.admin_id)
    sub_category = await require_accessible_sub_category(session, admin_id=payload.admin_id, sub_category_id=payload.sub_category_id)
    next_design_id = await _resolve_available_design_id(session, payload.design_id)
    title = payload.design_title.strip()
    code = payload.code.strip()
    if not code:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Design code is required.")
    await _ensure_unique_design_code(session, code=code)
    item = SubCategoryDesign(
        admin_id=payload.admin_id,
        sub_category_id=sub_category.id,
        temp_id=sub_category.temp_id,
        cat_id=sub_category.cat_id,
        sub_cat_id=sub_category.sub_cat_id,
        design_id=next_design_id,
        design_title=title,
        code=code,
        title=title,
        sort_order=payload.sort_order if payload.sort_order is not None else next_design_id,
        is_system=payload.is_system,
    )
    session.add(item)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Design ID or code is already used.") from exc
    await _replace_parts(session, design=item, sub_category=sub_category, parts=payload.parts)
    item = await _load_design(session, item.id)
    await _replace_interior_instances(session, design=item, payloads=list(payload.interior_instances or []))
    item = await _load_design(session, item.id)
    await _replace_door_instances(session, design=item, payloads=list(payload.door_instances or []))
    await session.flush()
    item = await _load_design(session, item.id)
    await rebuild_design_snapshots(session, item)
    await session.commit()
    item = await _load_design(session, item.id)
    return _serialize_design(
        item,
        include_interior=await interior_instance_tables_ready(session),
        design_outline_color=await _category_outline_color(session, sub_category.cat_id),
    )


@router.patch("/{design_uuid}", response_model=SubCategoryDesignItem)
async def update_sub_category_design(
    design_uuid: uuid.UUID,
    payload: SubCategoryDesignUpdate,
    session: AsyncSession = Depends(get_db_session),
) -> SubCategoryDesignItem:
    item = await _load_design(session, design_uuid)
    await require_admin_if_present(session, payload.admin_id)
    sub_category = await require_accessible_sub_category(session, admin_id=payload.admin_id, sub_category_id=payload.sub_category_id)
    next_design_id = await _resolve_available_design_id(session, payload.design_id, exclude_uuid=item.id)
    title = payload.design_title.strip()
    code = payload.code.strip()
    if not code:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Design code is required.")
    await _ensure_unique_design_code(session, code=code, exclude_id=item.id)
    item.admin_id = payload.admin_id
    item.sub_category_id = sub_category.id
    item.temp_id = sub_category.temp_id
    item.cat_id = sub_category.cat_id
    item.sub_cat_id = sub_category.sub_cat_id
    item.design_id = next_design_id
    item.design_title = title
    item.code = code
    item.title = title
    item.sort_order = payload.sort_order
    item.is_system = payload.is_system
    await _replace_parts(session, design=item, sub_category=sub_category, parts=payload.parts)
    item = await _load_design(session, item.id)
    await _replace_interior_instances(session, design=item, payloads=list(payload.interior_instances or []))
    item = await _load_design(session, item.id)
    await _replace_door_instances(session, design=item, payloads=list(payload.door_instances or []))
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Design ID or code is already used.") from exc
    item = await _load_design(session, item.id)
    await rebuild_design_snapshots(session, item)
    await session.commit()
    item = await _load_design(session, item.id)
    return _serialize_design(
        item,
        include_interior=await interior_instance_tables_ready(session),
        design_outline_color=await _category_outline_color(session, sub_category.cat_id),
    )


@router.delete("/{design_uuid}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_sub_category_design(design_uuid: uuid.UUID, session: AsyncSession = Depends(get_db_session)) -> Response:
    item = await session.get(SubCategoryDesign, design_uuid)
    if not item or item.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sub-category design not found.")
    try:
        deleted_at = datetime.now(timezone.utc)
        item.deleted_at = deleted_at
        item.design_id = None
        item.code = _deleted_design_code(item.code, item.id)
        await session.execute(
            delete(SubCategoryDesignPart).where(SubCategoryDesignPart.design_id == design_uuid)
        )
        if await interior_instance_tables_ready(session):
            await session.execute(
                delete(SubCategoryDesignInteriorInstance).where(SubCategoryDesignInteriorInstance.design_id == design_uuid)
            )
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This sub-category design is still referenced and cannot be deleted.",
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/preview-draft", response_model=SubCategoryDesignPreviewResponse)
async def preview_sub_category_design_draft(
    payload: SubCategoryDesignPreviewDraftRequest,
    session: AsyncSession = Depends(get_db_session),
) -> SubCategoryDesignPreviewResponse:
    await require_admin_if_present(session, payload.admin_id)
    sub_category = await require_accessible_sub_category(session, admin_id=payload.admin_id, sub_category_id=payload.sub_category_id)
    raw_params, resolved_base_formulas, snapshots, interior_instances, door_instances = await compose_sub_category_design_preview(
        session,
        admin_id=payload.admin_id,
        sub_category=sub_category,
        part_selections=[item.model_dump() for item in payload.parts],
        interior_instances=payload.interior_instances,
        door_instances=[
            SubCategoryDesignDoorInstance(
                id=item.id or uuid.uuid4(),
                design_id=uuid.uuid4(),
                door_part_group_id=item.door_part_group_id,
                instance_code=str(item.instance_code or "").strip(),
                line_color=item.line_color,
                ui_order=int(item.ui_order or 0),
                structural_part_formula_ids=[int(row) for row in list(item.structural_part_formula_ids or []) if int(row) > 0],
                dependent_interior_instance_ids=[str(row).strip() for row in list(item.dependent_interior_instance_ids or []) if str(row).strip()],
                controller_box_snapshot=dict(item.controller_box_snapshot or {}),
                param_values={str(key): value for key, value in dict(item.param_values or {}).items()},
                param_meta={str(key): dict(value or {}) for key, value in dict(item.param_meta or {}).items()},
                part_snapshots=[],
                viewer_boxes=[],
                status="draft",
            )
            for item in list(payload.door_instances or [])
        ],
    )
    return _serialize_preview(
        design_id=None,
        sub_category_id=sub_category.id,
        design_outline_color=await _category_outline_color(session, sub_category.cat_id),
        raw_params=raw_params,
        resolved_base_formulas=resolved_base_formulas,
        snapshots=snapshots,
        interior_instances=interior_instances,
        door_instances=door_instances,
    )


@router.post("/{design_uuid}/parts/rebuild", response_model=SubCategoryDesignPreviewResponse)
async def rebuild_sub_category_design_parts(design_uuid: uuid.UUID, session: AsyncSession = Depends(get_db_session)) -> SubCategoryDesignPreviewResponse:
    item = await _load_design(session, design_uuid)
    await rebuild_design_snapshots(session, item)
    await session.commit()
    return await preview_sub_category_design(design_uuid, session)


@router.get("/{design_uuid}/preview", response_model=SubCategoryDesignPreviewResponse)
async def preview_sub_category_design(design_uuid: uuid.UUID, session: AsyncSession = Depends(get_db_session)) -> SubCategoryDesignPreviewResponse:
    item = await _load_design(session, design_uuid)
    include_interior = await interior_instance_tables_ready(session)
    include_doors = await door_instance_tables_ready(session)
    sub_category = await session.get(SubCategory, item.sub_category_id)
    if not sub_category or sub_category.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sub-category not found for this design.")
    raw_params, resolved_base_formulas, snapshots, interior_instances, door_instances = await compose_sub_category_design_preview(
        session,
        admin_id=item.admin_id,
        sub_category=sub_category,
        part_selections=[
            {
                "part_formula_id": int(part.part_formula_id or 0),
                "enabled": bool(part.enabled),
                "ui_order": int(part.ui_order or 0),
            }
            for part in list(item.parts or [])
        ],
        interior_instances=list(item.interior_instances or []) if include_interior else [],
        door_instances=list(getattr(item, "__dict__", {}).get("door_instances") or []) if include_doors else [],
    )
    return _serialize_preview(
        design_id=item.id,
        sub_category_id=sub_category.id,
        design_outline_color=await _category_outline_color(session, sub_category.cat_id),
        raw_params=raw_params,
        resolved_base_formulas=resolved_base_formulas,
        snapshots=snapshots,
        interior_instances=interior_instances,
        door_instances=door_instances,
    )


def _normalize_interior_param_values(payload: dict[str, str | int | float | bool | None]) -> dict[str, str | None]:
    return {
        str(key): (None if value is None else str(value))
        for key, value in dict(payload or {}).items()
        if str(key or "").strip()
    }


def _normalize_door_param_values(payload: dict[str, str | int | float | bool | None]) -> dict[str, str | None]:
    return {
        str(key): (None if value is None else str(value))
        for key, value in dict(payload or {}).items()
        if str(key or "").strip()
    }


def _next_generated_interior_instance_code(
    *,
    existing_instances: list[object],
    group_code: str | None,
    fallback_order: int,
) -> str:
    prefix = str(group_code or "interior").strip() or "interior"
    existing_codes = {
        str(getattr(item, "instance_code", "") or "").strip()
        for item in list(existing_instances or [])
    }
    suffix = max(1, int(fallback_order) + 1)
    while True:
        candidate = f"{prefix}-{suffix:02d}"
        if candidate not in existing_codes:
            return candidate
        suffix += 1


def _next_generated_door_instance_code(
    *,
    existing_instances: list[object],
    group_code: str | None,
    fallback_order: int,
) -> str:
    prefix = str(group_code or "door").strip() or "door"
    existing_codes = {
        str(getattr(item, "instance_code", "") or "").strip()
        for item in list(existing_instances or [])
    }
    suffix = max(1, int(fallback_order) + 1)
    while True:
        candidate = f"{prefix}-{suffix:02d}"
        if candidate not in existing_codes:
            return candidate
        suffix += 1


def _design_base_boxes(design: SubCategoryDesign) -> list[dict[str, object]]:
    boxes: list[dict[str, object]] = []
    for part in sorted(list(design.parts or []), key=lambda row: (int(row.ui_order or 0), int(row.part_formula_id or 0))):
        snapshot = next((snap for snap in list(part.snapshots or []) if snap.viewer_payload), None)
        viewer_payload = snapshot.viewer_payload if snapshot else {}
        box = viewer_payload.get("box") if isinstance(viewer_payload, dict) else None
        if isinstance(box, dict):
            boxes.append(dict(box))
    return boxes


async def _refresh_design_interior_instance(
    session: AsyncSession,
    *,
    design: SubCategoryDesign,
    instance: SubCategoryDesignInteriorInstance,
) -> None:
    sub_category = await require_accessible_sub_category(session, admin_id=design.admin_id, sub_category_id=design.sub_category_id)
    group = await require_accessible_internal_part_group(session, admin_id=design.admin_id, group_id=instance.internal_part_group_id)
    interior_box_snapshot = dict(instance.interior_box_snapshot or {})
    if not interior_box_snapshot:
        interior_box_snapshot = derive_interior_box_snapshot(_design_base_boxes(design))
    resolved = await resolve_internal_instance_preview(
        session,
        admin_id=design.admin_id,
        sub_category=sub_category,
        internal_group=group,
        instance_id=instance.id,
        instance_code=str(instance.instance_code or ""),
        ui_order=int(instance.ui_order or 0),
        placement_z=float(instance.placement_z or 0),
        interior_box_snapshot=interior_box_snapshot,
        param_values=dict(instance.param_values or {}),
        param_meta=dict(instance.param_meta or {}),
    )
    instance.interior_box_snapshot = resolved.interior_box_snapshot
    instance.param_values = resolved.param_values
    instance.param_meta = resolved.param_meta
    instance.part_snapshots = resolved.part_snapshots
    instance.viewer_boxes = resolved.viewer_boxes

    # Keep dependent door controllers in sync with interior moves.
    target_id = str(getattr(instance, "id", "") or "").strip()
    if target_id:
        for door in list(getattr(design, "door_instances", []) or []):
            deps = [
                str(row).strip()
                for row in list(getattr(door, "dependent_interior_instance_ids", []) or [])
                if str(row).strip()
            ]
            if target_id in deps:
                await _refresh_design_door_instance(session, design=design, instance=door)
                continue
            controller_snapshot = dict(getattr(door, "controller_box_snapshot", {}) or {})
            selected_parts = list(controller_snapshot.get("selected_parts") or [])
            if any(
                str(part.get("source_type") or "") == "interior"
                and str(part.get("source_id") or "").strip() == target_id
                for part in selected_parts
            ):
                await _refresh_design_door_instance(session, design=design, instance=door)


async def _next_interior_instance_state(
    session: AsyncSession,
    *,
    design: SubCategoryDesign,
    group_id: uuid.UUID,
    placement_z: float,
    ui_order: int | None,
    instance_code: str | None,
    param_values: dict[str, str | int | float | bool | None],
) -> tuple[str, int, dict[str, object], dict[str, str | None], dict[str, dict[str, object]]]:
    sub_category = await require_accessible_sub_category(session, admin_id=design.admin_id, sub_category_id=design.sub_category_id)
    group = await require_accessible_internal_part_group(session, admin_id=design.admin_id, group_id=group_id)
    existing = list(design.interior_instances or [])
    next_order = ui_order if ui_order is not None else (max([int(item.ui_order or 0) for item in existing], default=-1) + 1)
    next_code = str(instance_code or "").strip() or _next_generated_interior_instance_code(
        existing_instances=existing,
        group_code=getattr(group, "code", None),
        fallback_order=next_order,
    )
    base_boxes = _design_base_boxes(design)
    interior_box_snapshot = derive_interior_box_snapshot(base_boxes)
    normalized_values = _normalize_interior_param_values(param_values)
    resolved = await resolve_internal_instance_preview(
        session,
        admin_id=design.admin_id,
        sub_category=sub_category,
        internal_group=group,
        instance_id=None,
        instance_code=next_code,
        ui_order=next_order,
        placement_z=placement_z,
        interior_box_snapshot=interior_box_snapshot,
        param_values=normalized_values,
        param_meta={},
    )
    return next_code, next_order, resolved.interior_box_snapshot, resolved.param_values, resolved.param_meta


async def _refresh_design_door_instance(
    session: AsyncSession,
    *,
    design: SubCategoryDesign,
    instance: SubCategoryDesignDoorInstance,
) -> None:
    sub_category = await require_accessible_sub_category(session, admin_id=design.admin_id, sub_category_id=design.sub_category_id)
    group = await require_accessible_door_part_group(session, admin_id=design.admin_id, group_id=instance.door_part_group_id)
    part_boxes = {
        int(part.part_formula_id): dict(snapshot.viewer_payload.get("box") or {})
        for part in list(design.parts or [])
        for snapshot in list(part.snapshots or [])[:1]
        if bool(part.enabled) and isinstance(snapshot.viewer_payload, dict) and isinstance(snapshot.viewer_payload.get("box"), dict)
    }
    allowed_dependent_ids = {
        str(item.id)
        for item in list(getattr(design, "interior_instances", []) or [])
        if getattr(item, "id", None) is not None
    }
    normalized_dependent_ids = [
        str(row).strip()
        for row in list(instance.dependent_interior_instance_ids or [])
        if str(row).strip() and str(row).strip() in allowed_dependent_ids
    ]
    for interior in list(getattr(design, "interior_instances", []) or []):
        if str(getattr(interior, "id", "") or "") not in normalized_dependent_ids:
            continue
        for row in list(getattr(interior, "part_snapshots", []) or []):
            box = dict((row or {}).get("viewer_payload", {}) or {}).get("box")
            part_formula_id = int((row or {}).get("part_formula_id") or 0)
            if part_formula_id > 0 and isinstance(box, dict):
                part_boxes[part_formula_id] = dict(box)
    part_boxes.update(
        _collect_controller_selection_boxes_by_formula_id(
            controller_box_snapshot=dict(instance.controller_box_snapshot or {}),
            root_part_snapshots=[
                {
                    "part_formula_id": int(part.part_formula_id or 0),
                    "viewer_payload": dict(getattr(snapshot, "viewer_payload", {}) or {}),
                }
                for part in list(design.parts or [])
                for snapshot in list(part.snapshots or [])[:1]
            ],
            interiors=list(getattr(design, "interior_instances", []) or []),
        )
    )
    selected_part_boxes = _collect_controller_selection_boxes(
        controller_box_snapshot=dict(instance.controller_box_snapshot or {}),
        root_part_snapshots=[
            {
                "part_formula_id": int(part.part_formula_id or 0),
                "viewer_payload": dict(getattr(snapshot, "viewer_payload", {}) or {}),
            }
            for part in list(design.parts or [])
            for snapshot in list(part.snapshots or [])[:1]
        ],
        interiors=list(getattr(design, "interior_instances", []) or []),
    )
    resolved = await resolve_door_instance_preview(
        session,
        admin_id=design.admin_id,
        sub_category=sub_category,
        door_part_group=group,
        instance_id=instance.id,
        instance_code=str(instance.instance_code or ""),
        line_color=str(getattr(instance, "line_color", "") or "").strip() or None,
        ui_order=int(instance.ui_order or 0),
        structural_part_formula_ids=list(instance.structural_part_formula_ids or []),
        dependent_interior_instance_ids=normalized_dependent_ids,
        controller_box_snapshot=dict(instance.controller_box_snapshot or {}),
        param_values=dict(instance.param_values or {}),
        param_meta=dict(instance.param_meta or {}),
        source_boxes_by_formula_id=part_boxes,
        selected_part_boxes=selected_part_boxes,
    )
    instance.controller_box_snapshot = resolved.controller_box_snapshot
    instance.param_values = resolved.param_values
    instance.param_meta = resolved.param_meta
    instance.part_snapshots = resolved.part_snapshots
    instance.viewer_boxes = resolved.viewer_boxes


async def _next_door_instance_state(
    session: AsyncSession,
    *,
    design: SubCategoryDesign,
    group_id: uuid.UUID,
    ui_order: int | None,
    instance_code: str | None,
    structural_part_formula_ids: list[int],
    dependent_interior_instance_ids: list[uuid.UUID | str],
    controller_box_snapshot: dict[str, object],
    param_values: dict[str, str | int | float | bool | None],
) -> tuple[str, int, dict[str, object], dict[str, str | None], dict[str, dict[str, object]]]:
    sub_category = await require_accessible_sub_category(session, admin_id=design.admin_id, sub_category_id=design.sub_category_id)
    group = await require_accessible_door_part_group(session, admin_id=design.admin_id, group_id=group_id)
    existing = list(getattr(design, "door_instances", []) or [])
    next_order = ui_order if ui_order is not None else (max([int(item.ui_order or 0) for item in existing], default=-1) + 1)
    next_code = str(instance_code or "").strip() or _next_generated_door_instance_code(
        existing_instances=existing,
        group_code=getattr(group, "code", None),
        fallback_order=next_order,
    )
    part_boxes = {
        int(part.part_formula_id): dict(snapshot.viewer_payload.get("box") or {})
        for part in list(design.parts or [])
        for snapshot in list(part.snapshots or [])[:1]
        if bool(part.enabled) and isinstance(snapshot.viewer_payload, dict) and isinstance(snapshot.viewer_payload.get("box"), dict)
    }
    normalized_dependent_ids = [str(row).strip() for row in list(dependent_interior_instance_ids or []) if str(row).strip()]
    allowed_dependent_ids = {
        str(item.id)
        for item in list(getattr(design, "interior_instances", []) or [])
        if getattr(item, "id", None) is not None
    }
    normalized_dependent_ids = [row for row in normalized_dependent_ids if row in allowed_dependent_ids]
    for interior in list(getattr(design, "interior_instances", []) or []):
        if str(getattr(interior, "id", "") or "") not in normalized_dependent_ids:
            continue
        for row in list(getattr(interior, "part_snapshots", []) or []):
            box = dict((row or {}).get("viewer_payload", {}) or {}).get("box")
            part_formula_id = int((row or {}).get("part_formula_id") or 0)
            if part_formula_id > 0 and isinstance(box, dict):
                part_boxes[part_formula_id] = dict(box)
    part_boxes.update(
        _collect_controller_selection_boxes_by_formula_id(
            controller_box_snapshot=dict(controller_box_snapshot or {}),
            root_part_snapshots=[
                {
                    "part_formula_id": int(part.part_formula_id or 0),
                    "viewer_payload": dict(getattr(snapshot, "viewer_payload", {}) or {}),
                }
                for part in list(design.parts or [])
                for snapshot in list(part.snapshots or [])[:1]
            ],
            interiors=list(getattr(design, "interior_instances", []) or []),
        )
    )
    selected_part_boxes = _collect_controller_selection_boxes(
        controller_box_snapshot=dict(controller_box_snapshot or {}),
        root_part_snapshots=[
            {
                "part_formula_id": int(part.part_formula_id or 0),
                "viewer_payload": dict(getattr(snapshot, "viewer_payload", {}) or {}),
            }
            for part in list(design.parts or [])
            for snapshot in list(part.snapshots or [])[:1]
        ],
        interiors=list(getattr(design, "interior_instances", []) or []),
    )
    resolved = await resolve_door_instance_preview(
        session,
        admin_id=design.admin_id,
        sub_category=sub_category,
        door_part_group=group,
        instance_id=None,
        instance_code=next_code,
        line_color=str(getattr(group, "line_color", "") or "").strip() or None,
        ui_order=next_order,
        structural_part_formula_ids=structural_part_formula_ids,
        dependent_interior_instance_ids=normalized_dependent_ids,
        controller_box_snapshot=dict(controller_box_snapshot or {}),
        param_values=_normalize_door_param_values(param_values),
        param_meta={},
        source_boxes_by_formula_id=part_boxes,
        selected_part_boxes=selected_part_boxes,
    )
    return next_code, next_order, resolved.controller_box_snapshot, resolved.param_values, resolved.param_meta


async def _replace_interior_instances(
    session: AsyncSession,
    *,
    design: SubCategoryDesign,
    payloads: list[SubCategoryDesignInteriorInstanceDraftPayload],
) -> None:
    if not await interior_instance_tables_ready(session):
        return
    existing = {item.id: item for item in list(getattr(design, "interior_instances", []) or []) if getattr(item, "id", None) is not None}
    keep_ids = {item.id for item in list(payloads or []) if item.id is not None}
    for instance in list(getattr(design, "interior_instances", []) or []):
        if instance.id not in keep_ids:
            await session.delete(instance)
    await session.flush()
    design = await _load_design(session, design.id)
    for payload in sorted(list(payloads or []), key=lambda row: (int(row.ui_order or 0), str(row.instance_code or ""))):
        target = existing.get(payload.id) if payload.id is not None else None
        if target is None:
            next_code, next_order, interior_box_snapshot, param_values, param_meta = await _next_interior_instance_state(
                session,
                design=design,
                group_id=payload.internal_part_group_id,
                placement_z=float(payload.placement_z or 0),
                ui_order=int(payload.ui_order or 0),
                instance_code=str(payload.instance_code or "").strip() or None,
                param_values=dict(payload.param_values or {}),
            )
            target = SubCategoryDesignInteriorInstance(
                design=design,
                internal_part_group_id=payload.internal_part_group_id,
                instance_code=next_code,
                line_color=_normalize_hex_color(payload.line_color, DEFAULT_INTERIOR_LINE_COLOR) if payload.line_color else None,
                ui_order=next_order,
                placement_z=float(payload.placement_z or 0),
                interior_box_snapshot=interior_box_snapshot,
                param_values=param_values,
                param_meta=param_meta,
                status="draft",
            )
            session.add(target)
            await session.flush()
        else:
            target.internal_part_group_id = payload.internal_part_group_id
            target.instance_code = str(payload.instance_code or "").strip()
            target.line_color = _normalize_hex_color(payload.line_color, DEFAULT_INTERIOR_LINE_COLOR) if payload.line_color else None
            target.ui_order = int(payload.ui_order or 0)
            target.placement_z = float(payload.placement_z or 0)
            target.param_values = _normalize_interior_param_values(payload.param_values)
            target.param_meta = {str(key): dict(value or {}) for key, value in dict(payload.param_meta or {}).items()}
            await session.flush()
        design = await _load_design(session, design.id)
        target = next(instance for instance in design.interior_instances if instance.id == target.id)
        await _refresh_design_interior_instance(session, design=design, instance=target)
        await session.flush()
        design = await _load_design(session, design.id)


async def _replace_door_instances(
    session: AsyncSession,
    *,
    design: SubCategoryDesign,
    payloads: list[SubCategoryDesignDoorInstanceDraftPayload],
) -> None:
    if not await door_instance_tables_ready(session):
        return
    existing = {item.id: item for item in list(getattr(design, "door_instances", []) or []) if getattr(item, "id", None) is not None}
    keep_ids = {item.id for item in list(payloads or []) if item.id is not None}
    for instance in list(getattr(design, "door_instances", []) or []):
        if instance.id not in keep_ids:
            await session.delete(instance)
    await session.flush()
    design = await _load_design(session, design.id)
    for payload in sorted(list(payloads or []), key=lambda row: (int(row.ui_order or 0), str(row.instance_code or ""))):
        target = existing.get(payload.id) if payload.id is not None else None
        if target is None:
            next_code, next_order, controller_box_snapshot, param_values, param_meta = await _next_door_instance_state(
                session,
                design=design,
                group_id=payload.door_part_group_id,
                ui_order=int(payload.ui_order or 0),
                instance_code=str(payload.instance_code or "").strip() or None,
                structural_part_formula_ids=list(payload.structural_part_formula_ids or []),
                dependent_interior_instance_ids=list(payload.dependent_interior_instance_ids or []),
                controller_box_snapshot=dict(payload.controller_box_snapshot or {}),
                param_values=dict(payload.param_values or {}),
            )
            target = SubCategoryDesignDoorInstance(
                design=design,
                door_part_group_id=payload.door_part_group_id,
                instance_code=next_code,
                line_color=_normalize_hex_color(payload.line_color, DEFAULT_INTERIOR_LINE_COLOR) if payload.line_color else None,
                ui_order=next_order,
                structural_part_formula_ids=[int(row) for row in list(payload.structural_part_formula_ids or []) if int(row) > 0],
                dependent_interior_instance_ids=[str(row).strip() for row in list(payload.dependent_interior_instance_ids or []) if str(row).strip()],
                controller_box_snapshot=controller_box_snapshot,
                param_values=param_values,
                param_meta=param_meta,
                status="draft",
            )
            session.add(target)
            await session.flush()
        else:
            target.door_part_group_id = payload.door_part_group_id
            target.instance_code = str(payload.instance_code or "").strip()
            target.line_color = _normalize_hex_color(payload.line_color, DEFAULT_INTERIOR_LINE_COLOR) if payload.line_color else None
            target.ui_order = int(payload.ui_order or 0)
            target.structural_part_formula_ids = [int(row) for row in list(payload.structural_part_formula_ids or []) if int(row) > 0]
            target.dependent_interior_instance_ids = [str(row).strip() for row in list(payload.dependent_interior_instance_ids or []) if str(row).strip()]
            target.param_values = _normalize_door_param_values(payload.param_values)
            target.param_meta = {str(key): dict(value or {}) for key, value in dict(payload.param_meta or {}).items()}
            await session.flush()
        design = await _load_design(session, design.id)
        target = next(instance for instance in design.door_instances if instance.id == target.id)
        await _refresh_design_door_instance(session, design=design, instance=target)
        await session.flush()
        design = await _load_design(session, design.id)


@router.post("/{design_uuid}/interior-instances", response_model=SubCategoryDesignInteriorInstanceItem, status_code=status.HTTP_201_CREATED)
async def create_sub_category_design_interior_instance(
    design_uuid: uuid.UUID,
    payload: SubCategoryDesignInteriorInstanceCreate,
    session: AsyncSession = Depends(get_db_session),
) -> SubCategoryDesignInteriorInstanceItem:
    if not await interior_instance_tables_ready(session):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Interior-instance tables are not available yet. Run database migrations first.")
    design = await _load_design(session, design_uuid)
    group = await require_accessible_internal_part_group(
        session,
        admin_id=design.admin_id,
        group_id=payload.internal_part_group_id,
    )
    next_code, next_order, interior_box_snapshot, param_values, param_meta = await _next_interior_instance_state(
        session,
        design=design,
        group_id=payload.internal_part_group_id,
        placement_z=float(payload.placement_z or 0),
        ui_order=payload.ui_order,
        instance_code=payload.instance_code,
        param_values=payload.param_values,
    )
    item = SubCategoryDesignInteriorInstance(
        design=design,
        internal_part_group_id=payload.internal_part_group_id,
        instance_code=next_code,
        line_color=_normalize_hex_color(payload.line_color, DEFAULT_INTERIOR_LINE_COLOR) if payload.line_color else _normalize_hex_color(getattr(group, "line_color", None), DEFAULT_INTERIOR_LINE_COLOR),
        ui_order=next_order,
        placement_z=float(payload.placement_z or 0),
        interior_box_snapshot=interior_box_snapshot,
        param_values=param_values,
        param_meta=param_meta,
        status="draft",
    )
    session.add(item)
    await session.flush()
    design = await _load_design(session, design.id)
    target = next(instance for instance in design.interior_instances if instance.id == item.id)
    await _refresh_design_interior_instance(session, design=design, instance=target)
    await session.commit()
    design = await _load_design(session, design.id)
    target = next(instance for instance in design.interior_instances if instance.id == item.id)
    return SubCategoryDesignInteriorInstanceItem.model_validate(target)


@router.patch("/{design_uuid}/interior-instances/{instance_id}", response_model=SubCategoryDesignInteriorInstanceItem)
async def update_sub_category_design_interior_instance(
    design_uuid: uuid.UUID,
    instance_id: uuid.UUID,
    payload: SubCategoryDesignInteriorInstanceUpdate,
    session: AsyncSession = Depends(get_db_session),
) -> SubCategoryDesignInteriorInstanceItem:
    if not await interior_instance_tables_ready(session):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Interior-instance tables are not available yet. Run database migrations first.")
    design = await _load_design(session, design_uuid)
    item = next((row for row in design.interior_instances if row.id == instance_id), None)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sub-category design interior instance not found.")
    item.instance_code = str(payload.instance_code or "").strip()
    item.line_color = _normalize_hex_color(payload.line_color, DEFAULT_INTERIOR_LINE_COLOR) if payload.line_color else None
    item.ui_order = int(payload.ui_order)
    item.placement_z = float(payload.placement_z or 0)
    item.param_values = _normalize_interior_param_values(payload.param_values)
    await session.flush()
    design = await _load_design(session, design.id)
    target = next(instance for instance in design.interior_instances if instance.id == item.id)
    await _refresh_design_interior_instance(session, design=design, instance=target)
    await session.commit()
    design = await _load_design(session, design.id)
    target = next(instance for instance in design.interior_instances if instance.id == item.id)
    return SubCategoryDesignInteriorInstanceItem.model_validate(target)


@router.post("/{design_uuid}/interior-instances/{instance_id}/duplicate", response_model=SubCategoryDesignInteriorInstanceItem, status_code=status.HTTP_201_CREATED)
async def duplicate_sub_category_design_interior_instance(
    design_uuid: uuid.UUID,
    instance_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> SubCategoryDesignInteriorInstanceItem:
    if not await interior_instance_tables_ready(session):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Interior-instance tables are not available yet. Run database migrations first.")
    design = await _load_design(session, design_uuid)
    source = next((row for row in design.interior_instances if row.id == instance_id), None)
    if not source:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sub-category design interior instance not found.")
    group = await require_accessible_internal_part_group(
        session,
        admin_id=design.admin_id,
        group_id=source.internal_part_group_id,
    )
    next_code, next_order, interior_box_snapshot, param_values, param_meta = await _next_interior_instance_state(
        session,
        design=design,
        group_id=source.internal_part_group_id,
        placement_z=float(source.placement_z or 0),
        ui_order=max([int(row.ui_order or 0) for row in list(design.interior_instances or [])], default=-1) + 1,
        instance_code=None,
        param_values=dict(source.param_values or {}),
    )
    item = SubCategoryDesignInteriorInstance(
        design=design,
        internal_part_group_id=source.internal_part_group_id,
        instance_code=next_code,
        line_color=_normalize_hex_color(getattr(source, "line_color", None), DEFAULT_INTERIOR_LINE_COLOR) if getattr(source, "line_color", None) else _normalize_hex_color(getattr(group, "line_color", None), DEFAULT_INTERIOR_LINE_COLOR),
        ui_order=next_order,
        placement_z=float(source.placement_z or 0),
        interior_box_snapshot=interior_box_snapshot,
        param_values=param_values,
        param_meta=param_meta,
        status=str(source.status or "draft").strip() or "draft",
    )
    session.add(item)
    await session.flush()
    design = await _load_design(session, design.id)
    target = next(instance for instance in design.interior_instances if instance.id == item.id)
    await _refresh_design_interior_instance(session, design=design, instance=target)
    await session.commit()
    design = await _load_design(session, design.id)
    target = next(instance for instance in design.interior_instances if instance.id == item.id)
    return SubCategoryDesignInteriorInstanceItem.model_validate(target)


@router.delete("/{design_uuid}/interior-instances/{instance_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_sub_category_design_interior_instance(
    design_uuid: uuid.UUID,
    instance_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    if not await interior_instance_tables_ready(session):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Interior-instance tables are not available yet. Run database migrations first.")
    design = await _load_design(session, design_uuid)
    item = next((row for row in design.interior_instances if row.id == instance_id), None)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sub-category design interior instance not found.")
    await session.delete(item)
    await session.flush()
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{design_uuid}/door-instances", response_model=SubCategoryDesignDoorInstanceItem, status_code=status.HTTP_201_CREATED)
async def create_sub_category_design_door_instance(
    design_uuid: uuid.UUID,
    payload: SubCategoryDesignDoorInstanceCreate,
    session: AsyncSession = Depends(get_db_session),
) -> SubCategoryDesignDoorInstanceItem:
    if not await door_instance_tables_ready(session):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Door-instance tables are not available yet. Run database migrations first.")
    design = await _load_design(session, design_uuid)
    group = await require_accessible_door_part_group(session, admin_id=design.admin_id, group_id=payload.door_part_group_id)
    structural_part_formula_ids = [int(row) for row in list(payload.structural_part_formula_ids or []) if int(row) > 0]
    if str(getattr(group, "controller_type", "") or "").strip() == "double_equal_hinged_doors" and len(set(structural_part_formula_ids)) != 4:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Double-equal hinged door controller requires exactly 4 structural parts.")
    next_code, next_order, controller_box_snapshot, param_values, param_meta = await _next_door_instance_state(
        session,
        design=design,
        group_id=payload.door_part_group_id,
        ui_order=payload.ui_order,
        instance_code=payload.instance_code,
        structural_part_formula_ids=structural_part_formula_ids,
        dependent_interior_instance_ids=list(payload.dependent_interior_instance_ids or []),
        controller_box_snapshot=dict(payload.controller_box_snapshot or {}),
        param_values=payload.param_values,
    )
    item = SubCategoryDesignDoorInstance(
        design=design,
        door_part_group_id=payload.door_part_group_id,
        instance_code=next_code,
        line_color=_normalize_hex_color(payload.line_color, DEFAULT_INTERIOR_LINE_COLOR) if payload.line_color else _normalize_hex_color(getattr(group, "line_color", None), DEFAULT_INTERIOR_LINE_COLOR),
        ui_order=next_order,
        structural_part_formula_ids=structural_part_formula_ids,
        dependent_interior_instance_ids=[str(row).strip() for row in list(payload.dependent_interior_instance_ids or []) if str(row).strip()],
        controller_box_snapshot=controller_box_snapshot,
        param_values=param_values,
        param_meta=param_meta,
        status="draft",
    )
    session.add(item)
    await session.flush()
    design = await _load_design(session, design.id)
    target = next(instance for instance in design.door_instances if instance.id == item.id)
    await _refresh_design_door_instance(session, design=design, instance=target)
    await session.commit()
    design = await _load_design(session, design.id)
    target = next(instance for instance in design.door_instances if instance.id == item.id)
    return SubCategoryDesignDoorInstanceItem.model_validate({
        "id": target.id,
        "door_part_group_id": target.door_part_group_id,
        "controller_type": str(getattr(group, "controller_type", "") or "").strip() or None,
        "controller_bindings": dict(getattr(group, "controller_bindings", {}) or {}),
        "instance_code": str(target.instance_code or ""),
        "line_color": str(getattr(target, "line_color", "") or "").strip() or None,
        "ui_order": int(target.ui_order or 0),
        "structural_part_formula_ids": [int(row) for row in list(target.structural_part_formula_ids or []) if int(row) > 0],
        "dependent_interior_instance_ids": [str(row).strip() for row in list(target.dependent_interior_instance_ids or []) if str(row).strip()],
        "controller_box_snapshot": dict(target.controller_box_snapshot or {}),
        "param_values": {str(key): (None if value is None else str(value)) for key, value in dict(target.param_values or {}).items()},
        "param_meta": {str(key): dict(value or {}) for key, value in dict(target.param_meta or {}).items()},
        "part_snapshots": [dict(row or {}) for row in list(target.part_snapshots or [])],
        "viewer_boxes": [dict(row or {}) for row in list(target.viewer_boxes or [])],
        "status": str(target.status or "draft").strip() or "draft",
    })


@router.patch("/{design_uuid}/door-instances/{instance_id}", response_model=SubCategoryDesignDoorInstanceItem)
async def update_sub_category_design_door_instance(
    design_uuid: uuid.UUID,
    instance_id: uuid.UUID,
    payload: SubCategoryDesignDoorInstanceUpdate,
    session: AsyncSession = Depends(get_db_session),
) -> SubCategoryDesignDoorInstanceItem:
    if not await door_instance_tables_ready(session):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Door-instance tables are not available yet. Run database migrations first.")
    design = await _load_design(session, design_uuid)
    item = next((row for row in getattr(design, "door_instances", []) if row.id == instance_id), None)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sub-category design door instance not found.")
    item.instance_code = str(payload.instance_code or "").strip()
    item.line_color = _normalize_hex_color(payload.line_color, DEFAULT_INTERIOR_LINE_COLOR) if payload.line_color else None
    item.ui_order = int(payload.ui_order)
    item.structural_part_formula_ids = [int(row) for row in list(payload.structural_part_formula_ids or []) if int(row) > 0]
    item.dependent_interior_instance_ids = [str(row).strip() for row in list(payload.dependent_interior_instance_ids or []) if str(row).strip()]
    item.param_values = _normalize_door_param_values(payload.param_values)
    await session.flush()
    design = await _load_design(session, design.id)
    target = next(instance for instance in design.door_instances if instance.id == item.id)
    await _refresh_design_door_instance(session, design=design, instance=target)
    await session.commit()
    design = await _load_design(session, design.id)
    target = next(instance for instance in design.door_instances if instance.id == item.id)
    group = await require_accessible_door_part_group(session, admin_id=design.admin_id, group_id=target.door_part_group_id)
    return SubCategoryDesignDoorInstanceItem.model_validate({
        "id": target.id,
        "door_part_group_id": target.door_part_group_id,
        "controller_type": str(getattr(group, "controller_type", "") or "").strip() or None,
        "controller_bindings": dict(getattr(group, "controller_bindings", {}) or {}),
        "instance_code": str(target.instance_code or ""),
        "line_color": str(getattr(target, "line_color", "") or "").strip() or None,
        "ui_order": int(target.ui_order or 0),
        "structural_part_formula_ids": [int(row) for row in list(target.structural_part_formula_ids or []) if int(row) > 0],
        "dependent_interior_instance_ids": [str(row).strip() for row in list(target.dependent_interior_instance_ids or []) if str(row).strip()],
        "controller_box_snapshot": dict(target.controller_box_snapshot or {}),
        "param_values": {str(key): (None if value is None else str(value)) for key, value in dict(target.param_values or {}).items()},
        "param_meta": {str(key): dict(value or {}) for key, value in dict(target.param_meta or {}).items()},
        "part_snapshots": [dict(row or {}) for row in list(target.part_snapshots or [])],
        "viewer_boxes": [dict(row or {}) for row in list(target.viewer_boxes or [])],
        "status": str(target.status or "draft").strip() or "draft",
    })


@router.post("/{design_uuid}/door-instances/{instance_id}/duplicate", response_model=SubCategoryDesignDoorInstanceItem, status_code=status.HTTP_201_CREATED)
async def duplicate_sub_category_design_door_instance(
    design_uuid: uuid.UUID,
    instance_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> SubCategoryDesignDoorInstanceItem:
    if not await door_instance_tables_ready(session):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Door-instance tables are not available yet. Run database migrations first.")
    design = await _load_design(session, design_uuid)
    source = next((row for row in getattr(design, "door_instances", []) if row.id == instance_id), None)
    if not source:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sub-category design door instance not found.")
    group = await require_accessible_door_part_group(session, admin_id=design.admin_id, group_id=source.door_part_group_id)
    next_code, next_order, controller_box_snapshot, param_values, param_meta = await _next_door_instance_state(
        session,
        design=design,
        group_id=source.door_part_group_id,
        ui_order=max([int(row.ui_order or 0) for row in list(getattr(design, "door_instances", []) or [])], default=-1) + 1,
        instance_code=None,
        structural_part_formula_ids=list(source.structural_part_formula_ids or []),
        dependent_interior_instance_ids=list(source.dependent_interior_instance_ids or []),
        controller_box_snapshot=dict(source.controller_box_snapshot or {}),
        param_values=dict(source.param_values or {}),
    )
    item = SubCategoryDesignDoorInstance(
        design=design,
        door_part_group_id=source.door_part_group_id,
        instance_code=next_code,
        line_color=_normalize_hex_color(getattr(source, "line_color", None), DEFAULT_INTERIOR_LINE_COLOR) if getattr(source, "line_color", None) else _normalize_hex_color(getattr(group, "line_color", None), DEFAULT_INTERIOR_LINE_COLOR),
        ui_order=next_order,
        structural_part_formula_ids=[int(row) for row in list(source.structural_part_formula_ids or []) if int(row) > 0],
        dependent_interior_instance_ids=[str(row).strip() for row in list(source.dependent_interior_instance_ids or []) if str(row).strip()],
        controller_box_snapshot=controller_box_snapshot,
        param_values=param_values,
        param_meta=param_meta,
        status=str(source.status or "draft").strip() or "draft",
    )
    session.add(item)
    await session.flush()
    design = await _load_design(session, design.id)
    target = next(instance for instance in design.door_instances if instance.id == item.id)
    await _refresh_design_door_instance(session, design=design, instance=target)
    await session.commit()
    design = await _load_design(session, design.id)
    target = next(instance for instance in design.door_instances if instance.id == item.id)
    return SubCategoryDesignDoorInstanceItem.model_validate({
        "id": target.id,
        "door_part_group_id": target.door_part_group_id,
        "controller_type": str(getattr(group, "controller_type", "") or "").strip() or None,
        "controller_bindings": dict(getattr(group, "controller_bindings", {}) or {}),
        "instance_code": str(target.instance_code or ""),
        "line_color": str(getattr(target, "line_color", "") or "").strip() or None,
        "ui_order": int(target.ui_order or 0),
        "structural_part_formula_ids": [int(row) for row in list(target.structural_part_formula_ids or []) if int(row) > 0],
        "dependent_interior_instance_ids": [str(row).strip() for row in list(target.dependent_interior_instance_ids or []) if str(row).strip()],
        "controller_box_snapshot": dict(target.controller_box_snapshot or {}),
        "param_values": {str(key): (None if value is None else str(value)) for key, value in dict(target.param_values or {}).items()},
        "param_meta": {str(key): dict(value or {}) for key, value in dict(target.param_meta or {}).items()},
        "part_snapshots": [dict(row or {}) for row in list(target.part_snapshots or [])],
        "viewer_boxes": [dict(row or {}) for row in list(target.viewer_boxes or [])],
        "status": str(target.status or "draft").strip() or "draft",
    })


@router.delete("/{design_uuid}/door-instances/{instance_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_sub_category_design_door_instance(
    design_uuid: uuid.UUID,
    instance_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    if not await door_instance_tables_ready(session):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Door-instance tables are not available yet. Run database migrations first.")
    design = await _load_design(session, design_uuid)
    item = next((row for row in getattr(design, "door_instances", []) if row.id == instance_id), None)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sub-category design door instance not found.")
    await session.delete(item)
    await session.flush()
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
