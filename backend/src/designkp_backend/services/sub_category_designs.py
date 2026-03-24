from __future__ import annotations

import ast
import uuid
from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from designkp_backend.db.models.catalog import BaseFormula, Param, PartFormula, SubCategory, SubCategoryDesign, SubCategoryDesignPart, SubCategoryDesignPartSnapshot, SubCategoryParamDefault
from designkp_backend.services.sub_category_defaults import sync_defaults_for_sub_categories


PART_FORMULA_FIELDS = (
    "formula_l",
    "formula_w",
    "formula_width",
    "formula_depth",
    "formula_height",
    "formula_cx",
    "formula_cy",
    "formula_cz",
)


@dataclass(slots=True)
class ResolvedPartSnapshot:
    part_formula: PartFormula
    ui_order: int
    enabled: bool
    resolved_part_formulas: dict[str, float]
    viewer_payload: dict[str, object]


def _round_number(value: float | int) -> float:
    return round(float(value), 6)


def _coerce_numeric(value: object) -> float:
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value or "").strip()
    if not text:
        return 0.0
    normalized = (
        text.replace("−", "-")
        .replace("﹣", "-")
        .replace("－", "-")
        .replace("٫", ".")
        .replace("،", ".")
        .translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))
    )
    try:
        return float(normalized)
    except ValueError:
        return 0.0


def _evaluate_ast(node: ast.AST, values: dict[str, float]) -> float:
    if isinstance(node, ast.Expression):
        return _evaluate_ast(node.body, values)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        operand = _evaluate_ast(node.operand, values)
        return operand if isinstance(node.op, ast.UAdd) else -operand
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
        left = _evaluate_ast(node.left, values)
        right = _evaluate_ast(node.right, values)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if right == 0:
            raise ZeroDivisionError("division by zero")
        return left / right
    if isinstance(node, ast.Name):
        if node.id not in values:
            raise NameError(node.id)
        return float(values[node.id])
    raise ValueError("unsupported-expression")


def evaluate_formula_expression(expression: str, values: dict[str, float]) -> float:
    try:
        parsed = ast.parse(str(expression or "").strip(), mode="eval")
        return _round_number(_evaluate_ast(parsed, values))
    except NameError:
        raise
    except ZeroDivisionError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Formula division by zero in expression: {expression}") from exc
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Formula evaluation failed for expression: {expression}") from exc


async def require_accessible_sub_category(
    session: AsyncSession,
    *,
    admin_id: uuid.UUID | None,
    sub_category_id: uuid.UUID,
) -> SubCategory:
    stmt = select(SubCategory).where(SubCategory.id == sub_category_id)
    if admin_id is not None:
        stmt = stmt.where(or_(SubCategory.admin_id.is_(None), SubCategory.admin_id == admin_id))
    item = await session.scalar(stmt)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sub-category not found for this admin scope.")
    await sync_defaults_for_sub_categories(session, [item])
    return item


async def require_accessible_part_formulas(
    session: AsyncSession,
    *,
    admin_id: uuid.UUID | None,
    part_formula_ids: list[int],
) -> list[PartFormula]:
    if not part_formula_ids:
        return []
    stmt = select(PartFormula).where(PartFormula.part_formula_id.in_(part_formula_ids))
    if admin_id is not None:
        stmt = stmt.where(or_(PartFormula.admin_id.is_(None), PartFormula.admin_id == admin_id))
    items = (await session.scalars(
        stmt.order_by(PartFormula.sort_order.asc(), PartFormula.part_formula_id.asc())
    )).all()
    found_ids = {int(item.part_formula_id) for item in items}
    missing = [str(item) for item in part_formula_ids if int(item) not in found_ids]
    if missing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown part formulas for this admin scope: {', '.join(missing)}")
    return items


async def get_sub_category_resolved_params(
    session: AsyncSession,
    sub_category: SubCategory,
) -> tuple[dict[str, str | None], dict[str, float]]:
    defaults = (
        await session.execute(
            select(SubCategoryParamDefault, Param.param_code)
            .join(Param, Param.param_id == SubCategoryParamDefault.param_id)
            .where(SubCategoryParamDefault.sub_category_id == sub_category.id)
        )
    ).all()
    raw_values: dict[str, str | None] = {}
    numeric_values: dict[str, float] = {}
    for row in defaults:
        default_row, param_code = row
        raw = default_row.default_value
        raw_values[str(param_code)] = raw
        numeric_values[str(param_code)] = _round_number(_coerce_numeric(raw))
    return raw_values, numeric_values


async def resolve_base_formula_values(session: AsyncSession, *, admin_id: uuid.UUID | None, params: dict[str, float]) -> dict[str, float]:
    stmt = select(BaseFormula)
    if admin_id is not None:
        stmt = stmt.where(or_(BaseFormula.admin_id.is_(None), BaseFormula.admin_id == admin_id))
    formulas = (await session.scalars(
        stmt.order_by(BaseFormula.sort_order.asc(), BaseFormula.fo_id.asc())
    )).all()
    resolved: dict[str, float] = {}
    pending = {str(item.param_formula): str(item.formula) for item in formulas}
    max_passes = max(1, len(pending) * 2)
    for _ in range(max_passes):
        if not pending:
            break
        progressed = False
        for code, expression in list(pending.items()):
            try:
                resolved[code] = evaluate_formula_expression(expression, {**params, **resolved})
            except NameError:
                continue
            pending.pop(code, None)
            progressed = True
        if not progressed:
            break
    if pending:
        unresolved = next(iter(pending))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Could not resolve base formula dependencies near: {unresolved}")
    return resolved


def resolve_part_formula_values(
    part_formula: PartFormula,
    *,
    params: dict[str, float],
    base_formulas: dict[str, float],
) -> dict[str, float]:
    values = {**params, **base_formulas}
    resolved: dict[str, float] = {}
    for field_name in PART_FORMULA_FIELDS:
        expression = str(getattr(part_formula, field_name) or "").strip()
        resolved[field_name] = evaluate_formula_expression(expression, values)
    return resolved


def build_part_viewer_payload(part_formula: PartFormula, resolved_part_formulas: dict[str, float]) -> dict[str, object]:
    width = _round_number(resolved_part_formulas.get("formula_width", 0))
    depth = _round_number(resolved_part_formulas.get("formula_depth", 0))
    height = _round_number(resolved_part_formulas.get("formula_height", 0))
    cx = _round_number(resolved_part_formulas.get("formula_cx", 0))
    cy = _round_number(resolved_part_formulas.get("formula_cy", 0))
    cz = _round_number(resolved_part_formulas.get("formula_cz", 0))
    return {
        "part_formula_id": int(part_formula.part_formula_id),
        "part_kind_id": int(part_formula.part_kind_id),
        "part_code": part_formula.part_code,
        "part_title": part_formula.part_title,
        "width": width,
        "depth": depth,
        "height": height,
        "cx": cx,
        "cy": cy,
        "cz": cz,
        "box": {
            "width": width,
            "depth": depth,
            "height": height,
            "cx": cx,
            "cy": cy,
            "cz": cz,
        },
    }


async def compose_sub_category_design_preview(
    session: AsyncSession,
    *,
    admin_id: uuid.UUID | None,
    sub_category: SubCategory,
    part_selections: list[dict[str, object]],
) -> tuple[dict[str, str | None], dict[str, float], list[ResolvedPartSnapshot]]:
    raw_params, numeric_params = await get_sub_category_resolved_params(session, sub_category)
    resolved_base_formulas = await resolve_base_formula_values(session, admin_id=admin_id, params=numeric_params)

    selected_ids = [int(item["part_formula_id"]) for item in part_selections if int(item.get("part_formula_id") or 0) > 0 and bool(item.get("enabled", True))]
    formulas = await require_accessible_part_formulas(session, admin_id=admin_id, part_formula_ids=selected_ids)
    formula_by_id = {int(item.part_formula_id): item for item in formulas}

    snapshots: list[ResolvedPartSnapshot] = []
    for selection in sorted(part_selections, key=lambda item: (int(item.get("ui_order") or 0), int(item.get("part_formula_id") or 0))):
        formula_id = int(selection.get("part_formula_id") or 0)
        if not formula_id or not bool(selection.get("enabled", True)):
            continue
        formula = formula_by_id.get(formula_id)
        if not formula:
            continue
        resolved_part_formulas = resolve_part_formula_values(formula, params=numeric_params, base_formulas=resolved_base_formulas)
        snapshots.append(
            ResolvedPartSnapshot(
                part_formula=formula,
                ui_order=int(selection.get("ui_order") or 0),
                enabled=True,
                resolved_part_formulas=resolved_part_formulas,
                viewer_payload=build_part_viewer_payload(formula, resolved_part_formulas),
            )
        )
    return raw_params, resolved_base_formulas, snapshots


async def rebuild_design_snapshots(session: AsyncSession, design: SubCategoryDesign) -> None:
    sub_category = await session.get(SubCategory, design.sub_category_id)
    if not sub_category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sub-category not found for this design.")

    part_selections = [
        {
            "part_formula_id": int(part.part_formula_id),
            "enabled": bool(part.enabled),
            "ui_order": int(part.ui_order),
        }
        for part in design.parts
    ]
    raw_params, resolved_base_formulas, snapshots = await compose_sub_category_design_preview(
        session,
        admin_id=design.admin_id,
        sub_category=sub_category,
        part_selections=part_selections,
    )

    snapshots_by_formula_id = {int(item.part_formula.part_formula_id): item for item in snapshots}
    for part in design.parts:
        snapshot = next((item for item in part.snapshots), None)
        if not part.enabled:
            if snapshot:
                await session.delete(snapshot)
            continue
        computed = snapshots_by_formula_id.get(int(part.part_formula_id))
        if not computed:
            if snapshot:
                await session.delete(snapshot)
            continue
        if snapshot is None:
            snapshot = SubCategoryDesignPartSnapshot(design_part=part)
            session.add(snapshot)
        snapshot.resolved_params = raw_params
        snapshot.resolved_base_formulas = resolved_base_formulas
        snapshot.resolved_part_formulas = computed.resolved_part_formulas
        snapshot.width = computed.viewer_payload["width"]
        snapshot.depth = computed.viewer_payload["depth"]
        snapshot.height = computed.viewer_payload["height"]
        snapshot.cx = computed.viewer_payload["cx"]
        snapshot.cy = computed.viewer_payload["cy"]
        snapshot.cz = computed.viewer_payload["cz"]
        snapshot.viewer_payload = computed.viewer_payload
