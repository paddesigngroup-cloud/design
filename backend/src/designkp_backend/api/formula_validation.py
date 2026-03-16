from __future__ import annotations

import re
import uuid

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from designkp_backend.db.models.catalog import BaseFormula, Param


FORMULA_IDENTIFIER_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
FORMULA_NUMBER_RE = re.compile(r"-?(?:\d+(?:\.\d+)?|\.\d+)")


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


def extract_formula_identifiers(expression: str) -> set[str]:
    return {token for token in tokenize_formula_expression(expression) if FORMULA_IDENTIFIER_RE.fullmatch(token)}


async def known_param_codes(session: AsyncSession, admin_id: uuid.UUID | None) -> set[str]:
    stmt = select(Param.param_code)
    if admin_id is None:
        stmt = stmt.where(Param.admin_id.is_(None))
    else:
        stmt = stmt.where(or_(Param.admin_id.is_(None), Param.admin_id == admin_id))
    rows = await session.scalars(stmt)
    return {str(value or "").strip() for value in rows if str(value or "").strip()}


async def known_base_formula_codes(session: AsyncSession, admin_id: uuid.UUID | None) -> set[str]:
    stmt = select(BaseFormula.param_formula)
    if admin_id is None:
        stmt = stmt.where(BaseFormula.admin_id.is_(None))
    else:
        stmt = stmt.where(or_(BaseFormula.admin_id.is_(None), BaseFormula.admin_id == admin_id))
    rows = await session.scalars(stmt)
    return {str(value or "").strip() for value in rows if str(value or "").strip()}


async def validate_expression_identifiers(
    session: AsyncSession,
    admin_id: uuid.UUID | None,
    expression: str,
    *,
    allow_param_codes: bool = True,
    allow_base_formula_codes: bool = False,
) -> None:
    structure_errors = validate_formula_structure(expression)
    if structure_errors:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=structure_errors[0])

    known_codes: set[str] = set()
    if allow_param_codes:
        known_codes |= await known_param_codes(session, admin_id)
    if allow_base_formula_codes:
        known_codes |= await known_base_formula_codes(session, admin_id)

    identifiers = extract_formula_identifiers(expression)
    missing = sorted(token for token in identifiers if token not in known_codes)
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown codes in formula: {', '.join(missing)}",
        )
