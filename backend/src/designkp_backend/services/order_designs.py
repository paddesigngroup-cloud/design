from __future__ import annotations

import hashlib
import json
import uuid

from fastapi import HTTPException, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from designkp_backend.db.models.account import Order, OrderDesign, OrderDesignDoorInstance, OrderDesignInteriorInstance
from designkp_backend.db.models.catalog import (
    DoorPartGroup,
    DoorPartGroupParamDefault,
    InternalPartGroup,
    Param,
    ParamGroup,
    SubCategory,
    SubCategoryDesign,
    SubCategoryDesignDoorInstance,
    SubCategoryDesignInteriorInstance,
    SubCategoryDesignPart,
    SubCategoryParamDefault,
)
from designkp_backend.services.admin_access import require_admin
from designkp_backend.services.admin_storage import admin_icon_exists, normalize_icon_file_name
from designkp_backend.services.sub_category_designs import (
    DesignExecutionContext,
    _coerce_numeric,
    _round_number,
    build_design_execution_context,
    build_sub_category_param_display_snapshot,
    build_part_viewer_payload,
    build_source_state_signature,
    door_instance_tables_ready,
    door_part_group_param_defaults_table_ready,
    interior_instance_tables_ready,
    merge_subcategory_and_internal_group_defaults,
    require_accessible_door_part_group,
    require_accessible_internal_part_group,
    require_accessible_sub_category,
    resolve_door_instance_preview,
    resolve_internal_instance_preview,
    resolve_base_formula_values_with_context,
    resolve_part_formula_values,
    strip_inherited_param_values,
    derive_interior_box_snapshot,
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
    door_instances: list[OrderDesignDoorInstance | SubCategoryDesignDoorInstance] | None = None,
    source_state: dict[str, object] | None = None,
) -> str:
    payload = {
        "sub_category_design_id": str(source_design.id),
        "sub_category_design_version": int(getattr(source_design, "version_id", 0) or 0),
        "sub_category_design_updated_at": str(getattr(source_design, "updated_at", "") or ""),
        "source_state_signature": str((source_state or {}).get("signature") or ""),
        "order_attr_values": {str(key): value for key, value in sorted(dict(order_attr_values or {}).items(), key=lambda row: str(row[0]))},
        "interior_instances": [
            {
                "id": str(getattr(instance, "id", "") or ""),
                "internal_part_group_id": str(getattr(instance, "internal_part_group_id", "") or ""),
                "instance_code": str(getattr(instance, "instance_code", "") or ""),
                "line_color": str(getattr(instance, "line_color", "") or ""),
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


def read_order_design_snapshot_state(meta: dict[str, object] | None) -> dict[str, object]:
    return dict((meta or {}).get(SNAPSHOT_META_KEY) or {})


def _normalize_snapshot_marker(
    *,
    source_design: SubCategoryDesign,
    interior_instances: list[OrderDesignInteriorInstance | SubCategoryDesignInteriorInstance] | None,
    door_instances: list[OrderDesignDoorInstance | SubCategoryDesignDoorInstance] | None = None,
) -> dict[str, object]:
    return {
        "sub_category_design_version": int(getattr(source_design, "version_id", 0) or 0),
        "sub_category_design_updated_at": str(getattr(source_design, "updated_at", "") or ""),
        "interior_instances": [
            {
                "id": str(getattr(instance, "id", "") or ""),
                "version_id": int(getattr(instance, "version_id", 0) or 0),
                "updated_at": str(getattr(instance, "updated_at", "") or ""),
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
        "door_instances": [
            {
                "id": str(getattr(instance, "id", "") or ""),
                "door_part_group_id": str(getattr(instance, "door_part_group_id", "") or ""),
                "instance_code": str(getattr(instance, "instance_code", "") or ""),
                "line_color": str(getattr(instance, "line_color", "") or ""),
                "ui_order": int(getattr(instance, "ui_order", 0) or 0),
                "structural_part_formula_ids": [int(row) for row in list(getattr(instance, "structural_part_formula_ids", []) or []) if int(row) > 0],
                "dependent_interior_instance_ids": [str(row).strip() for row in list(getattr(instance, "dependent_interior_instance_ids", []) or []) if str(row).strip()],
                "param_values": {
                    str(key): value
                    for key, value in sorted(dict(getattr(instance, "param_values", {}) or {}).items(), key=lambda row: str(row[0]))
                },
            }
            for instance in sorted(
                list(door_instances or []),
                key=lambda row: (
                    int(getattr(row, "ui_order", 0) or 0),
                    str(getattr(row, "instance_code", "") or ""),
                    str(getattr(row, "id", "") or ""),
                ),
            )
        ],
        "door_instances": [
            {
                "id": str(getattr(instance, "id", "") or ""),
                "version_id": int(getattr(instance, "version_id", 0) or 0),
                "updated_at": str(getattr(instance, "updated_at", "") or ""),
            }
            for instance in sorted(
                list(door_instances or []),
                key=lambda row: (
                    int(getattr(row, "ui_order", 0) or 0),
                    str(getattr(row, "instance_code", "") or ""),
                    str(getattr(row, "id", "") or ""),
                ),
            )
        ],
    }


def order_design_snapshot_marker(
    *,
    source_design: SubCategoryDesign,
    interior_instances: list[OrderDesignInteriorInstance | SubCategoryDesignInteriorInstance] | None,
    door_instances: list[OrderDesignDoorInstance | SubCategoryDesignDoorInstance] | None = None,
) -> str:
    payload = _normalize_snapshot_marker(
        source_design=source_design,
        interior_instances=interior_instances,
        door_instances=door_instances,
    )
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def with_order_design_snapshot_checksum(
    meta: dict[str, dict[str, object]],
    *,
    checksum: str,
    marker: str | None = None,
    source_state_signature: str | None = None,
) -> dict[str, dict[str, object]]:
    next_meta = strip_snapshot_state_from_meta(meta)
    state: dict[str, object] = {"version": 2, "checksum": checksum}
    if marker:
        state["marker"] = marker
    if source_state_signature:
        state["source_state_signature"] = source_state_signature
    next_meta[SNAPSHOT_META_KEY] = state
    return next_meta


def order_design_snapshot_looks_fresh(
    *,
    meta: dict[str, object] | None,
    snapshot_checksum: str | None,
    source_design: SubCategoryDesign,
    interior_instances: list[OrderDesignInteriorInstance | SubCategoryDesignInteriorInstance] | None,
    door_instances: list[OrderDesignDoorInstance | SubCategoryDesignDoorInstance] | None = None,
) -> bool:
    state = read_order_design_snapshot_state(meta)
    expected_marker = order_design_snapshot_marker(
        source_design=source_design,
        interior_instances=interior_instances,
        door_instances=door_instances,
    )
    stored_marker = str(state.get("marker") or "")
    stored_checksum = str(state.get("checksum") or "")
    current_checksum = str(snapshot_checksum or "").strip()
    if not stored_marker or stored_marker != expected_marker:
        return False
    if not stored_checksum:
        return False
    return not current_checksum or current_checksum == stored_checksum


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
    if await door_instance_tables_ready(session):
        stmt = stmt.options(selectinload(SubCategoryDesign.door_instances))
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
            select(InternalPartGroup)
            .options(selectinload(InternalPartGroup.parts))
            .where(
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


async def _load_accessible_door_groups(
    session: AsyncSession,
    *,
    admin_id: uuid.UUID,
    group_ids: set[uuid.UUID],
) -> dict[uuid.UUID, DoorPartGroup]:
    if not group_ids:
        return {}
    include_param_defaults = await door_part_group_param_defaults_table_ready(session)
    stmt = (
        select(DoorPartGroup)
        .options(selectinload(DoorPartGroup.parts), selectinload(DoorPartGroup.param_groups))
        .where(
            and_(
                DoorPartGroup.id.in_(list(group_ids)),
                or_(DoorPartGroup.admin_id.is_(None), DoorPartGroup.admin_id == admin_id),
            )
        )
    )
    if include_param_defaults:
        stmt = stmt.options(selectinload(DoorPartGroup.param_defaults).selectinload(DoorPartGroupParamDefault.param))
    groups = (
        await session.scalars(
            stmt
        )
    ).all()
    groups_by_id = {item.id: item for item in groups}
    missing = [group_id for group_id in group_ids if group_id not in groups_by_id]
    if missing:
        await require_accessible_door_part_group(session, admin_id=admin_id, group_id=missing[0])
    return groups_by_id


def _strip_inherited_internal_param_values(
    *,
    source_base_values: dict[str, str | None],
    param_values: dict[str, object] | None,
) -> dict[str, str | None]:
    return strip_inherited_param_values(
        inherited_values=source_base_values,
        param_values=param_values,
    )


def _enabled_source_part_formula_ids(source_design: SubCategoryDesign) -> set[int]:
    return {
        int(part.part_formula_id)
        for part in list(source_design.parts or [])
        if bool(part.enabled) and int(part.part_formula_id or 0) > 0
    }


def _root_part_snapshots_for_order_item(
    *,
    item: OrderDesign,
    source_design: SubCategoryDesign,
) -> list[dict[str, object]]:
    root_formula_ids = _enabled_source_part_formula_ids(source_design)
    return [
        dict(snapshot or {})
        for snapshot in list(item.part_snapshots or [])
        if int(dict(snapshot or {}).get("part_formula_id") or 0) in root_formula_ids
    ]


def _root_viewer_boxes_for_order_item(
    *,
    item: OrderDesign,
    source_design: SubCategoryDesign,
) -> list[dict[str, object]]:
    boxes: list[dict[str, object]] = []
    for snapshot in _root_part_snapshots_for_order_item(item=item, source_design=source_design):
        viewer_payload = dict(snapshot.get("viewer_payload") or {})
        box = viewer_payload.get("box")
        if isinstance(box, dict):
            boxes.append(dict(box))
    return boxes


def build_effective_order_design_interior_param_values(
    *,
    context: DesignExecutionContext,
    internal_group: InternalPartGroup,
    base_raw_values: dict[str, str | None],
    param_values: dict[str, object] | None,
) -> dict[str, str | None]:
    group_param_codes = set(context.internal_group_param_codes.get(internal_group.id, set()))
    _, effective_values = merge_subcategory_and_internal_group_defaults(
        base_values={str(key): (None if value is None else str(value)) for key, value in dict(base_raw_values or {}).items()},
        group_param_codes=group_param_codes,
        group_default_values=dict(context.internal_group_display_values.get(internal_group.id, {})),
        instance_values={str(key): value for key, value in dict(param_values or {}).items()},
    )
    return {
        code: effective_values.get(code)
        for code in sorted(group_param_codes)
        if code in effective_values
    }


def _build_order_source_state(
    *,
    context: DesignExecutionContext,
    source_design: SubCategoryDesign,
    order_attr_values: dict[str, str | None],
    interior_instances: list[OrderDesignInteriorInstance | SubCategoryDesignInteriorInstance],
    door_instances: list[OrderDesignDoorInstance | SubCategoryDesignDoorInstance] | None = None,
) -> dict[str, object]:
    payload = {
        "context_signature": str(context.source_state.get("signature") or ""),
        "sub_category_design_id": str(source_design.id),
        "sub_category_design_version": int(getattr(source_design, "version_id", 0) or 0),
        "sub_category_design_updated_at": str(getattr(source_design, "updated_at", "") or ""),
        "order_attr_values": {key: value for key, value in sorted(order_attr_values.items())},
        "interior_instances": [
            {
                "id": str(getattr(instance, "id", "") or ""),
                "version_id": int(getattr(instance, "version_id", 0) or 0),
                "updated_at": str(getattr(instance, "updated_at", "") or ""),
                "internal_part_group_id": str(getattr(instance, "internal_part_group_id", "") or ""),
                "instance_code": str(getattr(instance, "instance_code", "") or ""),
                "line_color": str(getattr(instance, "line_color", "") or ""),
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
        "door_instances": [
            {
                "id": str(getattr(instance, "id", "") or ""),
                "version_id": int(getattr(instance, "version_id", 0) or 0),
                "updated_at": str(getattr(instance, "updated_at", "") or ""),
                "door_part_group_id": str(getattr(instance, "door_part_group_id", "") or ""),
                "instance_code": str(getattr(instance, "instance_code", "") or ""),
                "line_color": str(getattr(instance, "line_color", "") or ""),
                "ui_order": int(getattr(instance, "ui_order", 0) or 0),
                "structural_part_formula_ids": [int(row) for row in list(getattr(instance, "structural_part_formula_ids", []) or []) if int(row) > 0],
                "dependent_interior_instance_ids": [str(row).strip() for row in list(getattr(instance, "dependent_interior_instance_ids", []) or []) if str(row).strip()],
                "param_values": {
                    str(key): value
                    for key, value in sorted(dict(getattr(instance, "param_values", {}) or {}).items(), key=lambda row: str(row[0]))
                },
            }
            for instance in sorted(
                list(door_instances or []),
                key=lambda row: (
                    int(getattr(row, "ui_order", 0) or 0),
                    str(getattr(row, "instance_code", "") or ""),
                    str(getattr(row, "id", "") or ""),
                ),
            )
        ],
    }
    return {
        "payload": payload,
        "signature": build_source_state_signature(payload),
    }


async def build_order_design_snapshot(
    session: AsyncSession,
    *,
    order: Order,
    source_design: SubCategoryDesign,
    override_attr_values: dict[str, object] | None = None,
    interior_instances: list[OrderDesignInteriorInstance | SubCategoryDesignInteriorInstance] | None = None,
    door_instances: list[OrderDesignDoorInstance | SubCategoryDesignDoorInstance] | None = None,
) -> dict[str, object]:
    sub_category = await require_accessible_sub_category(
        session,
        admin_id=order.admin_id,
        sub_category_id=source_design.sub_category_id,
    )
    schema_ready = await interior_instance_tables_ready(session)
    door_schema_ready = await door_instance_tables_ready(session)
    sorted_interior_instances = (
        sorted(list(interior_instances or []), key=lambda row: (int(row.ui_order or 0), str(row.instance_code or "")))
        if schema_ready else []
    )
    sorted_door_instances = (
        sorted(list(door_instances or []), key=lambda row: (int(row.ui_order or 0), str(row.instance_code or "")))
        if door_schema_ready else []
    )
    context = await build_design_execution_context(
        session,
        admin_id=order.admin_id,
        sub_category=sub_category,
        part_formula_ids={
            int(part.part_formula_id)
            for part in list(source_design.parts or [])
            if bool(part.enabled) and int(part.part_formula_id or 0) > 0
        },
        internal_group_ids={instance.internal_part_group_id for instance in sorted_interior_instances},
        include_sub_category_display=False,
    )
    raw_params = dict(context.sub_category_raw_params)
    numeric_params = dict(context.sub_category_numeric_params)
    source_base_raw_params = {
        str(key): (None if value is None else str(value))
        for key, value in dict(raw_params or {}).items()
    }
    order_attr_values, order_attr_meta = await _build_display_attr_snapshot(
        session,
        sub_category=sub_category,
        order_admin_id=order.admin_id,
        override_values=override_attr_values,
    )
    for code, value in order_attr_values.items():
        raw_params[code] = value
        numeric_params[code] = _round_number(_coerce_numeric(value))

    resolved_base_formulas = resolve_base_formula_values_with_context(context, params=numeric_params)
    part_selections = [
        {
            "part_formula_id": int(part.part_formula_id),
            "enabled": bool(part.enabled),
            "ui_order": int(part.ui_order),
        }
        for part in sorted(source_design.parts, key=lambda row: (int(row.ui_order), int(row.part_formula_id)))
        if part.enabled
    ]

    part_snapshots: list[dict[str, object]] = []
    viewer_boxes: list[dict[str, object]] = []
    for selection in part_selections:
        formula = context.part_formulas_by_id.get(int(selection["part_formula_id"]))
        if not formula:
            continue
        resolved_part_formulas = resolve_part_formula_values(
            formula,
            params=numeric_params,
            base_formulas=resolved_base_formulas,
            context=context,
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
    source_boxes_by_formula_id = {
        int(row["part_formula_id"]): dict((row.get("viewer_payload") or {}).get("box") or {})
        for row in part_snapshots
        if isinstance((row.get("viewer_payload") or {}).get("box"), dict)
    }
    internal_groups_by_id = await _load_accessible_internal_groups(
        session,
        admin_id=order.admin_id,
        group_ids={instance.internal_part_group_id for instance in sorted_interior_instances},
    ) if sorted_interior_instances else {}
    for instance in sorted_interior_instances:
        internal_group = internal_groups_by_id.get(instance.internal_part_group_id)
        if internal_group is None:
            internal_group = await require_accessible_internal_part_group(
                session,
                admin_id=order.admin_id,
                group_id=instance.internal_part_group_id,
            )
        inherited_values = {
            **source_base_raw_params,
            **context.internal_group_display_values.get(internal_group.id, {}),
        }
        persisted_param_values = _strip_inherited_internal_param_values(
            source_base_values=inherited_values,
            param_values={str(key): value for key, value in dict(instance.param_values or {}).items()},
        )
        effective_param_values = build_effective_order_design_interior_param_values(
            context=context,
            internal_group=internal_group,
            base_raw_values=raw_params,
            param_values={str(key): value for key, value in dict(instance.param_values or {}).items()},
        )
        param_meta = {str(key): dict(value or {}) for key, value in dict(instance.param_meta or {}).items()}
        expected_param_codes = {str(key).strip() for key in dict(effective_param_values or {}).keys() if str(key).strip()}
        missing_param_meta_codes = expected_param_codes.difference(param_meta.keys())
        if expected_param_codes and (not param_meta or missing_param_meta_codes):
            _, resolved_param_meta = await build_sub_category_param_display_snapshot(
                session,
                sub_category=sub_category,
                codes=expected_param_codes,
                context=context,
            )
            for key, value in resolved_param_meta.items():
                code = str(key or "").strip()
                if not code:
                    continue
                current_meta = dict(param_meta.get(code) or {})
                for meta_key, meta_value in dict(value or {}).items():
                    if meta_value is None:
                        continue
                    if isinstance(meta_value, str) and not meta_value.strip():
                        continue
                    if meta_key not in current_meta or current_meta.get(meta_key) in (None, ""):
                        current_meta[str(meta_key)] = meta_value
                param_meta[code] = current_meta
        resolved = await resolve_internal_instance_preview(
            session,
            admin_id=order.admin_id,
            sub_category=sub_category,
            internal_group=internal_group,
            instance_id=getattr(instance, "id", None),
            instance_code=str(instance.instance_code or ""),
            line_color=str(getattr(instance, "line_color", "") or "").strip() or None,
            ui_order=int(instance.ui_order or 0),
            placement_z=float(instance.placement_z or 0),
            interior_box_snapshot=dict(instance.interior_box_snapshot or {}),
            param_values=persisted_param_values,
            param_meta=param_meta,
            base_raw_values=raw_params,
            base_numeric_params=numeric_params,
            prefer_base_params=True,
            context=context,
        )
        resolved_interior_instances.append(
            {
                "id": resolved.instance_id,
                "internal_part_group_id": resolved.internal_part_group_id,
                "internal_part_group_code": resolved.internal_part_group_code,
                "internal_part_group_title": resolved.internal_part_group_title,
                "instance_code": resolved.instance_code,
                "line_color": resolved.line_color,
                "ui_order": resolved.ui_order,
                "placement_z": resolved.placement_z,
                "interior_box_snapshot": resolved.interior_box_snapshot,
                "param_values": effective_param_values,
                "param_meta": resolved.param_meta,
                "auto_params": resolved.auto_params,
                "part_snapshots": resolved.part_snapshots,
                "viewer_boxes": resolved.viewer_boxes,
                "status": str(getattr(instance, "status", "draft") or "draft"),
            }
        )
        viewer_boxes.extend([dict(box or {}) for box in resolved.viewer_boxes])
        part_snapshots.extend([dict(row or {}) for row in resolved.part_snapshots])
        for row in list(resolved.part_snapshots or []):
            box = dict((row or {}).get("viewer_payload", {}) or {}).get("box")
            part_formula_id = int((row or {}).get("part_formula_id") or 0)
            if part_formula_id > 0 and isinstance(box, dict):
                source_boxes_by_formula_id[part_formula_id] = dict(box)
    resolved_door_instances: list[dict[str, object]] = []
    door_groups_by_id = await _load_accessible_door_groups(
        session,
        admin_id=order.admin_id,
        group_ids={instance.door_part_group_id for instance in sorted_door_instances},
    ) if sorted_door_instances else {}
    valid_interior_ids = {str(getattr(instance, "id", "") or "") for instance in sorted_interior_instances if str(getattr(instance, "id", "") or "").strip()}
    for instance in sorted_door_instances:
        door_group = door_groups_by_id.get(instance.door_part_group_id)
        if door_group is None:
            door_group = await require_accessible_door_part_group(session, admin_id=order.admin_id, group_id=instance.door_part_group_id)
        resolved = await resolve_door_instance_preview(
            session,
            admin_id=order.admin_id,
            sub_category=sub_category,
            door_part_group=door_group,
            instance_id=getattr(instance, "id", None),
            instance_code=str(instance.instance_code or ""),
            line_color=str(getattr(instance, "line_color", "") or "").strip() or None,
            ui_order=int(getattr(instance, "ui_order", 0) or 0),
            structural_part_formula_ids=list(getattr(instance, "structural_part_formula_ids", []) or []),
            dependent_interior_instance_ids=[
                str(row).strip()
                for row in list(getattr(instance, "dependent_interior_instance_ids", []) or [])
                if str(row).strip() and str(row).strip() in valid_interior_ids
            ],
            controller_box_snapshot=dict(getattr(instance, "controller_box_snapshot", {}) or {}),
            param_values=dict(getattr(instance, "param_values", {}) or {}),
            param_meta=dict(getattr(instance, "param_meta", {}) or {}),
            source_boxes_by_formula_id=source_boxes_by_formula_id,
            base_raw_values=raw_params,
            base_numeric_params=numeric_params,
            context=context,
        )
        resolved_door_instances.append(
            {
                "id": resolved.instance_id,
                "door_part_group_id": resolved.door_part_group_id,
                "door_part_group_code": resolved.door_part_group_code,
                "door_part_group_title": resolved.door_part_group_title,
                "controller_type": resolved.controller_type,
                "controller_bindings": resolved.controller_bindings,
                "instance_code": resolved.instance_code,
                "line_color": resolved.line_color,
                "ui_order": resolved.ui_order,
                "structural_part_formula_ids": resolved.structural_part_formula_ids,
                "dependent_interior_instance_ids": resolved.dependent_interior_instance_ids,
                "controller_box_snapshot": resolved.controller_box_snapshot,
                "param_values": resolved.param_values,
                "param_meta": resolved.param_meta,
                "computed_params": resolved.computed_params,
                "part_snapshots": resolved.part_snapshots,
                "viewer_boxes": resolved.viewer_boxes,
                "status": str(getattr(instance, "status", "draft") or "draft"),
            }
        )
        viewer_boxes.extend([dict(box or {}) for box in resolved.viewer_boxes])
        part_snapshots.extend([dict(row or {}) for row in resolved.part_snapshots])

    source_state = _build_order_source_state(
        context=context,
        source_design=source_design,
        order_attr_values=order_attr_values,
        interior_instances=sorted_interior_instances,
        door_instances=sorted_door_instances,
    )
    return {
        "sub_category_id": sub_category.id,
        "design_code": str(source_design.code or "").strip(),
        "design_title": str(source_design.design_title or "").strip(),
        "order_attr_values": order_attr_values,
        "order_attr_meta": order_attr_meta,
        "part_snapshots": part_snapshots,
        "viewer_boxes": viewer_boxes,
        "interior_instances": resolved_interior_instances,
        "door_instances": resolved_door_instances,
        "source_state": source_state,
    }


async def sync_order_design_snapshot(
    session: AsyncSession,
    *,
    item: OrderDesign,
    order: Order | None = None,
    source_design: SubCategoryDesign | None = None,
    force: bool = False,
) -> bool:
    current_order = order or await require_accessible_order(session, order_id=item.order_id)
    schema_ready = await interior_instance_tables_ready(session)
    door_schema_ready = await door_instance_tables_ready(session)
    current_interior_instances = list(item.interior_instances or []) if schema_ready else []
    current_door_instances = list(getattr(item, "door_instances", []) or []) if door_schema_ready else []
    current_source_design = source_design or await require_accessible_sub_category_design(
        session,
        admin_id=current_order.admin_id,
        design_id=item.sub_category_design_id,
    )
    if not force and order_design_snapshot_looks_fresh(
        meta=dict(item.order_attr_meta or {}),
        snapshot_checksum=str(item.snapshot_checksum or ""),
        source_design=current_source_design,
        interior_instances=current_interior_instances,
        door_instances=current_door_instances,
    ):
        return False
    snapshot = await build_order_design_snapshot(
        session,
        order=current_order,
        source_design=current_source_design,
        override_attr_values=dict(item.order_attr_values or {}),
        interior_instances=current_interior_instances,
        door_instances=current_door_instances,
    )
    next_checksum = build_order_design_snapshot_checksum(
        source_design=current_source_design,
        order_attr_values=dict(item.order_attr_values or {}),
        interior_instances=current_interior_instances,
        door_instances=current_door_instances,
        source_state=dict(snapshot.get("source_state") or {}),
    )
    next_marker = order_design_snapshot_marker(
        source_design=current_source_design,
        interior_instances=current_interior_instances,
        door_instances=current_door_instances,
    )
    if not force and read_order_design_snapshot_checksum(dict(item.order_attr_meta or {})) == next_checksum:
        return False
    changed = False
    if dict(item.order_attr_values or {}) != snapshot["order_attr_values"]:
        item.order_attr_values = snapshot["order_attr_values"]
        changed = True
    if strip_snapshot_state_from_meta(dict(item.order_attr_meta or {})) != snapshot["order_attr_meta"]:
        item.order_attr_meta = with_order_design_snapshot_checksum(
            snapshot["order_attr_meta"],
            checksum=next_checksum,
            marker=next_marker,
            source_state_signature=str(dict(snapshot.get("source_state") or {}).get("signature") or ""),
        )
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
    if door_schema_ready:
        door_by_id = {str(getattr(instance, "id", "")): instance for instance in list(getattr(item, "door_instances", []) or [])}
        for resolved in list(snapshot.get("door_instances") or []):
            instance = door_by_id.get(str(resolved.get("id") or ""))
            if not instance:
                continue
            if dict(instance.controller_box_snapshot or {}) != resolved["controller_box_snapshot"]:
                instance.controller_box_snapshot = resolved["controller_box_snapshot"]
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
        item.order_attr_meta = with_order_design_snapshot_checksum(
            dict(item.order_attr_meta or {}),
            checksum=next_checksum,
            marker=next_marker,
            source_state_signature=str(dict(snapshot.get("source_state") or {}).get("signature") or ""),
        )
        changed = True
    if str(item.snapshot_checksum or "") != next_checksum:
        item.snapshot_checksum = next_checksum
        changed = True
    return changed


async def refresh_order_design_interior_instance(
    session: AsyncSession,
    *,
    item: OrderDesign,
    order: Order,
    source_design: SubCategoryDesign,
    instance: OrderDesignInteriorInstance,
    internal_group: InternalPartGroup | None = None,
) -> None:
    sub_category = await require_accessible_sub_category(
        session,
        admin_id=order.admin_id,
        sub_category_id=source_design.sub_category_id,
    )
    current_group = internal_group or await require_accessible_internal_part_group(
        session,
        admin_id=order.admin_id,
        group_id=instance.internal_part_group_id,
    )
    context = await build_design_execution_context(
        session,
        admin_id=order.admin_id,
        sub_category=sub_category,
        part_formula_ids=_enabled_source_part_formula_ids(source_design),
        internal_group_ids={row.internal_part_group_id for row in list(item.interior_instances or [])},
        include_sub_category_display=False,
    )
    raw_params = dict(context.sub_category_raw_params)
    numeric_params = dict(context.sub_category_numeric_params)
    for code, value in dict(item.order_attr_values or {}).items():
        normalized = None if value is None else str(value)
        raw_params[str(code)] = normalized
        numeric_params[str(code)] = _round_number(_coerce_numeric(normalized))
    interior_box_snapshot = dict(instance.interior_box_snapshot or {})
    if not interior_box_snapshot:
        interior_box_snapshot = derive_interior_box_snapshot(
            _root_viewer_boxes_for_order_item(item=item, source_design=source_design)
        )
    persisted_input_values = {str(key): value for key, value in dict(instance.param_values or {}).items()}
    resolved = await resolve_internal_instance_preview(
        session,
        admin_id=order.admin_id,
        sub_category=sub_category,
        internal_group=current_group,
        instance_id=getattr(instance, "id", None),
        instance_code=str(instance.instance_code or ""),
        ui_order=int(instance.ui_order or 0),
        placement_z=float(instance.placement_z or 0),
        interior_box_snapshot=interior_box_snapshot,
        param_values=persisted_input_values,
        param_meta={str(key): dict(value or {}) for key, value in dict(instance.param_meta or {}).items()},
        base_raw_values=raw_params,
        base_numeric_params=numeric_params,
        prefer_base_params=True,
        context=context,
    )
    instance.interior_box_snapshot = resolved.interior_box_snapshot
    instance.param_values = build_effective_order_design_interior_param_values(
        context=context,
        internal_group=current_group,
        base_raw_values=raw_params,
        param_values=persisted_input_values,
    )
    instance.param_meta = resolved.param_meta
    instance.part_snapshots = resolved.part_snapshots
    instance.viewer_boxes = resolved.viewer_boxes


def refresh_order_design_aggregate_snapshots(
    *,
    item: OrderDesign,
    source_design: SubCategoryDesign,
) -> None:
    root_part_snapshots = _root_part_snapshots_for_order_item(item=item, source_design=source_design)
    root_boxes = _root_viewer_boxes_for_order_item(item=item, source_design=source_design)
    sorted_interiors = sorted(
        list(item.interior_instances or []),
        key=lambda row: (int(row.ui_order or 0), str(row.instance_code or "")),
    )
    item.part_snapshots = list(root_part_snapshots) + [
        dict(snapshot or {})
        for interior in sorted_interiors
        for snapshot in list(interior.part_snapshots or [])
    ]
    interior_payloads = [
        {
            "viewer_boxes": [dict(box or {}) for box in list(interior.viewer_boxes or [])],
        }
        for interior in sorted_interiors
    ]
    from designkp_backend.api.routers.order_designs import _merge_viewer_boxes  # local import avoids cycle at module load

    item.viewer_boxes = _merge_viewer_boxes(root_boxes, interior_payloads)


def refresh_order_design_snapshot_state(
    *,
    item: OrderDesign,
    source_design: SubCategoryDesign,
) -> None:
    state = read_order_design_snapshot_state(dict(item.order_attr_meta or {}))
    source_state_signature = str(state.get("source_state_signature") or "")
    current_interior_instances = list(item.interior_instances or [])
    checksum = build_order_design_snapshot_checksum(
        source_design=source_design,
        order_attr_values=dict(item.order_attr_values or {}),
        interior_instances=current_interior_instances,
        source_state={"signature": source_state_signature} if source_state_signature else None,
    )
    marker = order_design_snapshot_marker(
        source_design=source_design,
        interior_instances=current_interior_instances,
    )
    item.order_attr_meta = with_order_design_snapshot_checksum(
        dict(item.order_attr_meta or {}),
        checksum=checksum,
        marker=marker,
        source_state_signature=source_state_signature or None,
    )
    item.snapshot_checksum = checksum


async def next_order_design_instance_code(
    session: AsyncSession,
    *,
    order_id: uuid.UUID,
    design_code: str,
) -> str:
    rows = (
        await session.scalars(
            select(OrderDesign.instance_code)
            .where(and_(OrderDesign.order_id == order_id, OrderDesign.deleted_at.is_(None)))
            .order_by(OrderDesign.instance_code.asc())
        )
    ).all()
    max_seq = 0
    for value in rows:
        text = str(value or "").strip()
        if not text or text[0].upper() != "U":
            continue
        suffix = text[1:]
        if suffix.isdigit():
            max_seq = max(max_seq, int(suffix))
    return f"U{max_seq + 1}"


async def next_order_design_sort_order(session: AsyncSession, *, order_id: uuid.UUID) -> int:
    max_order = await session.scalar(
        select(func.max(OrderDesign.sort_order)).where(and_(OrderDesign.order_id == order_id, OrderDesign.deleted_at.is_(None)))
    )
    return int(max_order or 0) + 1
