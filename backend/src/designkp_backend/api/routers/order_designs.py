from __future__ import annotations

import uuid

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from designkp_backend.db.dependencies import get_db_session
from designkp_backend.db.models.account import OrderDesign, OrderDesignInteriorInstance
from designkp_backend.db.models.catalog import SubCategory, SubCategoryDesign
from designkp_backend.services.order_designs import (
    SNAPSHOT_META_KEY,
    build_order_design_snapshot,
    build_order_design_snapshot_checksum,
    interior_instance_tables_ready,
    next_order_design_instance_code,
    next_order_design_sort_order,
    normalize_order_attr_value,
    order_design_snapshot_marker,
    read_order_design_snapshot_checksum,
    refresh_order_design_aggregate_snapshots,
    refresh_order_design_interior_instance,
    refresh_order_design_snapshot_state,
    require_accessible_order,
    require_accessible_sub_category_design,
    strip_snapshot_state_from_meta,
    sync_order_design_snapshot,
    with_order_design_snapshot_checksum,
)
from designkp_backend.services.sub_category_designs import require_accessible_internal_part_group

router = APIRouter(prefix="/order-designs", tags=["order_designs"])
DEFAULT_INTERIOR_LINE_COLOR = "#8A98A3"


def _normalize_hex_color(value: str | None, fallback: str = DEFAULT_INTERIOR_LINE_COLOR) -> str:
    raw = str(value or "").strip()
    if not raw:
        return fallback
    normalized = raw if raw.startswith("#") else f"#{raw}"
    if not normalized or len(normalized) != 7 or not all(ch in "0123456789ABCDEFabcdef#" for ch in normalized):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Interior line color must be a HEX value like #8A98A3.")
    return normalized.upper()

DELETED_RESTORE_INSTANCE_CODE_KEY = "restore_instance_code"


class OrderDesignItem(BaseModel):
    id: uuid.UUID
    order_id: uuid.UUID
    admin_id: uuid.UUID
    user_id: uuid.UUID
    sub_category_design_id: uuid.UUID
    sub_category_id: uuid.UUID
    design_outline_color: str
    design_code: str
    design_title: str
    instance_code: str
    sort_order: int
    status: str
    order_attr_values: dict[str, str | None]
    order_attr_meta: dict[str, dict[str, object]]
    part_snapshots: list[dict[str, object]]
    viewer_boxes: list[dict[str, object]]
    interior_instances: list[dict[str, object]]
    snapshot_checksum: str


class OrderDesignCreate(BaseModel):
    order_id: uuid.UUID
    sub_category_design_id: uuid.UUID
    design_title: str | None = Field(default=None, max_length=255)
    instance_code: str | None = Field(default=None, max_length=64)
    sort_order: int | None = Field(default=None, ge=0)
    status: str = Field(default="draft", max_length=32)
    order_attr_values: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class OrderDesignUpdate(BaseModel):
    design_title: str = Field(min_length=1, max_length=255)
    instance_code: str = Field(min_length=1, max_length=64)
    sort_order: int = Field(ge=0)
    status: str = Field(default="draft", max_length=32)
    order_attr_values: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class OrderDesignInteriorInstanceUpdate(BaseModel):
    placement_z: float
    ui_order: int = Field(ge=0)
    instance_code: str = Field(min_length=1, max_length=64)
    line_color: str | None = Field(default=None, min_length=7, max_length=7)
    param_values: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class OrderDesignInteriorInstanceCreate(BaseModel):
    internal_part_group_id: uuid.UUID
    placement_z: float = 0
    ui_order: int | None = Field(default=None, ge=0)
    instance_code: str | None = Field(default=None, max_length=64)
    line_color: str | None = Field(default=None, min_length=7, max_length=7)
    param_values: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class OrderDesignInteriorInstanceItem(BaseModel):
    id: uuid.UUID
    internal_part_group_id: uuid.UUID
    controller_type: str | None = None
    controller_bindings: dict[str, dict[str, str | None]] = Field(default_factory=dict)
    instance_code: str
    line_color: str | None = None
    ui_order: int
    placement_z: float
    interior_box_snapshot: dict[str, object]
    param_values: dict[str, str | None]
    param_meta: dict[str, dict[str, object]]
    part_snapshots: list[dict[str, object]]
    viewer_boxes: list[dict[str, object]]
    status: str

    model_config = {"from_attributes": True}


class OrderDesignHistoryRestoreInteriorInstance(BaseModel):
    id: uuid.UUID
    internal_part_group_id: uuid.UUID
    instance_code: str = Field(min_length=1, max_length=64)
    line_color: str | None = Field(default=None, min_length=7, max_length=7)
    ui_order: int = Field(ge=0)
    placement_z: float = 0
    param_values: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
    status: str = Field(default="draft", max_length=32)


class OrderDesignHistoryRestorePayload(BaseModel):
    design_title: str = Field(min_length=1, max_length=255)
    instance_code: str = Field(min_length=1, max_length=64)
    sort_order: int = Field(ge=0)
    status: str = Field(default="draft", max_length=32)
    order_attr_values: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
    interior_instances: list[OrderDesignHistoryRestoreInteriorInstance] = Field(default_factory=list)


def _box_signature(box: dict[str, object]) -> str:
    return "|".join(
        str(round(float(box.get(key) or 0), 6))
        for key in ("width", "depth", "height", "cx", "cy", "cz")
    )


def _merge_viewer_boxes(
    root_boxes: list[dict[str, object]] | None,
    interior_payloads: list[dict[str, object]] | None,
) -> list[dict[str, object]]:
    if not interior_payloads:
        return [dict(box or {}) for box in list(root_boxes or [])]
    merged: list[dict[str, object]] = []
    seen: set[str] = set()
    for box in list(root_boxes or []):
        payload = dict(box or {})
        signature = _box_signature(payload)
        if signature in seen:
            continue
        seen.add(signature)
        merged.append(payload)
    for interior in list(interior_payloads or []):
        for box in list(interior.get("viewer_boxes") or []):
            payload = dict(box or {})
            signature = _box_signature(payload)
            if signature in seen:
                continue
            seen.add(signature)
            merged.append(payload)
    return merged


def _serialize_item(item: OrderDesign, *, include_interior: bool = True) -> OrderDesignItem:
    category = getattr(getattr(item.sub_category_design, "sub_category", None), "category", None)
    interior_payloads = (
        [
            {
                "id": instance.id,
                "internal_part_group_id": instance.internal_part_group_id,
                "controller_type": None,
                "controller_bindings": {},
                "instance_code": str(instance.instance_code or "").strip(),
                "line_color": str(getattr(instance, "line_color", "") or "").strip() or None,
                "ui_order": int(instance.ui_order or 0),
                "placement_z": float(instance.placement_z or 0),
                "interior_box_snapshot": dict(instance.interior_box_snapshot or {}),
                "param_values": {
                    str(key): (None if value is None else str(value))
                    for key, value in dict(instance.param_values or {}).items()
                },
                "param_meta": {
                    str(key): dict(value or {})
                    for key, value in dict(instance.param_meta or {}).items()
                },
                "part_snapshots": [dict(row or {}) for row in list(instance.part_snapshots or [])],
                "viewer_boxes": [dict(row or {}) for row in list(instance.viewer_boxes or [])],
                "status": str(instance.status or "draft").strip() or "draft",
            }
            for instance in sorted(item.interior_instances, key=lambda row: (int(row.ui_order or 0), str(row.instance_code or "")))
        ]
        if include_interior else []
    )
    return OrderDesignItem(
        id=item.id,
        order_id=item.order_id,
        admin_id=item.admin_id,
        user_id=item.user_id,
        sub_category_design_id=item.sub_category_design_id,
        sub_category_id=item.sub_category_id,
        design_outline_color=str(getattr(category, "design_outline_color", "#7A4A2B") or "#7A4A2B"),
        design_code=str(item.design_code or "").strip(),
        design_title=str(item.design_title or "").strip(),
        instance_code=str(item.instance_code or "").strip(),
        sort_order=int(item.sort_order or 0),
        status=str(item.status or "draft").strip() or "draft",
        order_attr_values={
            str(key): (None if value is None else str(value))
            for key, value in dict(item.order_attr_values or {}).items()
        },
        order_attr_meta={
            str(key): dict(value or {})
            for key, value in strip_snapshot_state_from_meta(dict(item.order_attr_meta or {})).items()
        },
        part_snapshots=[dict(row or {}) for row in list(item.part_snapshots or [])],
        viewer_boxes=_merge_viewer_boxes(list(item.viewer_boxes or []), interior_payloads),
        interior_instances=interior_payloads,
        snapshot_checksum=str(item.snapshot_checksum or "").strip(),
    )


async def _require_item(session: AsyncSession, item_id: uuid.UUID) -> OrderDesign:
    stmt = select(OrderDesign).options(
        selectinload(OrderDesign.sub_category_design).selectinload(SubCategoryDesign.sub_category).selectinload(SubCategory.category)
    )
    if await interior_instance_tables_ready(session):
        stmt = stmt.options(selectinload(OrderDesign.interior_instances))
    item = await session.scalar(
        stmt.where(and_(OrderDesign.id == item_id, OrderDesign.deleted_at.is_(None)))
    )
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order design not found.")
    await require_accessible_order(session, order_id=item.order_id)
    return item


async def _require_item_any_status(session: AsyncSession, item_id: uuid.UUID) -> OrderDesign:
    stmt = select(OrderDesign).options(
        selectinload(OrderDesign.sub_category_design).selectinload(SubCategoryDesign.sub_category).selectinload(SubCategory.category)
    )
    if await interior_instance_tables_ready(session):
        stmt = stmt.options(selectinload(OrderDesign.interior_instances))
    item = await session.scalar(stmt.where(OrderDesign.id == item_id))
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order design not found.")
    order = await require_accessible_order(session, order_id=item.order_id)
    include_interior = await interior_instance_tables_ready(session)
    if include_interior and list(item.interior_instances or []):
        source_design = await require_accessible_sub_category_design(
            session,
            admin_id=order.admin_id,
            design_id=item.sub_category_design_id,
        )
        if await sync_order_design_snapshot(session, item=item, order=order, source_design=source_design):
            await session.commit()
            item = await session.scalar(stmt.where(and_(OrderDesign.id == item_id, OrderDesign.deleted_at.is_(None))))
            if not item:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order design not found.")
    return item


async def _ensure_unique_instance_code(
    session: AsyncSession,
    *,
    order_id: uuid.UUID,
    instance_code: str,
    exclude_id: uuid.UUID | None = None,
) -> None:
    stmt = select(OrderDesign).where(
        and_(
            OrderDesign.order_id == order_id,
            OrderDesign.instance_code == instance_code,
            OrderDesign.deleted_at.is_(None),
        )
    )
    if exclude_id is not None:
        stmt = stmt.where(OrderDesign.id != exclude_id)
    duplicate = await session.scalar(stmt)
    if duplicate:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Instance code is already used in this order.")


def _deleted_order_design_instance_code(instance_code: str, item_id: uuid.UUID) -> str:
    prefix = (str(instance_code or "").strip() or "design")[:40]
    suffix = f"__deleted__{str(item_id).replace('-', '')[:12]}"
    return f"{prefix}{suffix}"[:64]


def _remember_deleted_instance_code(meta: dict[str, object] | None, instance_code: str) -> dict[str, object]:
    next_meta = dict(meta or {})
    state = dict(next_meta.get(SNAPSHOT_META_KEY) or {})
    state[DELETED_RESTORE_INSTANCE_CODE_KEY] = str(instance_code or "").strip()
    next_meta[SNAPSHOT_META_KEY] = state
    return next_meta


def _restore_deleted_instance_code(meta: dict[str, object] | None, fallback: str) -> tuple[str, dict[str, object]]:
    next_meta = dict(meta or {})
    state = dict(next_meta.get(SNAPSHOT_META_KEY) or {})
    instance_code = str(state.get(DELETED_RESTORE_INSTANCE_CODE_KEY) or "").strip() or str(fallback or "").strip()
    state.pop(DELETED_RESTORE_INSTANCE_CODE_KEY, None)
    if state:
        next_meta[SNAPSHOT_META_KEY] = state
    else:
        next_meta.pop(SNAPSHOT_META_KEY, None)
    return instance_code, next_meta


def _normalize_attr_values(
    raw_values: dict[str, str | int | float | bool | None],
    current_meta: dict[str, dict[str, object]],
) -> dict[str, str | None]:
    normalized: dict[str, str | None] = {}
    for key, meta in strip_snapshot_state_from_meta(current_meta).items():
        input_mode = "binary" if str(meta.get("input_mode") or "") == "binary" else "value"
        next_value = raw_values[key] if key in raw_values else None
        normalized[key] = normalize_order_attr_value(next_value, input_mode=input_mode)
    return normalized


def _clone_order_design_json(value: object) -> object:
    if isinstance(value, dict):
        return {str(key): _clone_order_design_json(inner) for key, inner in value.items()}
    if isinstance(value, list):
        return [_clone_order_design_json(inner) for inner in value]
    return value


def _apply_resolved_interior_snapshot(
    item: OrderDesign,
    *,
    snapshot: dict[str, object],
) -> None:
    resolved_by_id = {
        str(row.get("id") or ""): row
        for row in list(snapshot.get("interior_instances") or [])
        if str(row.get("id") or "").strip()
    }
    for instance in list(item.interior_instances or []):
        resolved = resolved_by_id.get(str(instance.id))
        if not resolved:
            continue
        instance.interior_box_snapshot = dict(resolved.get("interior_box_snapshot") or {})
        instance.param_values = dict(resolved.get("param_values") or {})
        instance.param_meta = dict(resolved.get("param_meta") or {})
        instance.part_snapshots = list(resolved.get("part_snapshots") or [])
        instance.viewer_boxes = list(resolved.get("viewer_boxes") or [])


def _normalize_interior_param_values(
    payload: dict[str, str | int | float | bool | None],
) -> dict[str, str | None]:
    return {
        str(key): (None if value is None else str(value))
        for key, value in dict(payload or {}).items()
        if str(key or "").strip()
    }


def _next_generated_interior_instance_code(
    *,
    existing_instances: list[object],
    group_code: str | None,
    fallback_order: int,
) -> str:
    prefix = str(group_code or "interior").strip() or "interior"
    existing_codes = {
        str(getattr(item, "instance_code", "") or "").strip()
        for item in list(existing_instances or [])
    }
    suffix = max(1, int(fallback_order) + 1)
    while True:
        candidate = f"{prefix}-{suffix:02d}"
        if candidate not in existing_codes:
            return candidate
        suffix += 1


def _serialize_interior_instance_item(instance: OrderDesignInteriorInstance) -> OrderDesignInteriorInstanceItem:
    return OrderDesignInteriorInstanceItem(
        id=instance.id,
        internal_part_group_id=instance.internal_part_group_id,
        controller_type=None,
        controller_bindings={},
        instance_code=str(instance.instance_code or "").strip(),
        line_color=str(getattr(instance, "line_color", "") or "").strip() or None,
        ui_order=int(instance.ui_order or 0),
        placement_z=float(instance.placement_z or 0),
        interior_box_snapshot=dict(instance.interior_box_snapshot or {}),
        param_values={
            str(key): (None if value is None else str(value))
            for key, value in dict(instance.param_values or {}).items()
        },
        param_meta={
            str(key): dict(value or {})
            for key, value in dict(instance.param_meta or {}).items()
        },
        part_snapshots=[dict(row or {}) for row in list(instance.part_snapshots or [])],
        viewer_boxes=[dict(row or {}) for row in list(instance.viewer_boxes or [])],
        status=str(instance.status or "draft").strip() or "draft",
    )


async def _rebuild_order_design_after_interior_change(
    session: AsyncSession,
    *,
    item: OrderDesign,
) -> OrderDesign:
    order = await require_accessible_order(session, order_id=item.order_id)
    source_design = await require_accessible_sub_category_design(
        session,
        admin_id=order.admin_id,
        design_id=item.sub_category_design_id,
    )
    snapshot = await build_order_design_snapshot(
        session,
        order=order,
        source_design=source_design,
        override_attr_values=dict(item.order_attr_values or {}),
        interior_instances=list(item.interior_instances or []),
    )
    current_interior_instances = list(item.interior_instances or [])
    snapshot_checksum = build_order_design_snapshot_checksum(
        source_design=source_design,
        order_attr_values=dict(item.order_attr_values or {}),
        interior_instances=current_interior_instances,
        source_state=dict(snapshot.get("source_state") or {}),
    )
    snapshot_marker = order_design_snapshot_marker(
        source_design=source_design,
        interior_instances=current_interior_instances,
    )
    item.part_snapshots = snapshot["part_snapshots"]
    item.viewer_boxes = snapshot["viewer_boxes"]
    _apply_resolved_interior_snapshot(item, snapshot=snapshot)
    item.order_attr_meta = with_order_design_snapshot_checksum(
        dict(item.order_attr_meta or {}),
        checksum=snapshot_checksum,
        marker=snapshot_marker,
        source_state_signature=str(dict(snapshot.get("source_state") or {}).get("signature") or ""),
    )
    item.snapshot_checksum = snapshot_checksum
    await session.commit()
    return await _require_item(session, item.id)


async def _duplicate_order_design_record(
    session: AsyncSession,
    *,
    source_item: OrderDesign,
) -> OrderDesign:
    include_interior = await interior_instance_tables_ready(session)
    order = await require_accessible_order(session, order_id=source_item.order_id)
    next_instance_code = await next_order_design_instance_code(
        session,
        order_id=order.id,
        design_code=str(source_item.design_code or "").strip(),
    )
    await _ensure_unique_instance_code(session, order_id=order.id, instance_code=next_instance_code)
    checksum = (
        str(source_item.snapshot_checksum or "").strip()
        or read_order_design_snapshot_checksum(dict(source_item.order_attr_meta or {}))
        or build_order_design_snapshot_checksum(
            source_design=await require_accessible_sub_category_design(
                session,
                admin_id=order.admin_id,
                design_id=source_item.sub_category_design_id,
            ),
            order_attr_values=dict(source_item.order_attr_values or {}),
            interior_instances=list(source_item.interior_instances or []) if include_interior else [],
        )
    )
    duplicated = OrderDesign(
        order_id=source_item.order_id,
        admin_id=source_item.admin_id,
        user_id=source_item.user_id,
        sub_category_design_id=source_item.sub_category_design_id,
        sub_category_id=source_item.sub_category_id,
        design_code=str(source_item.design_code or "").strip(),
        design_title=str(source_item.design_title or "").strip(),
        instance_code=next_instance_code,
        sort_order=await next_order_design_sort_order(session, order_id=source_item.order_id),
        status=str(source_item.status or "draft").strip() or "draft",
        order_attr_values=_clone_order_design_json(dict(source_item.order_attr_values or {})),
        order_attr_meta=with_order_design_snapshot_checksum(
            strip_snapshot_state_from_meta(dict(source_item.order_attr_meta or {})),
            checksum=checksum,
        ),
        part_snapshots=_clone_order_design_json(list(source_item.part_snapshots or [])),
        viewer_boxes=_clone_order_design_json(list(source_item.viewer_boxes or [])),
        snapshot_checksum=checksum,
    )
    session.add(duplicated)
    await session.flush()
    if include_interior:
        for interior in list(source_item.interior_instances or []):
            session.add(
                OrderDesignInteriorInstance(
                    order_design_id=duplicated.id,
                    source_instance_id=interior.source_instance_id,
                    internal_part_group_id=interior.internal_part_group_id,
                    instance_code=str(interior.instance_code or "").strip(),
                    line_color=_normalize_hex_color(getattr(interior, "line_color", None), DEFAULT_INTERIOR_LINE_COLOR) if getattr(interior, "line_color", None) else None,
                    ui_order=int(interior.ui_order or 0),
                    placement_z=float(interior.placement_z or 0),
                    interior_box_snapshot=_clone_order_design_json(dict(interior.interior_box_snapshot or {})),
                    param_values=_clone_order_design_json(dict(interior.param_values or {})),
                    param_meta=_clone_order_design_json(dict(interior.param_meta or {})),
                    part_snapshots=_clone_order_design_json(list(interior.part_snapshots or [])),
                    viewer_boxes=_clone_order_design_json(list(interior.viewer_boxes or [])),
                    status=str(interior.status or "draft").strip() or "draft",
                )
            )
    await session.commit()
    return await _require_item(session, duplicated.id)


@router.get("", response_model=list[OrderDesignItem])
async def list_order_designs(
    order_id: uuid.UUID = Query(...),
    session: AsyncSession = Depends(get_db_session),
) -> list[OrderDesignItem]:
    order = await require_accessible_order(session, order_id=order_id)
    include_interior = await interior_instance_tables_ready(session)
    items = (
        await session.scalars(
            (select(OrderDesign).options(selectinload(OrderDesign.interior_instances)) if include_interior else select(OrderDesign))
            .options(selectinload(OrderDesign.sub_category_design).selectinload(SubCategoryDesign.sub_category).selectinload(SubCategory.category))
            .where(and_(OrderDesign.order_id == order_id, OrderDesign.deleted_at.is_(None)))
            .order_by(OrderDesign.sort_order.asc(), OrderDesign.instance_code.asc())
        )
    ).all()
    if include_interior:
        changed = False
        source_design_cache: dict[str, SubCategoryDesign] = {}
        for item in items:
            if not list(item.interior_instances or []):
                continue
            source_key = str(item.sub_category_design_id)
            source_design = source_design_cache.get(source_key)
            if source_design is None:
                source_design = await require_accessible_sub_category_design(
                    session,
                    admin_id=order.admin_id,
                    design_id=item.sub_category_design_id,
                )
                source_design_cache[source_key] = source_design
            if await sync_order_design_snapshot(session, item=item, order=order, source_design=source_design):
                changed = True
        if changed:
            await session.commit()
            items = (
                await session.scalars(
                    (select(OrderDesign).options(selectinload(OrderDesign.interior_instances)) if include_interior else select(OrderDesign))
                    .options(selectinload(OrderDesign.sub_category_design).selectinload(SubCategoryDesign.sub_category).selectinload(SubCategory.category))
                    .where(and_(OrderDesign.order_id == order_id, OrderDesign.deleted_at.is_(None)))
                    .order_by(OrderDesign.sort_order.asc(), OrderDesign.instance_code.asc())
                )
            ).all()
    return [_serialize_item(item, include_interior=include_interior) for item in items]


@router.post("", response_model=OrderDesignItem, status_code=status.HTTP_201_CREATED)
async def create_order_design(payload: OrderDesignCreate, session: AsyncSession = Depends(get_db_session)) -> OrderDesignItem:
    order = await require_accessible_order(session, order_id=payload.order_id)
    include_interior = await interior_instance_tables_ready(session)
    source_design = await require_accessible_sub_category_design(
        session,
        admin_id=order.admin_id,
        design_id=payload.sub_category_design_id,
    )
    snapshot = await build_order_design_snapshot(
        session,
        order=order,
        source_design=source_design,
        override_attr_values=payload.order_attr_values,
        interior_instances=list(source_design.interior_instances or []) if include_interior else [],
    )
    snapshot_checksum = build_order_design_snapshot_checksum(
        source_design=source_design,
        order_attr_values=snapshot["order_attr_values"],
        interior_instances=list(source_design.interior_instances or []) if include_interior else [],
        source_state=dict(snapshot.get("source_state") or {}),
    )
    snapshot_marker = order_design_snapshot_marker(
        source_design=source_design,
        interior_instances=list(source_design.interior_instances or []) if include_interior else [],
    )
    instance_code = str(payload.instance_code or "").strip() or await next_order_design_instance_code(
        session,
        order_id=order.id,
        design_code=str(snapshot["design_code"]),
    )
    await _ensure_unique_instance_code(session, order_id=order.id, instance_code=instance_code)
    title = str(payload.design_title or snapshot["design_title"] or "").strip()
    if not title:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Design title is required.")
    item = OrderDesign(
        order_id=order.id,
        admin_id=order.admin_id,
        user_id=order.user_id,
        sub_category_design_id=source_design.id,
        sub_category_id=source_design.sub_category_id,
        design_code=str(snapshot["design_code"]),
        design_title=title,
        instance_code=instance_code,
        sort_order=payload.sort_order if payload.sort_order is not None else await next_order_design_sort_order(session, order_id=order.id),
        status=str(payload.status or "draft").strip() or "draft",
        order_attr_values=snapshot["order_attr_values"],
        order_attr_meta=with_order_design_snapshot_checksum(
            snapshot["order_attr_meta"],
            checksum=snapshot_checksum,
            marker=snapshot_marker,
            source_state_signature=str(dict(snapshot.get("source_state") or {}).get("signature") or ""),
        ),
        part_snapshots=snapshot["part_snapshots"],
        viewer_boxes=snapshot["viewer_boxes"],
        snapshot_checksum=snapshot_checksum,
    )
    session.add(item)
    await session.flush()
    if include_interior:
        source_interiors_by_id = {
            str(interior.id): interior
            for interior in list(source_design.interior_instances or [])
        }
        for interior in list(snapshot["interior_instances"] or []):
            source_interior = source_interiors_by_id.get(str(interior.get("id") or ""))
            session.add(
                OrderDesignInteriorInstance(
                    order_design_id=item.id,
                    source_instance_id=getattr(source_interior, "id", None),
                    internal_part_group_id=uuid.UUID(str(interior.get("internal_part_group_id"))),
                    instance_code=str(interior.get("instance_code") or "").strip(),
                    line_color=(
                        str(interior.get("line_color") or "").strip()
                        or
                        str(getattr(source_interior, "line_color", "") or "").strip()
                        or None
                    ),
                    ui_order=int(interior.get("ui_order") or 0),
                    placement_z=float(interior.get("placement_z") or 0),
                    interior_box_snapshot=dict(interior.get("interior_box_snapshot") or {}),
                    param_values=dict(interior.get("param_values") or {}),
                    param_meta=dict(interior.get("param_meta") or {}),
                    part_snapshots=list(interior.get("part_snapshots") or []),
                    viewer_boxes=list(interior.get("viewer_boxes") or []),
                    status=str(interior.get("status") or getattr(source_interior, "status", "draft") or "draft").strip() or "draft",
                )
            )
    await session.commit()
    item = await _require_item(session, item.id)
    return _serialize_item(item, include_interior=include_interior)


@router.patch("/{item_id}", response_model=OrderDesignItem)
async def update_order_design(
    item_id: uuid.UUID,
    payload: OrderDesignUpdate,
    session: AsyncSession = Depends(get_db_session),
) -> OrderDesignItem:
    item = await _require_item(session, item_id)
    include_interior = await interior_instance_tables_ready(session)
    order = await require_accessible_order(session, order_id=item.order_id)
    source_design = await require_accessible_sub_category_design(
        session,
        admin_id=order.admin_id,
        design_id=item.sub_category_design_id,
    )
    title = str(payload.design_title or "").strip()
    instance_code = str(payload.instance_code or "").strip()
    if not title:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Design title is required.")
    if not instance_code:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Instance code is required.")
    await _ensure_unique_instance_code(session, order_id=item.order_id, instance_code=instance_code, exclude_id=item.id)
    next_attr_values = _normalize_attr_values(payload.order_attr_values, dict(item.order_attr_meta or {}))
    snapshot = await build_order_design_snapshot(
        session,
        order=order,
        source_design=source_design,
        override_attr_values=next_attr_values,
        interior_instances=list(item.interior_instances or []) if include_interior else [],
    )
    current_interior_instances = list(item.interior_instances or []) if include_interior else []
    snapshot_checksum = build_order_design_snapshot_checksum(
        source_design=source_design,
        order_attr_values=snapshot["order_attr_values"],
        interior_instances=current_interior_instances,
        source_state=dict(snapshot.get("source_state") or {}),
    )
    snapshot_marker = order_design_snapshot_marker(
        source_design=source_design,
        interior_instances=current_interior_instances,
    )
    item.design_title = title
    item.instance_code = instance_code
    item.sort_order = payload.sort_order
    item.status = str(payload.status or "draft").strip() or "draft"
    item.order_attr_values = snapshot["order_attr_values"]
    item.order_attr_meta = with_order_design_snapshot_checksum(
        snapshot["order_attr_meta"],
        checksum=snapshot_checksum,
        marker=snapshot_marker,
        source_state_signature=str(dict(snapshot.get("source_state") or {}).get("signature") or ""),
    )
    item.part_snapshots = snapshot["part_snapshots"]
    item.viewer_boxes = snapshot["viewer_boxes"]
    if include_interior:
        _apply_resolved_interior_snapshot(item, snapshot=snapshot)
    item.snapshot_checksum = snapshot_checksum
    await session.commit()
    item = await _require_item(session, item.id)
    return _serialize_item(item, include_interior=include_interior)


@router.post("/{item_id}/duplicate", response_model=OrderDesignItem, status_code=status.HTTP_201_CREATED)
async def duplicate_order_design(
    item_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> OrderDesignItem:
    source_item = await _require_item(session, item_id)
    include_interior = await interior_instance_tables_ready(session)
    duplicated = await _duplicate_order_design_record(
        session,
        source_item=source_item,
    )
    return _serialize_item(duplicated, include_interior=include_interior)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_order_design(item_id: uuid.UUID, session: AsyncSession = Depends(get_db_session)) -> Response:
    item = await _require_item(session, item_id)
    original_instance_code = str(item.instance_code or "").strip()
    item.order_attr_meta = _remember_deleted_instance_code(dict(item.order_attr_meta or {}), original_instance_code)
    item.instance_code = _deleted_order_design_instance_code(original_instance_code, item.id)
    item.deleted_at = datetime.now(timezone.utc)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{item_id}/restore", response_model=OrderDesignItem)
async def restore_order_design(item_id: uuid.UUID, session: AsyncSession = Depends(get_db_session)) -> OrderDesignItem:
    item = await _require_item_any_status(session, item_id)
    if item.deleted_at is None:
        include_interior = await interior_instance_tables_ready(session)
        return _serialize_item(item, include_interior=include_interior)
    instance_code, next_meta = _restore_deleted_instance_code(dict(item.order_attr_meta or {}), str(item.instance_code or "").strip())
    await _ensure_unique_instance_code(session, order_id=item.order_id, instance_code=instance_code, exclude_id=item.id)
    item.instance_code = instance_code
    item.order_attr_meta = next_meta
    item.deleted_at = None
    await session.commit()
    item = await _require_item(session, item_id)
    include_interior = await interior_instance_tables_ready(session)
    return _serialize_item(item, include_interior=include_interior)


@router.post("/{item_id}/history-restore", response_model=OrderDesignItem)
async def restore_order_design_history_state(
    item_id: uuid.UUID,
    payload: OrderDesignHistoryRestorePayload,
    session: AsyncSession = Depends(get_db_session),
) -> OrderDesignItem:
    item = await _require_item(session, item_id)
    include_interior = await interior_instance_tables_ready(session)
    order = await require_accessible_order(session, order_id=item.order_id)
    source_design = await require_accessible_sub_category_design(
        session,
        admin_id=order.admin_id,
        design_id=item.sub_category_design_id,
    )

    item.design_title = str(payload.design_title or "").strip()
    item.instance_code = str(payload.instance_code or "").strip()
    item.sort_order = int(payload.sort_order)
    item.status = str(payload.status or "draft").strip() or "draft"
    item.order_attr_values = _normalize_attr_values(payload.order_attr_values, dict(item.order_attr_meta or {}))

    if include_interior:
        existing_instances = {str(instance.id): instance for instance in list(item.interior_instances or [])}
        target_instances: list[OrderDesignInteriorInstance] = []
        target_ids: set[str] = set()
        for snapshot in sorted(payload.interior_instances, key=lambda row: (int(row.ui_order), str(row.instance_code or ""))):
            key = str(snapshot.id)
            target_ids.add(key)
            instance = existing_instances.get(key)
            if instance is None:
                instance = OrderDesignInteriorInstance(
                    id=snapshot.id,
                    order_design_id=item.id,
                    source_instance_id=None,
                    internal_part_group_id=snapshot.internal_part_group_id,
                    instance_code=str(snapshot.instance_code or "").strip(),
                    line_color=_normalize_hex_color(snapshot.line_color, DEFAULT_INTERIOR_LINE_COLOR) if snapshot.line_color else None,
                    ui_order=int(snapshot.ui_order),
                    placement_z=float(snapshot.placement_z or 0),
                    interior_box_snapshot={},
                    param_values=_normalize_interior_param_values(snapshot.param_values),
                    param_meta={},
                    part_snapshots=[],
                    viewer_boxes=[],
                    status=str(snapshot.status or "draft").strip() or "draft",
                )
                session.add(instance)
            else:
                instance.internal_part_group_id = snapshot.internal_part_group_id
                instance.instance_code = str(snapshot.instance_code or "").strip()
                instance.line_color = _normalize_hex_color(snapshot.line_color, DEFAULT_INTERIOR_LINE_COLOR) if snapshot.line_color else None
                instance.ui_order = int(snapshot.ui_order)
                instance.placement_z = float(snapshot.placement_z or 0)
                instance.param_values = _normalize_interior_param_values(snapshot.param_values)
                instance.status = str(snapshot.status or "draft").strip() or "draft"
            target_instances.append(instance)

        for instance in list(item.interior_instances or []):
            if str(instance.id) not in target_ids:
                await session.delete(instance)

        await session.flush()
        item.interior_instances = target_instances

    await sync_order_design_snapshot(
        session,
        item=item,
        order=order,
        source_design=source_design,
        force=True,
    )
    await session.commit()
    item = await _require_item(session, item.id)
    return _serialize_item(item, include_interior=include_interior)


@router.patch("/{item_id}/interior-instances/{instance_id}", response_model=OrderDesignInteriorInstanceItem)
async def update_order_design_interior_instance(
    item_id: uuid.UUID,
    instance_id: uuid.UUID,
    payload: OrderDesignInteriorInstanceUpdate,
    session: AsyncSession = Depends(get_db_session),
) -> OrderDesignInteriorInstanceItem:
    if not await interior_instance_tables_ready(session):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Interior-instance tables are not available yet. Run database migrations first.")
    item = await _require_item(session, item_id)
    target = next((instance for instance in item.interior_instances if instance.id == instance_id), None)
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order design interior instance not found.")
    target.instance_code = str(payload.instance_code or "").strip()
    target.line_color = _normalize_hex_color(payload.line_color, DEFAULT_INTERIOR_LINE_COLOR) if payload.line_color else None
    target.ui_order = int(payload.ui_order)
    target.placement_z = float(payload.placement_z or 0)
    target.param_values = _normalize_interior_param_values(payload.param_values)
    order = await require_accessible_order(session, order_id=item.order_id)
    source_design = await require_accessible_sub_category_design(
        session,
        admin_id=order.admin_id,
        design_id=item.sub_category_design_id,
    )
    await refresh_order_design_interior_instance(
        session,
        item=item,
        order=order,
        source_design=source_design,
        instance=target,
    )
    refresh_order_design_aggregate_snapshots(item=item, source_design=source_design)
    refresh_order_design_snapshot_state(item=item, source_design=source_design)
    response = _serialize_interior_instance_item(target)
    await session.commit()
    return response


@router.post("/{item_id}/interior-instances", response_model=OrderDesignInteriorInstanceItem, status_code=status.HTTP_201_CREATED)
async def create_order_design_interior_instance(
    item_id: uuid.UUID,
    payload: OrderDesignInteriorInstanceCreate,
    session: AsyncSession = Depends(get_db_session),
) -> OrderDesignInteriorInstanceItem:
    if not await interior_instance_tables_ready(session):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Interior-instance tables are not available yet. Run database migrations first.")
    item = await _require_item(session, item_id)
    order = await require_accessible_order(session, order_id=item.order_id)
    group = await require_accessible_internal_part_group(
        session,
        admin_id=order.admin_id,
        group_id=payload.internal_part_group_id,
    )
    source_design = await require_accessible_sub_category_design(
        session,
        admin_id=order.admin_id,
        design_id=item.sub_category_design_id,
    )
    existing_instances = list(item.interior_instances or [])
    next_order = payload.ui_order if payload.ui_order is not None else (max([int(row.ui_order or 0) for row in existing_instances], default=-1) + 1)
    next_code = str(payload.instance_code or "").strip() or _next_generated_interior_instance_code(
        existing_instances=existing_instances,
        group_code=getattr(group, "code", None),
        fallback_order=next_order,
    )
    target = OrderDesignInteriorInstance(
        order_design_id=item.id,
        source_instance_id=None,
        internal_part_group_id=group.id,
        instance_code=next_code,
        line_color=_normalize_hex_color(payload.line_color, DEFAULT_INTERIOR_LINE_COLOR) if payload.line_color else _normalize_hex_color(getattr(group, "line_color", None), DEFAULT_INTERIOR_LINE_COLOR),
        ui_order=int(next_order),
        placement_z=float(payload.placement_z or 0),
        interior_box_snapshot={},
        param_values=_normalize_interior_param_values(payload.param_values),
        param_meta={},
        part_snapshots=[],
        viewer_boxes=[],
        status="draft",
    )
    session.add(target)
    await session.flush()
    item = await _require_item(session, item.id)
    if target not in list(item.interior_instances or []):
        item.interior_instances = [*list(item.interior_instances or []), target]
    await refresh_order_design_interior_instance(
        session,
        item=item,
        order=order,
        source_design=source_design,
        instance=target,
        internal_group=group,
    )
    refresh_order_design_aggregate_snapshots(item=item, source_design=source_design)
    refresh_order_design_snapshot_state(item=item, source_design=source_design)
    response = _serialize_interior_instance_item(target)
    await session.commit()
    return response


@router.post("/{item_id}/interior-instances/{instance_id}/duplicate", response_model=OrderDesignInteriorInstanceItem, status_code=status.HTTP_201_CREATED)
async def duplicate_order_design_interior_instance(
    item_id: uuid.UUID,
    instance_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> OrderDesignInteriorInstanceItem:
    if not await interior_instance_tables_ready(session):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Interior-instance tables are not available yet. Run database migrations first.")
    item = await _require_item(session, item_id)
    source = next((instance for instance in item.interior_instances if instance.id == instance_id), None)
    if not source:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order design interior instance not found.")
    order = await require_accessible_order(session, order_id=item.order_id)
    group = await require_accessible_internal_part_group(
        session,
        admin_id=order.admin_id,
        group_id=source.internal_part_group_id,
    )
    source_design = await require_accessible_sub_category_design(
        session,
        admin_id=order.admin_id,
        design_id=item.sub_category_design_id,
    )
    existing_instances = list(item.interior_instances or [])
    next_order = max([int(row.ui_order or 0) for row in existing_instances], default=-1) + 1
    target = OrderDesignInteriorInstance(
        order_design_id=item.id,
        source_instance_id=source.source_instance_id,
        internal_part_group_id=source.internal_part_group_id,
        instance_code=_next_generated_interior_instance_code(
            existing_instances=existing_instances,
            group_code=getattr(group, "code", None),
            fallback_order=next_order,
        ),
        line_color=_normalize_hex_color(getattr(source, "line_color", None), DEFAULT_INTERIOR_LINE_COLOR) if getattr(source, "line_color", None) else _normalize_hex_color(getattr(group, "line_color", None), DEFAULT_INTERIOR_LINE_COLOR),
        ui_order=int(next_order),
        placement_z=float(source.placement_z or 0),
        interior_box_snapshot={},
        param_values=_normalize_interior_param_values(dict(source.param_values or {})),
        param_meta={},
        part_snapshots=[],
        viewer_boxes=[],
        status=str(source.status or "draft").strip() or "draft",
    )
    session.add(target)
    await session.flush()
    item = await _require_item(session, item.id)
    if target not in list(item.interior_instances or []):
        item.interior_instances = [*list(item.interior_instances or []), target]
    await refresh_order_design_interior_instance(
        session,
        item=item,
        order=order,
        source_design=source_design,
        instance=target,
        internal_group=group,
    )
    refresh_order_design_aggregate_snapshots(item=item, source_design=source_design)
    refresh_order_design_snapshot_state(item=item, source_design=source_design)
    response = _serialize_interior_instance_item(target)
    await session.commit()
    return response


@router.delete("/{item_id}/interior-instances/{instance_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_order_design_interior_instance(
    item_id: uuid.UUID,
    instance_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    if not await interior_instance_tables_ready(session):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Interior-instance tables are not available yet. Run database migrations first.")
    item = await _require_item(session, item_id)
    target = next((instance for instance in item.interior_instances if instance.id == instance_id), None)
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order design interior instance not found.")
    order = await require_accessible_order(session, order_id=item.order_id)
    source_design = await require_accessible_sub_category_design(
        session,
        admin_id=order.admin_id,
        design_id=item.sub_category_design_id,
    )
    await session.delete(target)
    await session.flush()
    item.interior_instances = [
        instance for instance in list(item.interior_instances or [])
        if instance.id != target.id
    ]
    refresh_order_design_aggregate_snapshots(item=item, source_design=source_design)
    refresh_order_design_snapshot_state(item=item, source_design=source_design)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{item_id}/recompute", response_model=OrderDesignItem)
async def recompute_order_design_snapshot(
    item_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> OrderDesignItem:
    item = await _require_item(session, item_id)
    order = await require_accessible_order(session, order_id=item.order_id)
    source_design = await require_accessible_sub_category_design(
        session,
        admin_id=order.admin_id,
        design_id=item.sub_category_design_id,
    )
    if await sync_order_design_snapshot(session, item=item, order=order, source_design=source_design):
        await session.commit()
    include_interior = await interior_instance_tables_ready(session)
    item = await _require_item(session, item.id)
    return _serialize_item(item, include_interior=include_interior)
