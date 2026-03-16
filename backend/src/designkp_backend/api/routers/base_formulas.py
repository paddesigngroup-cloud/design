from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from designkp_backend.api.formula_validation import validate_expression_identifiers
from designkp_backend.db.dependencies import get_db_session
from designkp_backend.db.models.catalog import BaseFormula
from designkp_backend.services.admin_access import require_admin_if_present

router = APIRouter(prefix="/base-formulas", tags=["base_formulas"])


class BaseFormulaItem(BaseModel):
    id: uuid.UUID
    admin_id: uuid.UUID | None
    fo_id: int
    param_formula: str
    formula: str
    code: str
    title: str
    sort_order: int
    is_system: bool

    model_config = {"from_attributes": True}


class BaseFormulaCreate(BaseModel):
    admin_id: uuid.UUID | None = None
    fo_id: int | None = Field(default=None, ge=1)
    param_formula: str = Field(min_length=1, max_length=64)
    formula: str = Field(min_length=1, max_length=2048)
    sort_order: int | None = Field(default=None, ge=0)
    is_system: bool = False


class BaseFormulaUpdate(BaseModel):
    admin_id: uuid.UUID | None = None
    fo_id: int = Field(ge=1)
    param_formula: str = Field(min_length=1, max_length=64)
    formula: str = Field(min_length=1, max_length=2048)
    sort_order: int = Field(ge=0)
    is_system: bool


def _to_response(item: BaseFormula) -> BaseFormulaItem:
    return BaseFormulaItem.model_validate(item)


async def _validate_formula_tokens(session: AsyncSession, admin_id: uuid.UUID | None, expression: str) -> None:
    await validate_expression_identifiers(session, admin_id, expression, allow_param_codes=True, allow_base_formula_codes=False)


async def _next_fo_id(session: AsyncSession) -> int:
    max_id = await session.scalar(select(func.max(BaseFormula.fo_id)))
    return int(max_id or 0) + 1


@router.get("", response_model=list[BaseFormulaItem])
async def list_base_formulas(
    admin_id: uuid.UUID | None = Query(default=None),
    session: AsyncSession = Depends(get_db_session),
) -> list[BaseFormulaItem]:
    await require_admin_if_present(session, admin_id)
    stmt = (
        select(BaseFormula)
        .where(or_(BaseFormula.admin_id.is_(None), BaseFormula.admin_id == admin_id))
        .order_by(BaseFormula.sort_order.asc(), BaseFormula.fo_id.asc())
    )
    items = (await session.scalars(stmt)).all()
    return [_to_response(item) for item in items]


@router.post("", response_model=BaseFormulaItem, status_code=status.HTTP_201_CREATED)
async def create_base_formula(payload: BaseFormulaCreate, session: AsyncSession = Depends(get_db_session)) -> BaseFormulaItem:
    await require_admin_if_present(session, payload.admin_id)
    normalized_formula = payload.formula.strip()
    await _validate_formula_tokens(session, payload.admin_id, normalized_formula)
    next_id = payload.fo_id or await _next_fo_id(session)
    sort_order = payload.sort_order if payload.sort_order is not None else next_id
    normalized_code = payload.param_formula.strip()
    item = BaseFormula(
        admin_id=payload.admin_id,
        fo_id=next_id,
        param_formula=normalized_code,
        formula=normalized_formula,
        code=normalized_code,
        title=normalized_code,
        sort_order=sort_order,
        is_system=payload.is_system,
    )
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return _to_response(item)


@router.patch("/{formula_uuid}", response_model=BaseFormulaItem)
async def update_base_formula(
    formula_uuid: uuid.UUID,
    payload: BaseFormulaUpdate,
    session: AsyncSession = Depends(get_db_session),
) -> BaseFormulaItem:
    item = await session.get(BaseFormula, formula_uuid)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Base formula not found.")
    await require_admin_if_present(session, payload.admin_id)
    normalized_formula = payload.formula.strip()
    await _validate_formula_tokens(session, payload.admin_id, normalized_formula)
    normalized_code = payload.param_formula.strip()

    item.admin_id = payload.admin_id
    item.fo_id = payload.fo_id
    item.param_formula = normalized_code
    item.formula = normalized_formula
    item.code = normalized_code
    item.title = normalized_code
    item.sort_order = payload.sort_order
    item.is_system = payload.is_system

    await session.commit()
    await session.refresh(item)
    return _to_response(item)


@router.delete("/{formula_uuid}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_base_formula(formula_uuid: uuid.UUID, session: AsyncSession = Depends(get_db_session)) -> Response:
    item = await session.get(BaseFormula, formula_uuid)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Base formula not found.")

    await session.delete(item)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
