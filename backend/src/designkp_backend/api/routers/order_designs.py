from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from designkp_backend.db.dependencies import get_db_session
from designkp_backend.db.models.account import OrderDesign
from designkp_backend.services.order_designs import (
    build_order_design_snapshot,
    next_order_design_instance_code,
    next_order_design_sort_order,
    normalize_order_attr_value,
    require_accessible_order,
    require_accessible_sub_category_design,
    sync_order_design_snapshot,
)

router = APIRouter(prefix="/order-designs", tags=["order_designs"])


class OrderDesignItem(BaseModel):
    id: uuid.UUID
    order_id: uuid.UUID
    admin_id: uuid.UUID
    user_id: uuid.UUID
    sub_category_design_id: uuid.UUID
    sub_category_id: uuid.UUID
    design_code: str
    design_title: str
    instance_code: str
    sort_order: int
    status: str
    order_attr_values: dict[str, str | None]
    order_attr_meta: dict[str, dict[str, object]]
    part_snapshots: list[dict[str, object]]
    viewer_boxes: list[dict[str, object]]


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


def _serialize_item(item: OrderDesign) -> OrderDesignItem:
    return OrderDesignItem(
        id=item.id,
        order_id=item.order_id,
        admin_id=item.admin_id,
        user_id=item.user_id,
        sub_category_design_id=item.sub_category_design_id,
        sub_category_id=item.sub_category_id,
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
            for key, value in dict(item.order_attr_meta or {}).items()
        },
        part_snapshots=[dict(row or {}) for row in list(item.part_snapshots or [])],
        viewer_boxes=[dict(row or {}) for row in list(item.viewer_boxes or [])],
    )


async def _require_item(session: AsyncSession, item_id: uuid.UUID) -> OrderDesign:
    item = await session.scalar(select(OrderDesign).where(and_(OrderDesign.id == item_id, OrderDesign.deleted_at.is_(None))))
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order design not found.")
    order = await require_accessible_order(session, order_id=item.order_id)
    if await sync_order_design_snapshot(session, item=item, order=order):
        await session.commit()
        await session.refresh(item)
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


def _normalize_attr_values(
    raw_values: dict[str, str | int | float | bool | None],
    current_meta: dict[str, dict[str, object]],
) -> dict[str, str | None]:
    normalized: dict[str, str | None] = {}
    for key, meta in current_meta.items():
        input_mode = "binary" if str(meta.get("input_mode") or "") == "binary" else "value"
        next_value = raw_values[key] if key in raw_values else None
        normalized[key] = normalize_order_attr_value(next_value, input_mode=input_mode)
    return normalized


@router.get("", response_model=list[OrderDesignItem])
async def list_order_designs(
    order_id: uuid.UUID = Query(...),
    session: AsyncSession = Depends(get_db_session),
) -> list[OrderDesignItem]:
    order = await require_accessible_order(session, order_id=order_id)
    items = (
        await session.scalars(
            select(OrderDesign)
            .where(and_(OrderDesign.order_id == order_id, OrderDesign.deleted_at.is_(None)))
            .order_by(OrderDesign.sort_order.asc(), OrderDesign.instance_code.asc())
        )
    ).all()
    changed = False
    for item in items:
        changed = (await sync_order_design_snapshot(session, item=item, order=order)) or changed
    if changed:
        await session.commit()
    return [_serialize_item(item) for item in items]


@router.post("", response_model=OrderDesignItem, status_code=status.HTTP_201_CREATED)
async def create_order_design(payload: OrderDesignCreate, session: AsyncSession = Depends(get_db_session)) -> OrderDesignItem:
    order = await require_accessible_order(session, order_id=payload.order_id)
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
        order_attr_meta=snapshot["order_attr_meta"],
        part_snapshots=snapshot["part_snapshots"],
        viewer_boxes=snapshot["viewer_boxes"],
    )
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return _serialize_item(item)


@router.patch("/{item_id}", response_model=OrderDesignItem)
async def update_order_design(
    item_id: uuid.UUID,
    payload: OrderDesignUpdate,
    session: AsyncSession = Depends(get_db_session),
) -> OrderDesignItem:
    item = await _require_item(session, item_id)
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
    )
    item.design_title = title
    item.instance_code = instance_code
    item.sort_order = payload.sort_order
    item.status = str(payload.status or "draft").strip() or "draft"
    item.order_attr_values = snapshot["order_attr_values"]
    item.order_attr_meta = snapshot["order_attr_meta"]
    item.part_snapshots = snapshot["part_snapshots"]
    item.viewer_boxes = snapshot["viewer_boxes"]
    await session.commit()
    await session.refresh(item)
    return _serialize_item(item)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_order_design(item_id: uuid.UUID, session: AsyncSession = Depends(get_db_session)) -> Response:
    item = await _require_item(session, item_id)
    await session.delete(item)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
