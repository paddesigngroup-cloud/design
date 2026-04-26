from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from designkp_backend.api.formula_validation import validate_expression_identifiers
from designkp_backend.db.dependencies import get_db_session
from designkp_backend.db.models.catalog import PartFormula, PartModel, PartServiceType
from designkp_backend.services.admin_access import require_admin_if_present

router = APIRouter(prefix="/part-formulas", tags=["part_formulas"])

FORMULA_FIELDS = (
    "formula_l",
    "formula_w",
    "formula_width",
    "formula_depth",
    "formula_height",
    "formula_cx",
    "formula_cy",
    "formula_cz",
)


class PartFormulaItem(BaseModel):
    id: uuid.UUID
    admin_id: uuid.UUID | None
    part_formula_id: int
    part_kind_id: int
    part_model_id: uuid.UUID
    part_model_title: str
    part_sub_kind_id: int
    part_code: str
    part_title: str
    formula_l: str
    formula_w: str
    formula_width: str
    formula_depth: str
    formula_height: str
    formula_cx: str
    formula_cy: str
    formula_cz: str
    lw_frame_mapping: dict[str, str]
    part_model_side_services: list[dict[str, object]]
    door_dependent: bool
    code: str
    title: str
    sort_order: int
    is_system: bool

    model_config = {"from_attributes": True}


class PartFormulaCreate(BaseModel):
    admin_id: uuid.UUID | None = None
    part_formula_id: int | None = Field(default=None, ge=1)
    part_kind_id: int = Field(ge=1)
    part_model_id: uuid.UUID
    part_sub_kind_id: int = Field(ge=1)
    part_code: str = Field(min_length=1, max_length=64)
    part_title: str = Field(min_length=1, max_length=255)
    formula_l: str = Field(min_length=1, max_length=2048)
    formula_w: str = Field(min_length=1, max_length=2048)
    formula_width: str = Field(min_length=1, max_length=2048)
    formula_depth: str = Field(min_length=1, max_length=2048)
    formula_height: str = Field(min_length=1, max_length=2048)
    formula_cx: str = Field(min_length=1, max_length=2048)
    formula_cy: str = Field(min_length=1, max_length=2048)
    formula_cz: str = Field(min_length=1, max_length=2048)
    lw_frame_mapping: dict[str, str] | None = None
    part_model_side_services: list[dict[str, object]] | None = None
    door_dependent: bool = False
    sort_order: int | None = Field(default=None, ge=0)
    is_system: bool = False


class PartFormulaUpdate(BaseModel):
    admin_id: uuid.UUID | None = None
    part_formula_id: int = Field(ge=1)
    part_kind_id: int = Field(ge=1)
    part_model_id: uuid.UUID
    part_sub_kind_id: int = Field(ge=1)
    part_code: str = Field(min_length=1, max_length=64)
    part_title: str = Field(min_length=1, max_length=255)
    formula_l: str = Field(min_length=1, max_length=2048)
    formula_w: str = Field(min_length=1, max_length=2048)
    formula_width: str = Field(min_length=1, max_length=2048)
    formula_depth: str = Field(min_length=1, max_length=2048)
    formula_height: str = Field(min_length=1, max_length=2048)
    formula_cx: str = Field(min_length=1, max_length=2048)
    formula_cy: str = Field(min_length=1, max_length=2048)
    formula_cz: str = Field(min_length=1, max_length=2048)
    lw_frame_mapping: dict[str, str] | None = None
    part_model_side_services: list[dict[str, object]] | None = None
    door_dependent: bool = False
    sort_order: int = Field(ge=0)
    is_system: bool


DEFAULT_LW_FRAME_MAPPING = {
    "l_axis": "horizontal",
    "w_axis": "vertical",
}


def _normalize_lw_frame_mapping(payload_value: dict[str, str] | None) -> dict[str, str]:
    value = dict(payload_value or {})
    l_axis = str(value.get("l_axis") or DEFAULT_LW_FRAME_MAPPING["l_axis"]).strip().lower()
    w_axis = str(value.get("w_axis") or DEFAULT_LW_FRAME_MAPPING["w_axis"]).strip().lower()
    allowed = {"horizontal", "vertical"}
    if l_axis not in allowed or w_axis not in allowed or l_axis == w_axis:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="L/W frame mapping must use opposite horizontal/vertical axes.",
        )
    return {
        "l_axis": l_axis,
        "w_axis": w_axis,
    }


async def _normalize_part_model_side_services(
    session: AsyncSession,
    *,
    admin_id: uuid.UUID | None,
    part_model: PartModel,
    payload_rows: list[dict[str, object]] | None,
) -> list[dict[str, object]]:
    rows = payload_rows or []
    normalized: list[dict[str, object]] = []
    seen_indexes: set[int] = set()
    for row in rows:
        side_index = int(row.get("side_index") or 0)
        if side_index < 0 or side_index >= int(part_model.side_count):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Side index {side_index} is out of range for part model side count {part_model.side_count}.",
            )
        if side_index in seen_indexes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Each part model side can only have one default service.",
            )
        raw_service_type_id = str(row.get("service_type_id") or row.get("part_service_type_id") or "").strip()
        if not raw_service_type_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Each side service mapping must include a service type id.",
            )
        try:
            service_type_id = uuid.UUID(raw_service_type_id)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Service type id is not a valid UUID.",
            ) from exc
        service_type = await session.scalar(
            select(PartServiceType).where(
                PartServiceType.id == service_type_id,
                or_(PartServiceType.admin_id.is_(None), PartServiceType.admin_id == admin_id),
            )
        )
        if service_type is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown service type for this owner scope: {service_type_id}",
            )
        normalized.append({
            "side_index": side_index,
            "service_type_id": str(service_type.id),
        })
        seen_indexes.add(side_index)
    normalized.sort(key=lambda entry: int(entry["side_index"]))
    return normalized


def _to_response(item: PartFormula) -> PartFormulaItem:
    return PartFormulaItem.model_validate({
        "id": item.id,
        "admin_id": item.admin_id,
        "part_formula_id": item.part_formula_id,
        "part_kind_id": item.part_kind_id,
        "part_model_id": item.part_model_id,
        "part_model_title": str(item.part_model.title or "").strip(),
        "part_sub_kind_id": item.part_sub_kind_id,
        "part_code": item.part_code,
        "part_title": item.part_title,
        "formula_l": item.formula_l,
        "formula_w": item.formula_w,
        "formula_width": item.formula_width,
        "formula_depth": item.formula_depth,
        "formula_height": item.formula_height,
        "formula_cx": item.formula_cx,
        "formula_cy": item.formula_cy,
        "formula_cz": item.formula_cz,
        "lw_frame_mapping": _normalize_lw_frame_mapping(item.lw_frame_mapping),
        "part_model_side_services": [
            {
                "side_index": int(entry.get("side_index", 0)),
                "service_type_id": str(entry.get("service_type_id") or ""),
            }
            for entry in sorted(item.part_model_side_services or [], key=lambda row: int(row.get("side_index", 0)))
        ],
        "door_dependent": item.door_dependent,
        "code": item.code,
        "title": item.title,
        "sort_order": item.sort_order,
        "is_system": item.is_system,
    })


async def _next_part_formula_id(session: AsyncSession) -> int:
    max_id = await session.scalar(select(func.max(PartFormula.part_formula_id)))
    return int(max_id or 0) + 1


async def _validate_part_formula_expressions(
    session: AsyncSession,
    admin_id: uuid.UUID | None,
    payload: PartFormulaCreate | PartFormulaUpdate,
) -> None:
    for field_name in FORMULA_FIELDS:
        expression = str(getattr(payload, field_name) or "").strip()
        await validate_expression_identifiers(
            session,
            admin_id,
            expression,
            allow_param_codes=True,
            allow_base_formula_codes=True,
        )


async def _require_visible_part_model(
    session: AsyncSession,
    *,
    admin_id: uuid.UUID | None,
    part_model_id: uuid.UUID,
) -> PartModel:
    stmt = select(PartModel).where(
        PartModel.id == part_model_id,
        or_(PartModel.admin_id.is_(None), PartModel.admin_id == admin_id),
    )
    item = await session.scalar(stmt)
    if item is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Part model is not valid for this owner scope.")
    return item


@router.get("", response_model=list[PartFormulaItem])
async def list_part_formulas(
    admin_id: uuid.UUID | None = Query(default=None),
    session: AsyncSession = Depends(get_db_session),
) -> list[PartFormulaItem]:
    await require_admin_if_present(session, admin_id)
    stmt = (
        select(PartFormula)
        .options(selectinload(PartFormula.part_model))
        .where(or_(PartFormula.admin_id.is_(None), PartFormula.admin_id == admin_id))
        .order_by(PartFormula.sort_order.asc(), PartFormula.part_formula_id.asc())
    )
    items = (await session.scalars(stmt)).all()
    return [_to_response(item) for item in items]


@router.post("", response_model=PartFormulaItem, status_code=status.HTTP_201_CREATED)
async def create_part_formula(payload: PartFormulaCreate, session: AsyncSession = Depends(get_db_session)) -> PartFormulaItem:
    await require_admin_if_present(session, payload.admin_id)
    await _validate_part_formula_expressions(session, payload.admin_id, payload)
    part_model = await _require_visible_part_model(session, admin_id=payload.admin_id, part_model_id=payload.part_model_id)
    lw_frame_mapping = _normalize_lw_frame_mapping(payload.lw_frame_mapping)
    part_model_side_services = await _normalize_part_model_side_services(
        session,
        admin_id=payload.admin_id,
        part_model=part_model,
        payload_rows=payload.part_model_side_services,
    )
    next_id = payload.part_formula_id or await _next_part_formula_id(session)
    sort_order = payload.sort_order if payload.sort_order is not None else next_id
    item = PartFormula(
        admin_id=payload.admin_id,
        part_formula_id=next_id,
        part_kind_id=payload.part_kind_id,
        part_model_id=payload.part_model_id,
        part_sub_kind_id=payload.part_sub_kind_id,
        part_code=payload.part_code.strip(),
        part_title=payload.part_title.strip(),
        formula_l=payload.formula_l.strip(),
        formula_w=payload.formula_w.strip(),
        formula_width=payload.formula_width.strip(),
        formula_depth=payload.formula_depth.strip(),
        formula_height=payload.formula_height.strip(),
        formula_cx=payload.formula_cx.strip(),
        formula_cy=payload.formula_cy.strip(),
        formula_cz=payload.formula_cz.strip(),
        lw_frame_mapping=lw_frame_mapping,
        part_model_side_services=part_model_side_services,
        door_dependent=payload.door_dependent,
        code=payload.part_code.strip(),
        title=payload.part_title.strip(),
        sort_order=sort_order,
        is_system=payload.is_system,
    )
    session.add(item)
    await session.commit()
    saved = await session.scalar(select(PartFormula).options(selectinload(PartFormula.part_model)).where(PartFormula.id == item.id))
    return _to_response(saved)


@router.patch("/{part_formula_uuid}", response_model=PartFormulaItem)
async def update_part_formula(
    part_formula_uuid: uuid.UUID,
    payload: PartFormulaUpdate,
    session: AsyncSession = Depends(get_db_session),
) -> PartFormulaItem:
    item = await session.get(PartFormula, part_formula_uuid)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Part formula not found.")
    await require_admin_if_present(session, payload.admin_id)
    await _validate_part_formula_expressions(session, payload.admin_id, payload)
    part_model = await _require_visible_part_model(session, admin_id=payload.admin_id, part_model_id=payload.part_model_id)
    lw_frame_mapping = _normalize_lw_frame_mapping(payload.lw_frame_mapping)
    part_model_side_services = await _normalize_part_model_side_services(
        session,
        admin_id=payload.admin_id,
        part_model=part_model,
        payload_rows=payload.part_model_side_services,
    )

    item.admin_id = payload.admin_id
    item.part_formula_id = payload.part_formula_id
    item.part_kind_id = payload.part_kind_id
    item.part_model_id = payload.part_model_id
    item.part_sub_kind_id = payload.part_sub_kind_id
    item.part_code = payload.part_code.strip()
    item.part_title = payload.part_title.strip()
    item.formula_l = payload.formula_l.strip()
    item.formula_w = payload.formula_w.strip()
    item.formula_width = payload.formula_width.strip()
    item.formula_depth = payload.formula_depth.strip()
    item.formula_height = payload.formula_height.strip()
    item.formula_cx = payload.formula_cx.strip()
    item.formula_cy = payload.formula_cy.strip()
    item.formula_cz = payload.formula_cz.strip()
    item.lw_frame_mapping = lw_frame_mapping
    item.part_model_side_services = part_model_side_services
    item.door_dependent = payload.door_dependent
    item.code = payload.part_code.strip()
    item.title = payload.part_title.strip()
    item.sort_order = payload.sort_order
    item.is_system = payload.is_system

    await session.commit()
    saved = await session.scalar(select(PartFormula).options(selectinload(PartFormula.part_model)).where(PartFormula.id == item.id))
    return _to_response(saved)


@router.delete("/{part_formula_uuid}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_part_formula(part_formula_uuid: uuid.UUID, session: AsyncSession = Depends(get_db_session)) -> Response:
    item = await session.get(PartFormula, part_formula_uuid)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Part formula not found.")

    await session.delete(item)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
