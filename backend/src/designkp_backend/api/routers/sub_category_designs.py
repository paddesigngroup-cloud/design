from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from designkp_backend.db.dependencies import get_db_session
from designkp_backend.db.models.catalog import SubCategory, SubCategoryDesign, SubCategoryDesignPart
from designkp_backend.services.admin_access import require_admin_if_present
from designkp_backend.services.sub_category_designs import (
    compose_sub_category_design_preview,
    rebuild_design_snapshots,
    require_accessible_sub_category,
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


class SubCategoryDesignPreviewResponse(BaseModel):
    design_id: uuid.UUID | None = None
    sub_category_id: uuid.UUID
    resolved_params: dict[str, str | None]
    resolved_base_formulas: dict[str, float]
    viewer_boxes: list[dict[str, object]]
    parts: list[SubCategoryDesignPartPreviewItem]


class SubCategoryDesignItem(BaseModel):
    id: uuid.UUID
    admin_id: uuid.UUID | None
    sub_category_id: uuid.UUID
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

    model_config = {"from_attributes": True}


class SubCategoryDesignCreate(BaseModel):
    admin_id: uuid.UUID | None = None
    sub_category_id: uuid.UUID
    design_id: int | None = Field(default=None, ge=1)
    design_title: str = Field(min_length=1, max_length=255)
    sort_order: int | None = Field(default=None, ge=0)
    is_system: bool = False
    parts: list[SubCategoryDesignPartSelectionPayload] = Field(default_factory=list)


class SubCategoryDesignUpdate(BaseModel):
    admin_id: uuid.UUID | None = None
    sub_category_id: uuid.UUID
    design_id: int = Field(ge=1)
    design_title: str = Field(min_length=1, max_length=255)
    sort_order: int = Field(ge=0)
    is_system: bool
    parts: list[SubCategoryDesignPartSelectionPayload] = Field(default_factory=list)


class SubCategoryDesignPreviewDraftRequest(BaseModel):
    admin_id: uuid.UUID
    sub_category_id: uuid.UUID
    parts: list[SubCategoryDesignPartSelectionPayload] = Field(default_factory=list)


def _code_for_design(design_id: int) -> str:
    return f"sub_category_design_{design_id}"


async def _next_design_id(session: AsyncSession) -> int:
    max_id = await session.scalar(select(func.max(SubCategoryDesign.design_id)))
    return int(max_id or 0) + 1


def _serialize_design(item: SubCategoryDesign) -> SubCategoryDesignItem:
    return SubCategoryDesignItem(
        id=item.id,
        admin_id=item.admin_id,
        sub_category_id=item.sub_category_id,
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
    )


def _serialize_preview(
    *,
    design_id: uuid.UUID | None,
    sub_category_id: uuid.UUID,
    raw_params: dict[str, str | None],
    resolved_base_formulas: dict[str, float],
    snapshots: list,
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
        resolved_params=raw_params,
        resolved_base_formulas=resolved_base_formulas,
        viewer_boxes=[item.viewer_payload["box"] for item in snapshots],
        parts=parts,
    )


async def _load_design(session: AsyncSession, design_uuid: uuid.UUID) -> SubCategoryDesign:
    item = await session.scalar(
        select(SubCategoryDesign)
        .options(
            selectinload(SubCategoryDesign.parts).selectinload(SubCategoryDesignPart.snapshots),
        )
        .where(SubCategoryDesign.id == design_uuid)
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
    stmt = select(SubCategoryDesign).options(selectinload(SubCategoryDesign.parts))
    if admin_id is None:
        stmt = stmt.where(SubCategoryDesign.admin_id.is_(None))
    else:
        stmt = stmt.where(or_(SubCategoryDesign.admin_id.is_(None), SubCategoryDesign.admin_id == admin_id))
    stmt = stmt.order_by(
        SubCategoryDesign.is_system.desc(),
        SubCategoryDesign.sort_order.asc(),
        SubCategoryDesign.design_id.asc(),
    )
    if sub_cat_id is not None:
        stmt = stmt.where(SubCategoryDesign.sub_cat_id == sub_cat_id)
    items = (await session.scalars(stmt)).all()
    return [_serialize_design(item) for item in items]


@router.post("", response_model=SubCategoryDesignItem, status_code=status.HTTP_201_CREATED)
async def create_sub_category_design(payload: SubCategoryDesignCreate, session: AsyncSession = Depends(get_db_session)) -> SubCategoryDesignItem:
    await require_admin_if_present(session, payload.admin_id)
    sub_category = await require_accessible_sub_category(session, admin_id=payload.admin_id, sub_category_id=payload.sub_category_id)
    next_design_id = payload.design_id or await _next_design_id(session)
    title = payload.design_title.strip()
    item = SubCategoryDesign(
        admin_id=payload.admin_id,
        sub_category_id=sub_category.id,
        temp_id=sub_category.temp_id,
        cat_id=sub_category.cat_id,
        sub_cat_id=sub_category.sub_cat_id,
        design_id=next_design_id,
        design_title=title,
        code=_code_for_design(next_design_id),
        title=title,
        sort_order=payload.sort_order if payload.sort_order is not None else next_design_id,
        is_system=payload.is_system,
    )
    session.add(item)
    await session.flush()
    await _replace_parts(session, design=item, sub_category=sub_category, parts=payload.parts)
    await session.flush()
    item = await _load_design(session, item.id)
    await rebuild_design_snapshots(session, item)
    await session.commit()
    item = await _load_design(session, item.id)
    return _serialize_design(item)


@router.patch("/{design_uuid}", response_model=SubCategoryDesignItem)
async def update_sub_category_design(
    design_uuid: uuid.UUID,
    payload: SubCategoryDesignUpdate,
    session: AsyncSession = Depends(get_db_session),
) -> SubCategoryDesignItem:
    item = await _load_design(session, design_uuid)
    await require_admin_if_present(session, payload.admin_id)
    sub_category = await require_accessible_sub_category(session, admin_id=payload.admin_id, sub_category_id=payload.sub_category_id)
    title = payload.design_title.strip()
    item.admin_id = payload.admin_id
    item.sub_category_id = sub_category.id
    item.temp_id = sub_category.temp_id
    item.cat_id = sub_category.cat_id
    item.sub_cat_id = sub_category.sub_cat_id
    item.design_id = payload.design_id
    item.design_title = title
    item.code = _code_for_design(payload.design_id)
    item.title = title
    item.sort_order = payload.sort_order
    item.is_system = payload.is_system
    await _replace_parts(session, design=item, sub_category=sub_category, parts=payload.parts)
    await session.flush()
    item = await _load_design(session, item.id)
    await rebuild_design_snapshots(session, item)
    await session.commit()
    item = await _load_design(session, item.id)
    return _serialize_design(item)


@router.delete("/{design_uuid}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_sub_category_design(design_uuid: uuid.UUID, session: AsyncSession = Depends(get_db_session)) -> Response:
    item = await session.get(SubCategoryDesign, design_uuid)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sub-category design not found.")
    await session.delete(item)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/preview-draft", response_model=SubCategoryDesignPreviewResponse)
async def preview_sub_category_design_draft(
    payload: SubCategoryDesignPreviewDraftRequest,
    session: AsyncSession = Depends(get_db_session),
) -> SubCategoryDesignPreviewResponse:
    await require_admin_if_present(session, payload.admin_id)
    sub_category = await require_accessible_sub_category(session, admin_id=payload.admin_id, sub_category_id=payload.sub_category_id)
    raw_params, resolved_base_formulas, snapshots = await compose_sub_category_design_preview(
        session,
        admin_id=payload.admin_id,
        sub_category=sub_category,
        part_selections=[item.model_dump() for item in payload.parts],
    )
    return _serialize_preview(
        design_id=None,
        sub_category_id=sub_category.id,
        raw_params=raw_params,
        resolved_base_formulas=resolved_base_formulas,
        snapshots=snapshots,
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
    sub_category = await session.get(SubCategory, item.sub_category_id)
    if not sub_category:
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
        resolved_params=raw_params,
        resolved_base_formulas=resolved_base_formulas,
        viewer_boxes=viewer_boxes,
        parts=parts,
    )
