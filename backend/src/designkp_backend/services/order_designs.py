from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from designkp_backend.db.models.account import Order, OrderDesign
from designkp_backend.db.models.catalog import Param, ParamGroup, SubCategory, SubCategoryDesign, SubCategoryDesignPart, SubCategoryParamDefault
from designkp_backend.services.admin_access import require_admin
from designkp_backend.services.admin_storage import admin_icon_exists, normalize_icon_file_name
from designkp_backend.services.sub_category_designs import (
    _coerce_numeric,
    _round_number,
    build_part_viewer_payload,
    get_sub_category_resolved_params,
    require_accessible_part_formulas,
    require_accessible_sub_category,
    resolve_base_formula_values,
    resolve_part_formula_values,
)


async def require_accessible_order(session: AsyncSession, *, order_id: uuid.UUID) -> Order:
    item = await session.scalar(
        select(Order)
        .where(and_(Order.id == order_id, Order.deleted_at.is_(None)))
    )
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")
    await require_admin(session, item.admin_id)
    return item


async def require_accessible_sub_category_design(
    session: AsyncSession,
    *,
    admin_id: uuid.UUID,
    design_id: uuid.UUID,
) -> SubCategoryDesign:
    item = await session.scalar(
        select(SubCategoryDesign)
        .options(selectinload(SubCategoryDesign.parts).selectinload(SubCategoryDesignPart.snapshots))
        .where(
            and_(
                SubCategoryDesign.id == design_id,
                or_(SubCategoryDesign.admin_id.is_(None), SubCategoryDesign.admin_id == admin_id),
            )
        )
    )
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sub-category design not found for this order.")
    return item


def normalize_order_attr_value(raw_value: object, *, input_mode: str) -> str | None:
    if raw_value is None:
        return None
    if input_mode == "binary":
        if isinstance(raw_value, bool):
            return "1" if raw_value else "0"
        text = str(raw_value).strip()
        return "1" if text in {"1", "true", "True", "on"} else "0"
    return str(raw_value).strip() or None


async def _build_display_attr_snapshot(
    session: AsyncSession,
    *,
    sub_category: SubCategory,
    order_admin_id: uuid.UUID,
    override_values: dict[str, object] | None = None,
) -> tuple[dict[str, str | None], dict[str, dict[str, object]]]:
    rows = (
        await session.execute(
            select(SubCategoryParamDefault, Param.param_code, Param.param_title_fa, Param.param_id, Param.ui_order, ParamGroup)
            .join(Param, Param.param_id == SubCategoryParamDefault.param_id)
            .join(ParamGroup, ParamGroup.param_group_id == Param.param_group_id)
            .where(
                and_(
                    SubCategoryParamDefault.sub_category_id == sub_category.id,
                    ParamGroup.show_in_order_attrs.is_(True),
                )
            )
            .order_by(ParamGroup.ui_order.asc(), Param.ui_order.asc(), Param.param_id.asc())
        )
    ).all()
    values: dict[str, str | None] = {}
    meta: dict[str, dict[str, object]] = {}
    overrides = override_values or {}
    for default_row, param_code, param_title_fa, param_id, param_ui_order, group in rows:
        code = str(param_code or "").strip()
        if not code:
            continue
        input_mode = default_row.input_mode if default_row.input_mode in {"value", "binary"} else "value"
        normalized_value = normalize_order_attr_value(
            overrides.get(code, default_row.default_value),
            input_mode=input_mode,
        )
        icon_path = normalize_icon_file_name(default_row.icon_path)
        binary_off_icon_path = normalize_icon_file_name(default_row.binary_off_icon_path)
        binary_on_icon_path = normalize_icon_file_name(default_row.binary_on_icon_path)
        if icon_path and not admin_icon_exists(order_admin_id, icon_path):
            icon_path = ""
        if binary_off_icon_path and not admin_icon_exists(order_admin_id, binary_off_icon_path):
            binary_off_icon_path = ""
        if binary_on_icon_path and not admin_icon_exists(order_admin_id, binary_on_icon_path):
            binary_on_icon_path = ""
        values[code] = normalized_value
        meta[code] = {
            "label": str(default_row.display_title or param_title_fa or code).strip() or code,
            "description_text": str(default_row.description_text or "").strip() or None,
            "icon_path": icon_path or None,
            "input_mode": input_mode,
            "binary_off_label": str(default_row.binary_off_label or "0").strip() or "0",
            "binary_on_label": str(default_row.binary_on_label or "1").strip() or "1",
            "binary_off_icon_path": binary_off_icon_path or None,
            "binary_on_icon_path": binary_on_icon_path or None,
            "group_id": int(group.param_group_id or 0),
            "group_title": str(group.org_param_group_title or group.title or group.param_group_code or "").strip() or None,
            "group_icon_path": normalize_icon_file_name(group.param_group_icon_path) or None,
            "group_ui_order": int(group.ui_order or 0),
            "param_id": int(param_id or 0),
            "param_ui_order": int(param_ui_order or 0),
        }
    return values, meta


async def build_order_design_snapshot(
    session: AsyncSession,
    *,
    order: Order,
    source_design: SubCategoryDesign,
    override_attr_values: dict[str, object] | None = None,
) -> dict[str, object]:
    sub_category = await require_accessible_sub_category(
        session,
        admin_id=order.admin_id,
        sub_category_id=source_design.sub_category_id,
    )
    raw_params, numeric_params = await get_sub_category_resolved_params(session, sub_category)
    order_attr_values, order_attr_meta = await _build_display_attr_snapshot(
        session,
        sub_category=sub_category,
        order_admin_id=order.admin_id,
        override_values=override_attr_values,
    )
    for code, value in order_attr_values.items():
        raw_params[code] = value
        numeric_params[code] = _round_number(_coerce_numeric(value))

    resolved_base_formulas = await resolve_base_formula_values(session, admin_id=order.admin_id, params=numeric_params)
    part_selections = [
        {
            "part_formula_id": int(part.part_formula_id),
            "enabled": bool(part.enabled),
            "ui_order": int(part.ui_order),
        }
        for part in sorted(source_design.parts, key=lambda row: (int(row.ui_order), int(row.part_formula_id)))
        if part.enabled
    ]
    formula_ids = [int(item["part_formula_id"]) for item in part_selections]
    formulas = await require_accessible_part_formulas(session, admin_id=order.admin_id, part_formula_ids=formula_ids)
    formulas_by_id = {int(item.part_formula_id): item for item in formulas}

    part_snapshots: list[dict[str, object]] = []
    viewer_boxes: list[dict[str, object]] = []
    for selection in part_selections:
        formula = formulas_by_id.get(int(selection["part_formula_id"]))
        if not formula:
            continue
        resolved_part_formulas = resolve_part_formula_values(
            formula,
            params=numeric_params,
            base_formulas=resolved_base_formulas,
        )
        viewer_payload = build_part_viewer_payload(formula, resolved_part_formulas)
        box = viewer_payload.get("box")
        if isinstance(box, dict):
            viewer_boxes.append(box)
        part_snapshots.append(
            {
                "part_formula_id": int(formula.part_formula_id),
                "part_kind_id": int(formula.part_kind_id),
                "part_code": formula.part_code,
                "part_title": formula.part_title,
                "enabled": True,
                "ui_order": int(selection["ui_order"]),
                "resolved_part_formulas": resolved_part_formulas,
                "viewer_payload": viewer_payload,
            }
        )

    return {
        "sub_category_id": sub_category.id,
        "design_code": str(source_design.code or "").strip(),
        "design_title": str(source_design.design_title or "").strip(),
        "order_attr_values": order_attr_values,
        "order_attr_meta": order_attr_meta,
        "part_snapshots": part_snapshots,
        "viewer_boxes": viewer_boxes,
    }


async def next_order_design_instance_code(
    session: AsyncSession,
    *,
    order_id: uuid.UUID,
    design_code: str,
) -> str:
    normalized_design_code = str(design_code or "").strip() or "design"
    rows = (
        await session.scalars(
            select(OrderDesign.instance_code)
            .where(and_(OrderDesign.order_id == order_id, OrderDesign.deleted_at.is_(None)))
            .order_by(OrderDesign.instance_code.asc())
        )
    ).all()
    prefix = f"{normalized_design_code}-"
    max_seq = 0
    for value in rows:
        text = str(value or "").strip()
        if text.startswith(prefix):
            suffix = text[len(prefix) :]
            if suffix.isdigit():
                max_seq = max(max_seq, int(suffix))
    return f"{normalized_design_code}-{max_seq + 1:02d}"


async def next_order_design_sort_order(session: AsyncSession, *, order_id: uuid.UUID) -> int:
    max_order = await session.scalar(
        select(func.max(OrderDesign.sort_order)).where(and_(OrderDesign.order_id == order_id, OrderDesign.deleted_at.is_(None)))
    )
    return int(max_order or 0) + 1
