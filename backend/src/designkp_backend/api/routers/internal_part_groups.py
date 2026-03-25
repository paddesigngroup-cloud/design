from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from designkp_backend.db.dependencies import get_db_session
from designkp_backend.db.models.catalog import InternalPartGroup, InternalPartGroupItem, PartFormula, PartKind
from designkp_backend.services.admin_access import require_admin_if_present

router = APIRouter(prefix="/internal-part-groups", tags=["internal_part_groups"])


class InternalPartGroupPartSelectionPayload(BaseModel):
    part_formula_id: int = Field(ge=1)
    enabled: bool = True
    ui_order: int = Field(default=0, ge=0)


class InternalPartGroupPartItem(BaseModel):
    id: uuid.UUID
    part_formula_id: int
    part_kind_id: int
    part_code: str
    part_title: str
    enabled: bool
    ui_order: int

    model_config = {"from_attributes": True}


class InternalPartGroupItemResponse(BaseModel):
    id: uuid.UUID
    admin_id: uuid.UUID | None
    group_id: int
    group_title: str
    code: str
    title: str
    sort_order: int
    is_system: bool
    parts: list[InternalPartGroupPartItem]

    model_config = {"from_attributes": True}


class InternalPartGroupCreate(BaseModel):
    admin_id: uuid.UUID | None = None
    group_id: int | None = Field(default=None, ge=1)
    group_title: str = Field(min_length=1, max_length=255)
    code: str = Field(min_length=1, max_length=64)
    sort_order: int | None = Field(default=None, ge=0)
    is_system: bool = False
    parts: list[InternalPartGroupPartSelectionPayload] = Field(default_factory=list)


class InternalPartGroupUpdate(BaseModel):
    admin_id: uuid.UUID | None = None
    group_id: int = Field(ge=1)
    group_title: str = Field(min_length=1, max_length=255)
    code: str = Field(min_length=1, max_length=64)
    sort_order: int = Field(ge=0)
    is_system: bool
    parts: list[InternalPartGroupPartSelectionPayload] = Field(default_factory=list)


async def _next_group_id(session: AsyncSession) -> int:
    max_id = await session.scalar(select(func.max(InternalPartGroup.group_id)))
    return int(max_id or 0) + 1


async def _ensure_unique_group_code(session: AsyncSession, *, code: str, exclude_id: uuid.UUID | None = None) -> None:
    stmt = select(InternalPartGroup).where(InternalPartGroup.code == code)
    if exclude_id is not None:
        stmt = stmt.where(InternalPartGroup.id != exclude_id)
    duplicate = await session.scalar(stmt)
    if duplicate:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Internal part group code is already used.")


async def _load_group(session: AsyncSession, group_uuid: uuid.UUID) -> InternalPartGroup:
    item = await session.scalar(
        select(InternalPartGroup)
        .options(selectinload(InternalPartGroup.parts))
        .where(InternalPartGroup.id == group_uuid)
    )
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Internal part group not found.")
    return item


def _serialize_group(item: InternalPartGroup) -> InternalPartGroupItemResponse:
    return InternalPartGroupItemResponse(
        id=item.id,
        admin_id=item.admin_id,
        group_id=int(item.group_id or 0),
        group_title=item.group_title,
        code=item.code,
        title=item.title,
        sort_order=item.sort_order,
        is_system=item.is_system,
        parts=[
            InternalPartGroupPartItem.model_validate(part)
            for part in sorted(item.parts, key=lambda part: (int(part.ui_order), int(part.part_formula_id)))
        ],
    )


async def _require_accessible_internal_part_formulas(
    session: AsyncSession,
    *,
    admin_id: uuid.UUID | None,
    part_formula_ids: list[int],
) -> list[PartFormula]:
    if not part_formula_ids:
        return []
    stmt = (
        select(PartFormula)
        .join(PartKind, PartKind.part_kind_id == PartFormula.part_kind_id)
        .where(PartFormula.part_formula_id.in_(part_formula_ids))
        .where(PartKind.is_internal.is_(True))
    )
    if admin_id is not None:
        stmt = stmt.where(or_(PartFormula.admin_id.is_(None), PartFormula.admin_id == admin_id))
    items = (await session.scalars(stmt.order_by(PartFormula.sort_order.asc(), PartFormula.part_formula_id.asc()))).all()
    found_ids = {int(item.part_formula_id) for item in items}
    missing = [str(item) for item in part_formula_ids if int(item) not in found_ids]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown internal part formulas for this admin scope: {', '.join(missing)}",
        )
    return items


async def _replace_group_parts(
    session: AsyncSession,
    *,
    group: InternalPartGroup,
    parts: list[InternalPartGroupPartSelectionPayload],
) -> None:
    next_formulas = await _require_accessible_internal_part_formulas(
        session,
        admin_id=group.admin_id,
        part_formula_ids=[int(item.part_formula_id) for item in parts if item.enabled],
    )
    by_formula_id = {int(item.part_formula_id): item for item in next_formulas}
    existing_parts = list(group.__dict__.get("parts") or [])
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
            existing = InternalPartGroupItem(
                group=group,
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


@router.get("", response_model=list[InternalPartGroupItemResponse])
async def list_internal_part_groups(
    admin_id: uuid.UUID | None = Query(default=None),
    session: AsyncSession = Depends(get_db_session),
) -> list[InternalPartGroupItemResponse]:
    await require_admin_if_present(session, admin_id)
    stmt = select(InternalPartGroup).options(selectinload(InternalPartGroup.parts))
    if admin_id is None:
        stmt = stmt.where(InternalPartGroup.admin_id.is_(None))
    else:
        stmt = stmt.where(or_(InternalPartGroup.admin_id.is_(None), InternalPartGroup.admin_id == admin_id))
    stmt = stmt.order_by(
        InternalPartGroup.is_system.desc(),
        InternalPartGroup.sort_order.asc(),
        InternalPartGroup.group_id.asc(),
    )
    items = (await session.scalars(stmt)).all()
    return [_serialize_group(item) for item in items]


@router.post("", response_model=InternalPartGroupItemResponse, status_code=status.HTTP_201_CREATED)
async def create_internal_part_group(payload: InternalPartGroupCreate, session: AsyncSession = Depends(get_db_session)) -> InternalPartGroupItemResponse:
    await require_admin_if_present(session, payload.admin_id)
    next_group_id = payload.group_id or await _next_group_id(session)
    title = payload.group_title.strip()
    code = payload.code.strip()
    if not code:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Internal part group code is required.")
    await _ensure_unique_group_code(session, code=code)
    item = InternalPartGroup(
        admin_id=payload.admin_id,
        group_id=next_group_id,
        group_title=title,
        code=code,
        title=title,
        sort_order=payload.sort_order if payload.sort_order is not None else next_group_id,
        is_system=payload.is_system,
    )
    session.add(item)
    await session.flush()
    await _replace_group_parts(session, group=item, parts=payload.parts)
    await session.commit()
    item = await _load_group(session, item.id)
    return _serialize_group(item)


@router.patch("/{group_uuid}", response_model=InternalPartGroupItemResponse)
async def update_internal_part_group(
    group_uuid: uuid.UUID,
    payload: InternalPartGroupUpdate,
    session: AsyncSession = Depends(get_db_session),
) -> InternalPartGroupItemResponse:
    item = await _load_group(session, group_uuid)
    await require_admin_if_present(session, payload.admin_id)
    title = payload.group_title.strip()
    code = payload.code.strip()
    if not code:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Internal part group code is required.")
    await _ensure_unique_group_code(session, code=code, exclude_id=item.id)
    item.admin_id = payload.admin_id
    item.group_id = payload.group_id
    item.group_title = title
    item.code = code
    item.title = title
    item.sort_order = payload.sort_order
    item.is_system = payload.is_system
    await _replace_group_parts(session, group=item, parts=payload.parts)
    await session.commit()
    item = await _load_group(session, item.id)
    return _serialize_group(item)


@router.delete("/{group_uuid}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_internal_part_group(group_uuid: uuid.UUID, session: AsyncSession = Depends(get_db_session)) -> Response:
    item = await session.get(InternalPartGroup, group_uuid)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Internal part group not found.")
    await session.delete(item)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
