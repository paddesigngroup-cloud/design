from __future__ import annotations

import hashlib
import json
import uuid

from fastapi import HTTPException, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from designkp_backend.db.models.account import Order, OrderDesign, OrderDesignInteriorInstance
from designkp_backend.db.models.catalog import (
    InternalPartGroup,
    Param,
    ParamGroup,
    SubCategory,
    SubCategoryDesign,
    SubCategoryDesignInteriorInstance,
    SubCategoryDesignPart,
    SubCategoryParamDefault,
)
from designkp_backend.services.admin_access import require_admin
from designkp_backend.services.admin_storage import admin_icon_exists, normalize_icon_file_name
from designkp_backend.services.sub_category_designs import (
    _coerce_numeric,
    _round_number,
    build_sub_category_param_display_snapshot,
    build_part_viewer_payload,
    get_sub_category_resolved_params,
    interior_instance_tables_ready,
    require_accessible_internal_part_group,
    require_accessible_part_formulas,
    require_accessible_sub_category,
    resolve_internal_instance_preview,
    resolve_base_formula_values,
    resolve_part_formula_values,
)

SNAPSHOT_META_KEY = "__snapshot_state"


def strip_snapshot_state_from_meta(meta: dict[str, dict[str, object]] | None) -> dict[str, dict[str, object]]:
    return {
        str(key): dict(value or {})
        for key, value in dict(meta or {}).items()
        if str(key) != SNAPSHOT_META_KEY
    }


def build_order_design_snapshot_checksum(
    *,
    source_design: SubCategoryDesign,
    order_attr_values: dict[str, object],
    interior_instances: list[OrderDesignInteriorInstance | SubCategoryDesignInteriorInstance] | None,
) -> str:
    payload = {
        "sub_category_design_id": str(source_design.id),
        "sub_category_design_version": int(getattr(source_design, "version_id", 0) or 0),
        "sub_category_design_updated_at": str(getattr(source_design, "updated_at", "") or ""),
        "order_attr_values": {str(key): value for key, value in sorted(dict(order_attr_values or {}).items(), key=lambda row: str(row[0]))},
        "interior_instances": [
            {
                "id": str(getattr(instance, "id", "") or ""),
                "internal_part_group_id": str(getattr(instance, "internal_part_group_id", "") or ""),
                "instance_code": str(getattr(instance, "instance_code", "") or ""),
                "ui_order": int(getattr(instance, "ui_order", 0) or 0),
                "placement_z": float(getattr(instance, "placement_z", 0) or 0),
                "param_values": {
                    str(key): value
                    for key, value in sorted(dict(getattr(instance, "param_values", {}) or {}).items(), key=lambda row: str(row[0]))
                },
            }
            for instance in sorted(
                list(interior_instances or []),
                key=lambda row: (
                    int(getattr(row, "ui_order", 0) or 0),
                    str(getattr(row, "instance_code", "") or ""),
                    str(getattr(row, "id", "") or ""),
                ),
            )
        ],
    }
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def read_order_design_snapshot_checksum(meta: dict[str, object] | None) -> str:
    state = dict((meta or {}).get(SNAPSHOT_META_KEY) or {})
    return str(state.get("checksum") or "")


def with_order_design_snapshot_checksum(meta: dict[str, dict[str, object]], *, checksum: str) -> dict[str, dict[str, object]]:
    next_meta = strip_snapshot_state_from_meta(meta)
    next_meta[SNAPSHOT_META_KEY] = {"version": 1, "checksum": checksum}
    return next_meta


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
    stmt = select(SubCategoryDesign).options(
        selectinload(SubCategoryDesign.parts).selectinload(SubCategoryDesignPart.snapshots),
    )
    if await interior_instance_tables_ready(session):
        stmt = stmt.options(selectinload(SubCategoryDesign.interior_instances))
    item = await session.scalar(
        stmt
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
                )
            )
            .order_by(ParamGroup.ui_order.asc(), Param.ui_order.asc(), Param.param_id.asc())
        )
    ).all()
    values: dict[str, str | None] = {}
    meta: dict[str, dict[str, object]] = {}
    overrides = override_values or {}
    icon_exists_cache: dict[str, bool] = {}

    def _icon_exists_cached(file_name: str | None) -> bool:
        normalized = normalize_icon_file_name(file_name)
        if not normalized:
            return False
        cached = icon_exists_cache.get(normalized)
        if cached is not None:
            return cached
        exists = admin_icon_exists(order_admin_id, normalized)
        icon_exists_cache[normalized] = exists
        return exists

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
        if icon_path and not _icon_exists_cached(icon_path):
            icon_path = ""
        if binary_off_icon_path and not _icon_exists_cached(binary_off_icon_path):
            binary_off_icon_path = ""
        if binary_on_icon_path and not _icon_exists_cached(binary_on_icon_path):
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
            "group_show_in_order_attrs": bool(group.show_in_order_attrs),
            "param_id": int(param_id or 0),
            "param_ui_order": int(param_ui_order or 0),
        }
    return values, meta


async def _load_accessible_internal_groups(
    session: AsyncSession,
    *,
    admin_id: uuid.UUID,
    group_ids: set[uuid.UUID],
) -> dict[uuid.UUID, InternalPartGroup]:
    if not group_ids:
        return {}
    groups = (
        await session.scalars(
            select(InternalPartGroup).where(
                and_(
                    InternalPartGroup.id.in_(list(group_ids)),
                    or_(InternalPartGroup.admin_id.is_(None), InternalPartGroup.admin_id == admin_id),
                )
            )
        )
    ).all()
    groups_by_id = {item.id: item for item in groups}
    missing = [group_id for group_id in group_ids if group_id not in groups_by_id]
    if missing:
        # Keep current behavior (4xx for inaccessible group) while avoiding per-row queries.
        missing_group = missing[0]
        await require_accessible_internal_part_group(session, admin_id=admin_id, group_id=missing_group)
    return groups_by_id


async def build_order_design_snapshot(
    session: AsyncSession,
    *,
    order: Order,
    source_design: SubCategoryDesign,
    override_attr_values: dict[str, object] | None = None,
    interior_instances: list[OrderDesignInteriorInstance | SubCategoryDesignInteriorInstance] | None = None,
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

    resolved_interior_instances: list[dict[str, object]] = []
    schema_ready = await interior_instance_tables_ready(session)
    sorted_interior_instances = (
        sorted(list(interior_instances or []), key=lambda row: (int(row.ui_order or 0), str(row.instance_code or "")))
        if schema_ready else []
    )
    internal_groups_by_id = await _load_accessible_internal_groups(
        session,
        admin_id=order.admin_id,
        group_ids={instance.internal_part_group_id for instance in sorted_interior_instances},
    ) if sorted_interior_instances else {}
    param_meta_cache: dict[tuple[str, ...], dict[str, dict[str, object]]] = {}
    for instance in sorted_interior_instances:
        internal_group = internal_groups_by_id.get(instance.internal_part_group_id)
        if internal_group is None:
            internal_group = await require_accessible_internal_part_group(
                session,
                admin_id=order.admin_id,
                group_id=instance.internal_part_group_id,
            )
        param_values = {str(key): value for key, value in dict(instance.param_values or {}).items()}
        param_meta = {str(key): dict(value or {}) for key, value in dict(instance.param_meta or {}).items()}
        if not param_meta:
            cache_key = tuple(sorted(str(code) for code in set(param_values.keys())))
            cached_param_meta = param_meta_cache.get(cache_key)
            if cached_param_meta is not None:
                param_meta = {str(key): dict(value or {}) for key, value in cached_param_meta.items()}
            else:
                _, resolved_param_meta = await build_sub_category_param_display_snapshot(
                    session,
                    sub_category=sub_category,
                    codes=set(param_values.keys()) or None,
                )
                param_meta = {str(key): dict(value or {}) for key, value in resolved_param_meta.items()}
                param_meta_cache[cache_key] = {str(key): dict(value or {}) for key, value in param_meta.items()}
        resolved = await resolve_internal_instance_preview(
            session,
            admin_id=order.admin_id,
            sub_category=sub_category,
            internal_group=internal_group,
            instance_id=getattr(instance, "id", None),
            instance_code=str(instance.instance_code or ""),
            ui_order=int(instance.ui_order or 0),
            placement_z=float(instance.placement_z or 0),
            interior_box_snapshot=dict(instance.interior_box_snapshot or {}),
            param_values=param_values,
            param_meta=param_meta,
        )
        resolved_interior_instances.append(
            {
                "id": resolved.instance_id,
                "internal_part_group_id": resolved.internal_part_group_id,
                "internal_part_group_code": resolved.internal_part_group_code,
                "internal_part_group_title": resolved.internal_part_group_title,
                "instance_code": resolved.instance_code,
                "ui_order": resolved.ui_order,
                "placement_z": resolved.placement_z,
                "interior_box_snapshot": resolved.interior_box_snapshot,
                "param_values": resolved.param_values,
                "param_meta": resolved.param_meta,
                "auto_params": resolved.auto_params,
                "part_snapshots": resolved.part_snapshots,
                "viewer_boxes": resolved.viewer_boxes,
                "status": str(getattr(instance, "status", "draft") or "draft"),
            }
        )
        viewer_boxes.extend([dict(box or {}) for box in resolved.viewer_boxes])
        part_snapshots.extend([dict(row or {}) for row in resolved.part_snapshots])

    return {
        "sub_category_id": sub_category.id,
        "design_code": str(source_design.code or "").strip(),
        "design_title": str(source_design.design_title or "").strip(),
        "order_attr_values": order_attr_values,
        "order_attr_meta": order_attr_meta,
        "part_snapshots": part_snapshots,
        "viewer_boxes": viewer_boxes,
        "interior_instances": resolved_interior_instances,
    }


async def sync_order_design_snapshot(
    session: AsyncSession,
    *,
    item: OrderDesign,
    order: Order | None = None,
    source_design: SubCategoryDesign | None = None,
) -> bool:
    current_order = order or await require_accessible_order(session, order_id=item.order_id)
    schema_ready = await interior_instance_tables_ready(session)
    current_source_design = source_design or await require_accessible_sub_category_design(
        session,
        admin_id=current_order.admin_id,
        design_id=item.sub_category_design_id,
    )
    next_checksum = build_order_design_snapshot_checksum(
        source_design=current_source_design,
        order_attr_values=dict(item.order_attr_values or {}),
        interior_instances=list(item.interior_instances or []) if schema_ready else [],
    )
    if read_order_design_snapshot_checksum(dict(item.order_attr_meta or {})) == next_checksum:
        return False
    snapshot = await build_order_design_snapshot(
        session,
        order=current_order,
        source_design=current_source_design,
        override_attr_values=dict(item.order_attr_values or {}),
        interior_instances=list(item.interior_instances or []) if schema_ready else [],
    )
    changed = False
    if dict(item.order_attr_values or {}) != snapshot["order_attr_values"]:
        item.order_attr_values = snapshot["order_attr_values"]
        changed = True
    if strip_snapshot_state_from_meta(dict(item.order_attr_meta or {})) != snapshot["order_attr_meta"]:
        item.order_attr_meta = with_order_design_snapshot_checksum(snapshot["order_attr_meta"], checksum=next_checksum)
        changed = True
    if list(item.part_snapshots or []) != snapshot["part_snapshots"]:
        item.part_snapshots = snapshot["part_snapshots"]
        changed = True
    if list(item.viewer_boxes or []) != snapshot["viewer_boxes"]:
        item.viewer_boxes = snapshot["viewer_boxes"]
        changed = True
    if schema_ready:
        interior_by_id = {str(getattr(instance, "id", "")): instance for instance in list(item.interior_instances or [])}
        for resolved in snapshot["interior_instances"]:
            instance = interior_by_id.get(str(resolved.get("id") or ""))
            if not instance:
                continue
            if dict(instance.interior_box_snapshot or {}) != resolved["interior_box_snapshot"]:
                instance.interior_box_snapshot = resolved["interior_box_snapshot"]
                changed = True
            if dict(instance.param_values or {}) != resolved["param_values"]:
                instance.param_values = resolved["param_values"]
                changed = True
            if dict(instance.param_meta or {}) != resolved["param_meta"]:
                instance.param_meta = resolved["param_meta"]
                changed = True
            if list(instance.part_snapshots or []) != resolved["part_snapshots"]:
                instance.part_snapshots = resolved["part_snapshots"]
                changed = True
            if list(instance.viewer_boxes or []) != resolved["viewer_boxes"]:
                instance.viewer_boxes = resolved["viewer_boxes"]
                changed = True
    if item.sub_category_id != snapshot["sub_category_id"]:
        item.sub_category_id = snapshot["sub_category_id"]
        changed = True
    if str(item.design_code or "").strip() != snapshot["design_code"]:
        item.design_code = snapshot["design_code"]
        changed = True
    if read_order_design_snapshot_checksum(dict(item.order_attr_meta or {})) != next_checksum:
        item.order_attr_meta = with_order_design_snapshot_checksum(dict(item.order_attr_meta or {}), checksum=next_checksum)
        changed = True
    return changed


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
