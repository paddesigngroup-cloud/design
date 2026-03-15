from __future__ import annotations

import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from designkp_backend.db.dependencies import get_db_session
from designkp_backend.db.models.catalog import BaseFormula, Param
from designkp_backend.services.admin_access import require_admin_if_present

router = APIRouter(prefix="/base-formulas", tags=["base_formulas"])

FORMULA_IDENTIFIER_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
FORMULA_NUMBER_RE = re.compile(r"-?(?:\d+(?:\.\d+)?|\.\d+)")


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


def tokenize_formula_expression(expression: str) -> list[str]:
    source = (expression or "").strip()
    if not source:
        return []

    tokens: list[str] = []
    position = 0
    length = len(source)
    while position < length:
        char = source[position]
        if char.isspace():
            position += 1
            continue

        previous_token = tokens[-1] if tokens else None
        can_read_negative_number = char == "-" and (
            previous_token is None or previous_token == "(" or previous_token in {"+", "-", "*", "/"}
        )

        if char.isalpha() or char == "_":
            end = position + 1
            while end < length and (source[end].isalnum() or source[end] == "_"):
                end += 1
            tokens.append(source[position:end])
            position = end
            continue

        if char.isdigit() or char == "." or can_read_negative_number:
            end = position + (1 if can_read_negative_number else 0)
            has_digit = False
            has_dot = False
            while end < length:
                current = source[end]
                if current.isdigit():
                    has_digit = True
                    end += 1
                    continue
                if current == "." and not has_dot:
                    has_dot = True
                    end += 1
                    continue
                break
            candidate = source[position:end]
            if has_digit and FORMULA_NUMBER_RE.fullmatch(candidate):
                tokens.append(candidate)
                position = end
                continue

        if char in "()+-*/":
            tokens.append(char)
            position += 1
            continue

        if position < length:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Formula contains an invalid token near: {source[position:position + 12]!r}",
            )
    return tokens


def validate_formula_structure(expression: str) -> list[str]:
    tokens = tokenize_formula_expression(expression)
    if not tokens:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Formula expression is empty.")

    errors: list[str] = []
    depth = 0
    expecting_operand = True
    previous_token: str | None = None

    for token in tokens:
        is_identifier = bool(FORMULA_IDENTIFIER_RE.fullmatch(token))
        is_number = bool(FORMULA_NUMBER_RE.fullmatch(token))

        if expecting_operand:
            if token == "(":
                depth += 1
            elif is_identifier or is_number:
                expecting_operand = False
            elif token == ")":
                errors.append("Parentheses are unbalanced.")
                break
            else:
                errors.append("Formula cannot start with an operator.")
                break
        else:
            if token in {"+", "-", "*", "/"}:
                expecting_operand = True
            elif token == ")":
                if previous_token == "(":
                    errors.append("Formula contains empty parentheses.")
                    break
                depth -= 1
                if depth < 0:
                    errors.append("Parentheses are unbalanced.")
                    break
            elif token == "(":
                errors.append("Formula contains invalid token order.")
                break
            else:
                errors.append("Formula contains invalid token order.")
                break

        previous_token = token

    if not errors and expecting_operand:
        errors.append("Formula cannot end with an operator.")
    if not errors and depth != 0:
        errors.append("Parentheses are unbalanced.")
    return errors


def extract_formula_param_codes(expression: str) -> set[str]:
    return {token for token in tokenize_formula_expression(expression) if FORMULA_IDENTIFIER_RE.fullmatch(token)}


async def _known_param_codes(session: AsyncSession, admin_id: uuid.UUID | None) -> set[str]:
    stmt = select(Param.param_code)
    if admin_id is None:
        stmt = stmt.where(Param.admin_id.is_(None))
    else:
        stmt = stmt.where(or_(Param.admin_id.is_(None), Param.admin_id == admin_id))
    rows = await session.scalars(stmt)
    return {str(value or "").strip() for value in rows if str(value or "").strip()}


async def _validate_formula_tokens(session: AsyncSession, admin_id: uuid.UUID | None, expression: str) -> None:
    structure_errors = validate_formula_structure(expression)
    if structure_errors:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=structure_errors[0])

    tokens = extract_formula_param_codes(expression)
    known_codes = await _known_param_codes(session, admin_id)
    missing = sorted(token for token in tokens if token not in known_codes)
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown param codes in formula: {', '.join(missing)}",
        )


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
