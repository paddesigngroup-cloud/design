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
from designkp_backend.db.models.catalog import Category, SubCategory, SubCategoryDesign, SubCategoryDesignInteriorInstance, SubCategoryDesignPart
from designkp_backend.services.admin_access import require_admin_if_present
from designkp_backend.services.sub_category_designs import (
    build_sub_category_param_display_snapshot,
    compose_sub_category_design_preview,
    derive_interior_box_snapshot,
    interior_instance_tables_ready,
    rebuild_design_snapshots,
    require_accessible_internal_part_group,
    require_accessible_sub_category,
    resolve_internal_instance_preview,
    serialize_resolved_part_snapshot,
)

router = APIRouter(prefix="/sub-category-designs", tags=["sub_category_designs"])


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
    instance_code: str
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
    instance_code: str
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


class SubCategoryDesignUpdate(BaseModel):
    admin_id: uuid.UUID | None = None
    sub_category_id: uuid.UUID
    design_id: int = Field(ge=1)
    design_title: str = Field(min_length=1, max_length=255)
    code: str = Field(min_length=1, max_length=64)
    sort_order: int = Field(ge=0)
    is_system: bool
    parts: list[SubCategoryDesignPartSelectionPayload] = Field(default_factory=list)


class SubCategoryDesignPreviewDraftRequest(BaseModel):
    admin_id: uuid.UUID
    sub_category_id: uuid.UUID
    parts: list[SubCategoryDesignPartSelectionPayload] = Field(default_factory=list)
    interior_instances: list["SubCategoryDesignInteriorInstanceDraftPayload"] = Field(default_factory=list)


class SubCategoryDesignInteriorInstanceDraftPayload(BaseModel):
    id: uuid.UUID | None = None
    internal_part_group_id: uuid.UUID
    instance_code: str = Field(min_length=1, max_length=64)
    ui_order: int = Field(ge=0)
    placement_z: float = 0
    interior_box_snapshot: dict[str, object] = Field(default_factory=dict)
    param_values: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
    param_meta: dict[str, dict[str, object]] = Field(default_factory=dict)


SubCategoryDesignPreviewDraftRequest.model_rebuild()


class SubCategoryDesignInteriorInstanceCreate(BaseModel):
    internal_part_group_id: uuid.UUID
    placement_z: float = 0
    ui_order: int | None = Field(default=None, ge=0)
    instance_code: str | None = Field(default=None, max_length=64)
    param_values: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class SubCategoryDesignInteriorInstanceUpdate(BaseModel):
    placement_z: float
    ui_order: int = Field(ge=0)
    instance_code: str = Field(min_length=1, max_length=64)
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
                SubCategoryDesignInteriorInstanceItem.model_validate(instance)
                for instance in sorted(item.interior_instances, key=lambda row: (int(row.ui_order), str(row.instance_code or "")))
            ]
            if include_interior else []
        ),
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
    return SubCategoryDesignPreviewResponse(
        design_id=design_id,
        sub_category_id=sub_category_id,
        design_outline_color=str(design_outline_color or "#7A4A2B").strip() or "#7A4A2B",
        resolved_params=raw_params,
        resolved_base_formulas=resolved_base_formulas,
        viewer_boxes=[item.viewer_payload["box"] for item in snapshots],
        parts=parts,
        interior_instances=[
            SubCategoryDesignInteriorInstancePreviewItem(
                id=item.instance_id,
                internal_part_group_id=item.internal_part_group_id,
                internal_part_group_code=item.internal_part_group_code,
                internal_part_group_title=item.internal_part_group_title,
                instance_code=item.instance_code,
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
    stmt = select(SubCategoryDesign).options(
        selectinload(SubCategoryDesign.parts),
        selectinload(SubCategoryDesign.sub_category).selectinload(SubCategory.category),
    )
    if include_interior:
        stmt = stmt.options(selectinload(SubCategoryDesign.interior_instances))
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
            include_interior=include_interior,
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
    raw_params, resolved_base_formulas, snapshots, interior_instances = await compose_sub_category_design_preview(
        session,
        admin_id=payload.admin_id,
        sub_category=sub_category,
        part_selections=[item.model_dump() for item in payload.parts],
        interior_instances=payload.interior_instances,
    )
    return _serialize_preview(
        design_id=None,
        sub_category_id=sub_category.id,
        design_outline_color=await _category_outline_color(session, sub_category.cat_id),
        raw_params=raw_params,
        resolved_base_formulas=resolved_base_formulas,
        snapshots=snapshots,
        interior_instances=interior_instances,
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
    sub_category = await session.get(SubCategory, item.sub_category_id)
    if not sub_category or sub_category.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sub-category not found for this design.")
    raw_params = {}
    resolved_base_formulas = {}
    parts: list[SubCategoryDesignPartPreviewItem] = []
    viewer_boxes: list[dict[str, object]] = []
    for part in sorted(item.parts, key=lambda row: (int(row.ui_order), int(row.part_formula_id))):
        snapshot = next((snap for snap in part.snapshots), None)
        if not snapshot:
            continue
        raw_params = snapshot.resolved_params or raw_params
        resolved_base_formulas = snapshot.resolved_base_formulas or resolved_base_formulas
        viewer_payload = snapshot.viewer_payload or {}
        viewer_box = viewer_payload.get("box") if isinstance(viewer_payload, dict) else None
        if isinstance(viewer_box, dict):
            viewer_boxes.append(viewer_box)
        parts.append(
            SubCategoryDesignPartPreviewItem(
                id=part.id,
                part_formula_id=int(part.part_formula_id),
                part_kind_id=int(part.part_kind_id),
                part_code=part.part_code,
                part_title=part.part_title,
                enabled=part.enabled,
                ui_order=int(part.ui_order),
                resolved_part_formulas=snapshot.resolved_part_formulas or {},
                viewer_payload=viewer_payload if isinstance(viewer_payload, dict) else {},
            )
        )
    return SubCategoryDesignPreviewResponse(
        design_id=item.id,
        sub_category_id=sub_category.id,
        design_outline_color=await _category_outline_color(session, sub_category.cat_id),
        resolved_params=raw_params,
        resolved_base_formulas=resolved_base_formulas,
        viewer_boxes=viewer_boxes + ([
            dict(box or {})
            for instance in sorted(item.interior_instances, key=lambda row: (int(row.ui_order or 0), str(row.instance_code or "")))
            for box in list(instance.viewer_boxes or [])
        ] if include_interior else []),
        parts=parts,
        interior_instances=[
            SubCategoryDesignInteriorInstancePreviewItem(
                id=instance.id,
                internal_part_group_id=instance.internal_part_group_id,
                internal_part_group_code="",
                internal_part_group_title="",
                instance_code=str(instance.instance_code or ""),
                ui_order=int(instance.ui_order or 0),
                placement_z=float(instance.placement_z or 0),
                interior_box_snapshot=dict(instance.interior_box_snapshot or {}),
                param_values={str(key): (None if value is None else str(value)) for key, value in dict(instance.param_values or {}).items()},
                param_meta={str(key): dict(value or {}) for key, value in dict(instance.param_meta or {}).items()},
                auto_params={},
                part_snapshots=[dict(row or {}) for row in list(instance.part_snapshots or [])],
                viewer_boxes=[dict(row or {}) for row in list(instance.viewer_boxes or [])],
            )
            for instance in sorted(item.interior_instances, key=lambda row: (int(row.ui_order or 0), str(row.instance_code or "")))
        ] if include_interior else [],
    )


def _normalize_interior_param_values(payload: dict[str, str | int | float | bool | None]) -> dict[str, str | None]:
    return {
        str(key): (None if value is None else str(value))
        for key, value in dict(payload or {}).items()
        if str(key or "").strip()
    }


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
    next_code = str(instance_code or "").strip() or f"{str(group.code or 'interior').strip() or 'interior'}-{next_order + 1:02d}"
    base_boxes = [item.viewer_payload["box"] for item in (await preview_sub_category_design(design.id, session)).parts if isinstance(item.viewer_payload.get("box"), dict)]
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


@router.post("/{design_uuid}/interior-instances", response_model=SubCategoryDesignInteriorInstanceItem, status_code=status.HTTP_201_CREATED)
async def create_sub_category_design_interior_instance(
    design_uuid: uuid.UUID,
    payload: SubCategoryDesignInteriorInstanceCreate,
    session: AsyncSession = Depends(get_db_session),
) -> SubCategoryDesignInteriorInstanceItem:
    if not await interior_instance_tables_ready(session):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Interior-instance tables are not available yet. Run database migrations first.")
    design = await _load_design(session, design_uuid)
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
    await rebuild_design_snapshots(session, design)
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
    item.ui_order = int(payload.ui_order)
    item.placement_z = float(payload.placement_z or 0)
    item.param_values = _normalize_interior_param_values(payload.param_values)
    await session.flush()
    design = await _load_design(session, design.id)
    await rebuild_design_snapshots(session, design)
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
    design = await _load_design(session, design.id)
    await rebuild_design_snapshots(session, design)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
