from __future__ import annotations

import ast
import hashlib
import json
import uuid
from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from designkp_backend.db.models.catalog import (
    BaseFormula,
    InternalPartGroup,
    InternalPartGroupParamDefault,
    Param,
    ParamGroup,
    PartFormula,
    SubCategory,
    SubCategoryDesign,
    SubCategoryDesignInteriorInstance,
    SubCategoryDesignPart,
    SubCategoryDesignPartSnapshot,
    SubCategoryParamDefault,
)
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


@dataclass(slots=True)
class ResolvedInteriorInstanceSnapshot:
    instance_id: uuid.UUID | None
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


@dataclass(slots=True)
class DesignExecutionContext:
    session: AsyncSession
    admin_id: uuid.UUID | None
    sub_category: SubCategory
    sub_category_raw_params: dict[str, str | None]
    sub_category_numeric_params: dict[str, float]
    sub_category_display_values: dict[str, str | None]
    sub_category_display_meta: dict[str, dict[str, object]]
    param_codes: set[str]
    auto_param_codes: set[str]
    base_formula_map: dict[str, str]
    base_formula_order: list[str]
    part_formulas_by_id: dict[int, PartFormula]
    internal_groups_by_id: dict[uuid.UUID, InternalPartGroup]
    internal_group_param_codes: dict[uuid.UUID, set[str]]
    internal_group_display_values: dict[uuid.UUID, dict[str, str | None]]
    internal_group_display_meta: dict[uuid.UUID, dict[str, dict[str, object]]]
    parsed_expression_cache: dict[str, ast.Expression]
    expression_name_cache: dict[str, set[str]]
    source_state: dict[str, object]


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


def extract_expression_names(expression: str) -> set[str]:
    return extract_expression_names_cached(expression)


def _parse_expression_cached(
    expression: str,
    *,
    cache: dict[str, ast.Expression] | None = None,
) -> ast.Expression:
    normalized = str(expression or "").strip()
    store = cache if cache is not None else {}
    cached = store.get(normalized)
    if cached is not None:
        return cached
    parsed = ast.parse(normalized, mode="eval")
    if cache is not None:
        cache[normalized] = parsed
    return parsed


def extract_expression_names_cached(
    expression: str,
    *,
    cache: dict[str, set[str]] | None = None,
    parsed_cache: dict[str, ast.Expression] | None = None,
) -> set[str]:
    normalized = str(expression or "").strip()
    store = cache if cache is not None else {}
    cached = store.get(normalized)
    if cached is not None:
        return set(cached)
    try:
        parsed = _parse_expression_cached(normalized, cache=parsed_cache)
    except Exception:  # noqa: BLE001
        return set()
    names: set[str] = set()
    for node in ast.walk(parsed):
        if isinstance(node, ast.Name):
            names.add(str(node.id))
    if cache is not None:
        cache[normalized] = set(names)
    return names


def evaluate_formula_expression(
    expression: str,
    values: dict[str, float],
    *,
    parsed_cache: dict[str, ast.Expression] | None = None,
) -> float:
    try:
        parsed = _parse_expression_cached(str(expression or "").strip(), cache=parsed_cache)
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
    stmt = select(SubCategory).where(
        and_(
            SubCategory.id == sub_category_id,
            SubCategory.deleted_at.is_(None),
        )
    )
    if admin_id is not None:
        stmt = stmt.where(or_(SubCategory.admin_id.is_(None), SubCategory.admin_id == admin_id))
    item = await session.scalar(stmt)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sub-category not found for this admin scope.")
    await sync_defaults_for_sub_categories(session, [item])
    return item


async def interior_instance_tables_ready(session: AsyncSession) -> bool:
    result = await session.execute(
        select(
            func.to_regclass("sub_category_design_interior_instances"),
            func.to_regclass("order_design_interior_instances"),
        )
    )
    subcat_table, order_table = result.one()
    return bool(subcat_table) and bool(order_table)


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
    formulas = await list_accessible_base_formulas(session, admin_id=admin_id)
    context = DesignExecutionContext(
        session=session,
        admin_id=admin_id,
        sub_category=SubCategory(),  # type: ignore[call-arg]
        sub_category_raw_params={},
        sub_category_numeric_params={},
        sub_category_display_values={},
        sub_category_display_meta={},
        param_codes=set(),
        auto_param_codes=set(),
        base_formula_map={
            str(item.param_formula).strip(): str(item.formula or "")
            for item in formulas
            if str(item.param_formula or "").strip()
        },
        base_formula_order=[
            str(item.param_formula).strip()
            for item in formulas
            if str(item.param_formula or "").strip()
        ],
        part_formulas_by_id={},
        internal_groups_by_id={},
        internal_group_param_codes={},
        internal_group_display_values={},
        internal_group_display_meta={},
        parsed_expression_cache={},
        expression_name_cache={},
        source_state={},
    )
    return resolve_base_formula_values_with_context(context, params=params)


def resolve_base_formula_values_with_context(
    context: DesignExecutionContext,
    *,
    params: dict[str, float],
) -> dict[str, float]:
    resolved: dict[str, float] = {}
    pending = {
        code: context.base_formula_map[code]
        for code in context.base_formula_order
        if code in context.base_formula_map
    }
    max_passes = max(1, len(pending) * 2)
    for _ in range(max_passes):
        if not pending:
            break
        progressed = False
        for code, expression in list(pending.items()):
            try:
                resolved[code] = evaluate_formula_expression(
                    expression,
                    {**params, **resolved},
                    parsed_cache=context.parsed_expression_cache,
                )
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


async def list_accessible_params(session: AsyncSession, *, admin_id: uuid.UUID | None) -> list[Param]:
    stmt = select(Param)
    if admin_id is not None:
        stmt = stmt.where(or_(Param.admin_id.is_(None), Param.admin_id == admin_id))
    return (
        await session.scalars(stmt.order_by(Param.sort_order.asc(), Param.param_id.asc()))
    ).all()


async def list_accessible_base_formulas(session: AsyncSession, *, admin_id: uuid.UUID | None) -> list[BaseFormula]:
    stmt = select(BaseFormula)
    if admin_id is not None:
        stmt = stmt.where(or_(BaseFormula.admin_id.is_(None), BaseFormula.admin_id == admin_id))
    return (
        await session.scalars(stmt.order_by(BaseFormula.sort_order.asc(), BaseFormula.fo_id.asc()))
    ).all()


async def get_auto_param_codes(session: AsyncSession, *, admin_id: uuid.UUID | None) -> set[str]:
    params = await list_accessible_params(session, admin_id=admin_id)
    return {
        str(item.param_code).strip()
        for item in params
        if str(item.interior_value_mode or "").strip().lower() == "auto" and str(item.param_code or "").strip()
    }


def _compute_boxes_bounds(boxes: list[dict[str, object]]) -> dict[str, float] | None:
    if not boxes:
        return None
    min_x = float("inf")
    max_x = float("-inf")
    min_y = float("inf")
    max_y = float("-inf")
    min_z = float("inf")
    max_z = float("-inf")
    for box in boxes:
        width = max(0.0, float(box.get("width") or 0))
        depth = max(0.0, float(box.get("depth") or 0))
        height = max(0.0, float(box.get("height") or 0))
        cx = float(box.get("cx") or 0)
        cy = float(box.get("cy") or 0)
        cz = float(box.get("cz") or 0)
        min_x = min(min_x, cx - (width * 0.5))
        max_x = max(max_x, cx + (width * 0.5))
        min_y = min(min_y, cy - (depth * 0.5))
        max_y = max(max_y, cy + (depth * 0.5))
        min_z = min(min_z, cz - (height * 0.5))
        max_z = max(max_z, cz + (height * 0.5))
    if not all(map(lambda item: item not in {float("inf"), float("-inf")}, [min_x, max_x, min_y, max_y, min_z, max_z])):
        return None
    return {
        "min_x": _round_number(min_x),
        "max_x": _round_number(max_x),
        "min_y": _round_number(min_y),
        "max_y": _round_number(max_y),
        "min_z": _round_number(min_z),
        "max_z": _round_number(max_z),
        "width": _round_number(max_x - min_x),
        "depth": _round_number(max_y - min_y),
        "height": _round_number(max_z - min_z),
        "cx": _round_number((min_x + max_x) * 0.5),
        "cy": _round_number((min_y + max_y) * 0.5),
        "cz": _round_number((min_z + max_z) * 0.5),
    }


def derive_interior_box_snapshot(viewer_boxes: list[dict[str, object]]) -> dict[str, object]:
    bounds = _compute_boxes_bounds(viewer_boxes) or {
        "min_x": 0.0,
        "max_x": 0.0,
        "min_y": 0.0,
        "max_y": 0.0,
        "min_z": 0.0,
        "max_z": 0.0,
        "width": 0.0,
        "depth": 0.0,
        "height": 0.0,
        "cx": 0.0,
        "cy": 0.0,
        "cz": 0.0,
    }
    return {key: _round_number(value) for key, value in bounds.items()}


def _normalize_raw_param_values(values: dict[str, object] | None) -> dict[str, str | None]:
    return {
        str(key): (None if value is None else str(value))
        for key, value in dict(values or {}).items()
        if str(key or "").strip()
    }


def _normalize_param_meta(meta: dict[str, dict[str, object]] | None) -> dict[str, dict[str, object]]:
    return {
        str(key): dict(value or {})
        for key, value in dict(meta or {}).items()
        if str(key or "").strip()
    }


def _merge_param_value_layers(*layers: dict[str, str | None]) -> dict[str, str | None]:
    merged: dict[str, str | None] = {}
    for layer in layers:
        for key, value in dict(layer or {}).items():
            code = str(key or "").strip()
            if code:
                merged[code] = value
    return merged


def strip_inherited_param_values(
    *,
    inherited_values: dict[str, str | None],
    param_values: dict[str, object] | None,
) -> dict[str, str | None]:
    stripped: dict[str, str | None] = {}
    for code, value in _normalize_raw_param_values(param_values).items():
        if code in inherited_values and value == inherited_values.get(code):
            continue
        stripped[code] = value
    return stripped


def build_source_state_signature(payload: dict[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


async def build_sub_category_param_display_snapshot(
    session: AsyncSession,
    *,
    sub_category: SubCategory,
    codes: set[str] | None = None,
    context: DesignExecutionContext | None = None,
) -> tuple[dict[str, str | None], dict[str, dict[str, object]]]:
    if context is not None:
        filter_codes = {str(item).strip() for item in (codes or set()) if str(item).strip()} if codes else None
        values = {
            code: value
            for code, value in context.sub_category_display_values.items()
            if filter_codes is None or code in filter_codes
        }
        meta = {
            code: dict(value or {})
            for code, value in context.sub_category_display_meta.items()
            if filter_codes is None or code in filter_codes
        }
        return values, meta
    rows = (
        await session.execute(
            select(SubCategoryParamDefault, Param.param_code, Param.param_title_fa, Param.param_id, Param.ui_order, ParamGroup)
            .join(Param, Param.param_id == SubCategoryParamDefault.param_id)
            .join(ParamGroup, ParamGroup.param_group_id == Param.param_group_id)
            .where(SubCategoryParamDefault.sub_category_id == sub_category.id)
            .order_by(ParamGroup.ui_order.asc(), Param.ui_order.asc(), Param.param_id.asc())
        )
    ).all()
    values: dict[str, str | None] = {}
    meta: dict[str, dict[str, object]] = {}
    filter_codes = {str(item).strip() for item in (codes or set()) if str(item).strip()} if codes else None
    for default_row, param_code, param_title_fa, param_id, param_ui_order, group in rows:
        code = str(param_code or "").strip()
        if not code or (filter_codes is not None and code not in filter_codes):
            continue
        values[code] = default_row.default_value
        meta[code] = {
            "label": str(default_row.display_title or param_title_fa or code).strip() or code,
            "description_text": str(default_row.description_text or "").strip() or None,
            "input_mode": default_row.input_mode if str(default_row.input_mode or "") == "binary" else "value",
            "binary_off_label": str(default_row.binary_off_label or "0").strip() or "0",
            "binary_on_label": str(default_row.binary_on_label or "1").strip() or "1",
            "group_id": int(group.param_group_id or 0),
            "group_title": str(group.org_param_group_title or group.title or group.param_group_code or "").strip() or None,
            "group_ui_order": int(group.ui_order or 0),
            "group_show_in_order_attrs": bool(group.show_in_order_attrs),
            "param_id": int(param_id or 0),
            "param_ui_order": int(param_ui_order or 0),
        }
    return values, meta


async def build_internal_group_param_display_snapshot(
    session: AsyncSession,
    *,
    internal_group: InternalPartGroup,
    codes: set[str] | None = None,
    context: DesignExecutionContext | None = None,
) -> tuple[dict[str, str | None], dict[str, dict[str, object]]]:
    if context is not None:
        filter_codes = {str(item).strip() for item in (codes or set()) if str(item).strip()} if codes else None
        values = {
            code: value
            for code, value in context.internal_group_display_values.get(internal_group.id, {}).items()
            if filter_codes is None or code in filter_codes
        }
        return values, {}
    rows = (
        await session.execute(
            select(
                InternalPartGroupParamDefault,
                Param.param_code,
                Param.param_title_fa,
                Param.param_id,
                Param.ui_order,
                ParamGroup,
            )
            .join(Param, Param.param_id == InternalPartGroupParamDefault.param_id)
            .join(ParamGroup, ParamGroup.param_group_id == Param.param_group_id)
            .where(InternalPartGroupParamDefault.internal_part_group_id == internal_group.id)
            .order_by(ParamGroup.ui_order.asc(), Param.ui_order.asc(), Param.param_id.asc())
        )
    ).all()
    values: dict[str, str | None] = {}
    filter_codes = {str(item).strip() for item in (codes or set()) if str(item).strip()} if codes else None
    for default_row, param_code, param_title_fa, param_id, param_ui_order, group in rows:
        code = str(param_code or "").strip()
        if not code or (filter_codes is not None and code not in filter_codes):
            continue
        values[code] = default_row.default_value
    return values, {}


def merge_subcategory_and_internal_group_defaults(
    *,
    base_values: dict[str, str | None],
    group_param_codes: set[str],
    group_default_values: dict[str, str | None],
    instance_values: dict[str, str | None] | None = None,
) -> tuple[dict[str, str | None], dict[str, str | None]]:
    inherited_group_values = _merge_param_value_layers(
        {code: base_values.get(code) for code in group_param_codes if code in base_values},
        {code: value for code, value in group_default_values.items() if code in group_param_codes},
    )
    effective_values = _merge_param_value_layers(
        base_values,
        {code: value for code, value in group_default_values.items() if code in group_param_codes},
        _normalize_raw_param_values(instance_values),
    )
    return inherited_group_values, effective_values


async def require_accessible_internal_part_group(
    session: AsyncSession,
    *,
    admin_id: uuid.UUID | None,
    group_id: uuid.UUID,
) -> InternalPartGroup:
    stmt = (
        select(InternalPartGroup)
        .options(
            selectinload(InternalPartGroup.parts),
            selectinload(InternalPartGroup.param_groups),
        )
        .where(InternalPartGroup.id == group_id)
    )
    if admin_id is not None:
        stmt = stmt.where(or_(InternalPartGroup.admin_id.is_(None), InternalPartGroup.admin_id == admin_id))
    item = await session.scalar(stmt)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Internal part group not found for this admin scope.")
    return item


async def collect_internal_group_selected_param_codes(
    session: AsyncSession,
    *,
    admin_id: uuid.UUID | None,
    group: InternalPartGroup,
) -> set[str]:
    selected_param_group_ids = {
        int(item.param_group_id)
        for item in list(group.__dict__.get("param_groups") or [])
        if bool(item.enabled) and int(item.param_group_id or 0) > 0
    }
    if not selected_param_group_ids:
        return set()
    stmt = select(Param).where(Param.param_group_id.in_(sorted(selected_param_group_ids)))
    if admin_id is not None:
        stmt = stmt.where(or_(Param.admin_id.is_(None), Param.admin_id == admin_id))
    params = (await session.scalars(stmt.order_by(Param.ui_order.asc(), Param.param_id.asc()))).all()
    return {
        str(item.param_code).strip()
        for item in params
        if str(item.param_code or "").strip()
    }


async def collect_internal_group_param_codes(
    session: AsyncSession,
    *,
    admin_id: uuid.UUID | None,
    group: InternalPartGroup,
    context: DesignExecutionContext | None = None,
) -> set[str]:
    if context is not None:
        return set(context.internal_group_param_codes.get(group.id, set()))
    return await collect_internal_group_selected_param_codes(
        session,
        admin_id=admin_id,
        group=group,
    )


async def _load_internal_groups_for_context(
    session: AsyncSession,
    *,
    admin_id: uuid.UUID | None,
    group_ids: set[uuid.UUID],
) -> dict[uuid.UUID, InternalPartGroup]:
    if not group_ids:
        return {}
    stmt = (
        select(InternalPartGroup)
        .options(
            selectinload(InternalPartGroup.parts),
            selectinload(InternalPartGroup.param_groups),
        )
        .where(InternalPartGroup.id.in_(list(group_ids)))
    )
    if admin_id is not None:
        stmt = stmt.where(or_(InternalPartGroup.admin_id.is_(None), InternalPartGroup.admin_id == admin_id))
    groups = (await session.scalars(stmt)).all()
    groups_by_id = {item.id: item for item in groups}
    missing = [group_id for group_id in group_ids if group_id not in groups_by_id]
    if missing:
        await require_accessible_internal_part_group(session, admin_id=admin_id, group_id=missing[0])
    return groups_by_id


async def _load_internal_group_display_snapshots(
    session: AsyncSession,
    *,
    group_ids: set[uuid.UUID],
) -> tuple[dict[uuid.UUID, dict[str, str | None]], dict[uuid.UUID, dict[str, dict[str, object]]]]:
    if not group_ids:
        return {}, {}
    rows = (
        await session.execute(
            select(
                InternalPartGroupParamDefault.internal_part_group_id,
                InternalPartGroupParamDefault,
                Param.param_code,
                Param.param_title_fa,
                Param.param_id,
                Param.ui_order,
                ParamGroup,
            )
            .join(Param, Param.param_id == InternalPartGroupParamDefault.param_id)
            .join(ParamGroup, ParamGroup.param_group_id == Param.param_group_id)
            .where(InternalPartGroupParamDefault.internal_part_group_id.in_(list(group_ids)))
            .order_by(
                InternalPartGroupParamDefault.internal_part_group_id.asc(),
                ParamGroup.ui_order.asc(),
                Param.ui_order.asc(),
                Param.param_id.asc(),
            )
        )
    ).all()
    values_by_group: dict[uuid.UUID, dict[str, str | None]] = {}
    meta_by_group: dict[uuid.UUID, dict[str, dict[str, object]]] = {}
    for group_id, default_row, param_code, param_title_fa, param_id, param_ui_order, group in rows:
        code = str(param_code or "").strip()
        if not code:
            continue
        values_by_group.setdefault(group_id, {})[code] = default_row.default_value
        meta_by_group.setdefault(group_id, {})[code] = {
            "label": str(default_row.display_title or param_title_fa or code).strip() or code,
            "description_text": str(default_row.description_text or "").strip() or None,
            "icon_path": str(default_row.icon_path or "").strip() or None,
            "input_mode": default_row.input_mode if str(default_row.input_mode or "") == "binary" else "value",
            "binary_off_label": str(default_row.binary_off_label or "0").strip() or "0",
            "binary_on_label": str(default_row.binary_on_label or "1").strip() or "1",
            "binary_off_icon_path": str(default_row.binary_off_icon_path or "").strip() or None,
            "binary_on_icon_path": str(default_row.binary_on_icon_path or "").strip() or None,
            "group_id": int(group.param_group_id or 0),
            "group_title": str(group.org_param_group_title or group.title or group.param_group_code or "").strip() or None,
            "group_ui_order": int(group.ui_order or 0),
            "group_show_in_order_attrs": bool(group.show_in_order_attrs),
            "param_id": int(param_id or 0),
            "param_ui_order": int(param_ui_order or 0),
        }
    return values_by_group, meta_by_group


def _collect_internal_group_param_codes_from_context(
    *,
    group: InternalPartGroup,
    params: list[Param],
) -> set[str]:
    selected_param_group_ids = {
        int(item.param_group_id)
        for item in list(group.__dict__.get("param_groups") or [])
        if bool(item.enabled) and int(item.param_group_id or 0) > 0
    }
    if not selected_param_group_ids:
        return set()
    return {
        str(item.param_code).strip()
        for item in params
        if int(item.param_group_id or 0) in selected_param_group_ids and str(item.param_code or "").strip()
    }


async def build_design_execution_context(
    session: AsyncSession,
    *,
    admin_id: uuid.UUID | None,
    sub_category: SubCategory | None,
    part_formula_ids: set[int] | None = None,
    internal_group_ids: set[uuid.UUID] | None = None,
    include_sub_category_display: bool = False,
) -> DesignExecutionContext:
    effective_sub_category = sub_category or SubCategory(id=uuid.uuid4())  # type: ignore[call-arg]
    raw_params, numeric_params = (
        await get_sub_category_resolved_params(session, effective_sub_category)
        if sub_category is not None else
        ({}, {})
    )
    display_values: dict[str, str | None] = {}
    display_meta: dict[str, dict[str, object]] = {}
    if sub_category is not None and include_sub_category_display:
        display_values, display_meta = await build_sub_category_param_display_snapshot(
            session,
            sub_category=effective_sub_category,
        )
    params = await list_accessible_params(session, admin_id=admin_id)
    param_codes = {str(item.param_code).strip() for item in params if str(item.param_code or "").strip()}
    auto_param_codes = {
        str(item.param_code).strip()
        for item in params
        if str(item.interior_value_mode or "").strip().lower() == "auto" and str(item.param_code or "").strip()
    }
    base_formulas = await list_accessible_base_formulas(session, admin_id=admin_id)
    base_formula_map = {
        str(item.param_formula).strip(): str(item.formula or "")
        for item in base_formulas
        if str(item.param_formula or "").strip()
    }
    base_formula_order = [
        str(item.param_formula).strip()
        for item in base_formulas
        if str(item.param_formula or "").strip()
    ]
    parsed_expression_cache: dict[str, ast.Expression] = {}
    expression_name_cache: dict[str, set[str]] = {}
    groups_by_id = await _load_internal_groups_for_context(
        session,
        admin_id=admin_id,
        group_ids=set(internal_group_ids or set()),
    )
    all_formula_ids = {int(item) for item in set(part_formula_ids or set()) if int(item) > 0}
    for group in groups_by_id.values():
        for selection in list(group.__dict__.get("parts") or []):
            if bool(selection.enabled) and int(selection.part_formula_id or 0) > 0:
                all_formula_ids.add(int(selection.part_formula_id))
    part_formulas = await require_accessible_part_formulas(
        session,
        admin_id=admin_id,
        part_formula_ids=sorted(all_formula_ids),
    )
    part_formulas_by_id = {int(item.part_formula_id): item for item in part_formulas}
    group_display_values, group_display_meta = await _load_internal_group_display_snapshots(
        session,
        group_ids=set(groups_by_id.keys()),
    )
    group_param_codes = {
        group_id: _collect_internal_group_param_codes_from_context(
            group=group,
            params=params,
        )
        for group_id, group in groups_by_id.items()
    }
    source_state_payload = {
        "sub_category_id": str(getattr(sub_category, "id", "") or ""),
        "sub_category_defaults": {key: value for key, value in sorted(raw_params.items())},
        "base_formulas": {code: base_formula_map[code] for code in base_formula_order},
        "internal_groups": [
            {
                "id": str(group.id),
                "code": str(group.code or "").strip(),
                "version_id": int(getattr(group, "version_id", 0) or 0),
                "updated_at": str(getattr(group, "updated_at", "") or ""),
                "parts": [
                    {
                        "part_formula_id": int(selection.part_formula_id or 0),
                        "enabled": bool(selection.enabled),
                        "ui_order": int(selection.ui_order or 0),
                    }
                    for selection in sorted(
                        list(group.__dict__.get("parts") or []),
                        key=lambda item: (int(item.ui_order or 0), int(item.part_formula_id or 0)),
                    )
                ],
                "param_defaults": {
                    code: group_display_values.get(group.id, {}).get(code)
                    for code in sorted(group_display_values.get(group.id, {}))
                },
            }
            for group in sorted(groups_by_id.values(), key=lambda item: str(item.id))
        ],
    }
    return DesignExecutionContext(
        session=session,
        admin_id=admin_id,
        sub_category=effective_sub_category,
        sub_category_raw_params=_normalize_raw_param_values(raw_params),
        sub_category_numeric_params={str(key): float(value) for key, value in dict(numeric_params).items()},
        sub_category_display_values=display_values,
        sub_category_display_meta=display_meta,
        param_codes=param_codes,
        auto_param_codes=auto_param_codes,
        base_formula_map=base_formula_map,
        base_formula_order=base_formula_order,
        part_formulas_by_id=part_formulas_by_id,
        internal_groups_by_id=groups_by_id,
        internal_group_param_codes=group_param_codes,
        internal_group_display_values=group_display_values,
        internal_group_display_meta=group_display_meta,
        parsed_expression_cache=parsed_expression_cache,
        expression_name_cache=expression_name_cache,
        source_state={
            "payload": source_state_payload,
            "signature": build_source_state_signature(source_state_payload),
        },
    )


async def _build_legacy_execution_context(
    session: AsyncSession,
    *,
    admin_id: uuid.UUID | None,
    sub_category: SubCategory,
    internal_group: InternalPartGroup,
) -> DesignExecutionContext:
    raw_params, numeric_params = await get_sub_category_resolved_params(session, sub_category)
    group_param_codes = await collect_internal_group_param_codes(session, admin_id=admin_id, group=internal_group)
    group_values, group_meta = await build_internal_group_param_display_snapshot(
        session,
        internal_group=internal_group,
        codes=group_param_codes,
    )
    auto_param_codes = await get_auto_param_codes(session, admin_id=admin_id)
    base_formulas = await list_accessible_base_formulas(session, admin_id=admin_id)
    part_formula_ids = [
        int(item.part_formula_id)
        for item in list(internal_group.__dict__.get("parts") or [])
        if bool(item.enabled)
    ]
    formulas = await require_accessible_part_formulas(session, admin_id=admin_id, part_formula_ids=part_formula_ids)
    return DesignExecutionContext(
        session=session,
        admin_id=admin_id,
        sub_category=sub_category,
        sub_category_raw_params=_normalize_raw_param_values(raw_params),
        sub_category_numeric_params={str(key): float(value) for key, value in dict(numeric_params).items()},
        sub_category_display_values={},
        sub_category_display_meta={},
        param_codes=set(),
        auto_param_codes=set(auto_param_codes),
        base_formula_map={
            str(item.param_formula).strip(): str(item.formula or "")
            for item in base_formulas
            if str(item.param_formula or "").strip()
        },
        base_formula_order=[
            str(item.param_formula).strip()
            for item in base_formulas
            if str(item.param_formula or "").strip()
        ],
        part_formulas_by_id={int(item.part_formula_id): item for item in formulas},
        internal_groups_by_id={internal_group.id: internal_group},
        internal_group_param_codes={internal_group.id: set(group_param_codes)},
        internal_group_display_values={internal_group.id: dict(group_values)},
        internal_group_display_meta={internal_group.id: {str(key): dict(value or {}) for key, value in group_meta.items()}},
        parsed_expression_cache={},
        expression_name_cache={},
        source_state={},
    )


def resolve_part_formula_values(
    part_formula: PartFormula,
    *,
    params: dict[str, float],
    base_formulas: dict[str, float],
    context: DesignExecutionContext | None = None,
) -> dict[str, float]:
    values = {**params, **base_formulas}
    resolved: dict[str, float] = {}
    for field_name in PART_FORMULA_FIELDS:
        expression = str(getattr(part_formula, field_name) or "").strip()
        resolved[field_name] = evaluate_formula_expression(
            expression,
            values,
            parsed_cache=context.parsed_expression_cache if context is not None else None,
        )
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


def serialize_resolved_part_snapshot(item: ResolvedPartSnapshot) -> dict[str, object]:
    return {
        "part_formula_id": int(item.part_formula.part_formula_id),
        "part_kind_id": int(item.part_formula.part_kind_id),
        "part_code": item.part_formula.part_code,
        "part_title": item.part_formula.part_title,
        "enabled": bool(item.enabled),
        "ui_order": int(item.ui_order),
        "resolved_part_formulas": dict(item.resolved_part_formulas),
        "viewer_payload": dict(item.viewer_payload),
    }


async def resolve_internal_instance_preview(
    session: AsyncSession,
    *,
    admin_id: uuid.UUID | None,
    sub_category: SubCategory,
    internal_group: InternalPartGroup,
    instance_id: uuid.UUID | None,
    instance_code: str,
    ui_order: int,
    placement_z: float,
    interior_box_snapshot: dict[str, object],
    param_values: dict[str, object] | None = None,
    param_meta: dict[str, dict[str, object]] | None = None,
    base_raw_values: dict[str, str | None] | None = None,
    base_numeric_params: dict[str, float] | None = None,
    prefer_base_params: bool = False,
    context: DesignExecutionContext | None = None,
) -> ResolvedInteriorInstanceSnapshot:
    resolved_context = context or (
        await build_design_execution_context(
            session,
            admin_id=admin_id,
            sub_category=sub_category,
            internal_group_ids={internal_group.id},
            include_sub_category_display=True,
        )
        if session is not None else
        await _build_legacy_execution_context(
            session,
            admin_id=admin_id,
            sub_category=sub_category,
            internal_group=internal_group,
        )
    )
    sub_category_raw_params = dict(resolved_context.sub_category_raw_params)
    sub_category_numeric_params = dict(resolved_context.sub_category_numeric_params)
    group_param_codes = await collect_internal_group_param_codes(
        session,
        admin_id=admin_id,
        group=internal_group,
        context=resolved_context,
    )
    copied_values, _ = await build_internal_group_param_display_snapshot(
        session,
        internal_group=internal_group,
        codes=group_param_codes,
        context=resolved_context,
    )
    copied_meta_values, copied_meta = await build_sub_category_param_display_snapshot(
        session,
        sub_category=sub_category,
        codes=group_param_codes,
        context=resolved_context,
    )
    normalized_input_values = _normalize_raw_param_values(param_values)
    effective_base_raw_values = _normalize_raw_param_values(base_raw_values or sub_category_raw_params)
    inherited_group_values, effective_formula_values = merge_subcategory_and_internal_group_defaults(
        base_values=effective_base_raw_values,
        group_param_codes=group_param_codes,
        group_default_values=copied_values,
        instance_values=normalized_input_values,
    )
    persisted_values = (
        strip_inherited_param_values(
            inherited_values=inherited_group_values,
            param_values=normalized_input_values,
        )
        if prefer_base_params else
        strip_inherited_param_values(
            inherited_values=_merge_param_value_layers(copied_meta_values, copied_values),
            param_values=normalized_input_values,
        )
    )
    meta = {
        **copied_meta,
        **{
            str(key): dict(value or {})
            for key, value in _normalize_param_meta(param_meta).items()
            if str(key or "").strip() in group_param_codes
        },
    }
    auto_param_codes = set(resolved_context.auto_param_codes)
    auto_values: dict[str, float] = {}
    formula_values = dict(effective_formula_values)
    width = _round_number(_coerce_numeric(interior_box_snapshot.get("width")))
    depth = _round_number(_coerce_numeric(interior_box_snapshot.get("depth")))
    placement = _round_number(placement_z)
    if "u_i_w" in auto_param_codes:
        auto_values["u_i_w"] = width
        formula_values["u_i_w"] = str(width)
    if "u_i_d" in auto_param_codes:
        auto_values["u_i_d"] = depth
        formula_values["u_i_d"] = str(depth)
    numeric_params = dict(base_numeric_params or sub_category_numeric_params)
    numeric_params.update({str(key): _round_number(_coerce_numeric(value)) for key, value in formula_values.items()})
    numeric_params.update(auto_values)
    resolved_base_formulas = resolve_base_formula_values_with_context(resolved_context, params=numeric_params)
    selected_ids = [
        int(item.part_formula_id)
        for item in list(internal_group.__dict__.get("parts") or [])
        if bool(item.enabled)
    ]
    part_snapshots: list[dict[str, object]] = []
    viewer_boxes: list[dict[str, object]] = []
    for selection in sorted(list(internal_group.__dict__.get("parts") or []), key=lambda item: (int(item.ui_order or 0), int(item.part_formula_id or 0))):
        if not bool(selection.enabled):
            continue
        formula = resolved_context.part_formulas_by_id.get(int(selection.part_formula_id))
        if not formula:
            continue
        resolved_part_formulas = resolve_part_formula_values(
            formula,
            params=numeric_params,
            base_formulas=resolved_base_formulas,
            context=resolved_context,
        )
        viewer_payload = build_part_viewer_payload(formula, resolved_part_formulas)
        part_snapshots.append(
            {
                "part_formula_id": int(formula.part_formula_id),
                "part_kind_id": int(formula.part_kind_id),
                "part_code": formula.part_code,
                "part_title": formula.part_title,
                "enabled": True,
                "ui_order": int(selection.ui_order or 0),
                "resolved_part_formulas": resolved_part_formulas,
                "viewer_payload": viewer_payload,
            }
        )
        box = viewer_payload.get("box")
        if isinstance(box, dict):
            viewer_boxes.append(box)
    return ResolvedInteriorInstanceSnapshot(
        instance_id=instance_id,
        internal_part_group_id=internal_group.id,
        internal_part_group_code=str(internal_group.code or "").strip(),
        internal_part_group_title=str(internal_group.group_title or internal_group.title or "").strip(),
        instance_code=str(instance_code or "").strip(),
        ui_order=int(ui_order),
        placement_z=placement,
        interior_box_snapshot={str(key): value for key, value in dict(interior_box_snapshot or {}).items()},
        param_values={str(key): (None if value is None else str(value)) for key, value in persisted_values.items()},
        param_meta={str(key): dict(value or {}) for key, value in meta.items()},
        auto_params=auto_values,
        part_snapshots=part_snapshots,
        viewer_boxes=viewer_boxes,
    )


async def compose_sub_category_design_preview(
    session: AsyncSession,
    *,
    admin_id: uuid.UUID | None,
    sub_category: SubCategory,
    part_selections: list[dict[str, object]],
    interior_instances: list[SubCategoryDesignInteriorInstance] | None = None,
) -> tuple[dict[str, str | None], dict[str, float], list[ResolvedPartSnapshot], list[ResolvedInteriorInstanceSnapshot]]:
    selected_ids = [int(item["part_formula_id"]) for item in part_selections if int(item.get("part_formula_id") or 0) > 0 and bool(item.get("enabled", True))]
    context = await build_design_execution_context(
        session,
        admin_id=admin_id,
        sub_category=sub_category,
        part_formula_ids=set(selected_ids),
        internal_group_ids={item.internal_part_group_id for item in list(interior_instances or [])},
    )
    raw_params = dict(context.sub_category_raw_params)
    numeric_params = dict(context.sub_category_numeric_params)
    resolved_base_formulas = resolve_base_formula_values_with_context(context, params=numeric_params)

    snapshots: list[ResolvedPartSnapshot] = []
    for selection in sorted(part_selections, key=lambda item: (int(item.get("ui_order") or 0), int(item.get("part_formula_id") or 0))):
        formula_id = int(selection.get("part_formula_id") or 0)
        if not formula_id or not bool(selection.get("enabled", True)):
            continue
        formula = context.part_formulas_by_id.get(formula_id)
        if not formula:
            continue
        resolved_part_formulas = resolve_part_formula_values(
            formula,
            params=numeric_params,
            base_formulas=resolved_base_formulas,
            context=context,
        )
        snapshots.append(
            ResolvedPartSnapshot(
                part_formula=formula,
                ui_order=int(selection.get("ui_order") or 0),
                enabled=True,
                resolved_part_formulas=resolved_part_formulas,
                viewer_payload=build_part_viewer_payload(formula, resolved_part_formulas),
            )
        )
    base_boxes = [item.viewer_payload["box"] for item in snapshots if isinstance(item.viewer_payload.get("box"), dict)]
    interior_box_snapshot = derive_interior_box_snapshot(base_boxes)
    resolved_interior: list[ResolvedInteriorInstanceSnapshot] = []
    for instance in sorted(list(interior_instances or []), key=lambda item: (int(item.ui_order or 0), str(item.instance_code or ""))):
        internal_group = context.internal_groups_by_id.get(instance.internal_part_group_id)
        if internal_group is None:
            internal_group = await require_accessible_internal_part_group(
                session,
                admin_id=admin_id,
                group_id=instance.internal_part_group_id,
            )
        resolved_interior.append(
            await resolve_internal_instance_preview(
                session,
                admin_id=admin_id,
                sub_category=sub_category,
                internal_group=internal_group,
                instance_id=instance.id,
                instance_code=str(instance.instance_code or ""),
                ui_order=int(instance.ui_order or 0),
                placement_z=float(instance.placement_z or 0),
                interior_box_snapshot=dict(instance.interior_box_snapshot or {}) or dict(interior_box_snapshot),
                param_values=dict(instance.param_values or {}),
                param_meta={str(key): dict(value or {}) for key, value in dict(instance.param_meta or {}).items()},
                context=context,
            )
        )
    return raw_params, resolved_base_formulas, snapshots, resolved_interior


async def rebuild_design_snapshots(session: AsyncSession, design: SubCategoryDesign) -> None:
    sub_category = await session.get(SubCategory, design.sub_category_id)
    if not sub_category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sub-category not found for this design.")
    schema_ready = await interior_instance_tables_ready(session)
    interior_instances = list(design.__dict__.get("interior_instances") or []) if schema_ready else []

    part_selections = [
        {
            "part_formula_id": int(part.part_formula_id),
            "enabled": bool(part.enabled),
            "ui_order": int(part.ui_order),
        }
        for part in design.parts
    ]
    raw_params, resolved_base_formulas, snapshots, resolved_interior = await compose_sub_category_design_preview(
        session,
        admin_id=design.admin_id,
        sub_category=sub_category,
        part_selections=part_selections,
        interior_instances=interior_instances,
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

    interior_by_id = {item.instance_id: item for item in resolved_interior if item.instance_id is not None}
    for instance in interior_instances:
        computed = interior_by_id.get(instance.id)
        if not computed:
            instance.part_snapshots = []
            instance.viewer_boxes = []
            continue
        instance.interior_box_snapshot = computed.interior_box_snapshot
        instance.param_values = computed.param_values
        instance.param_meta = computed.param_meta
        instance.part_snapshots = computed.part_snapshots
        instance.viewer_boxes = computed.viewer_boxes
