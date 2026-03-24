from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from designkp_backend.db.dependencies import get_db_session
from designkp_backend.db.models.account import Order, User
from designkp_backend.services.admin_access import require_admin

router = APIRouter(prefix="/orders", tags=["orders"])

OrderStatus = Literal["draft", "designing", "submitted", "archived"]


class OrderItem(BaseModel):
    id: uuid.UUID
    order_name: str
    order_number: str
    status: OrderStatus
    notes: str | None
    submitted_at: datetime
    admin_id: uuid.UUID
    admin_name: str
    user_id: uuid.UUID
    user_name: str


class OrderCreate(BaseModel):
    admin_id: uuid.UUID
    user_id: uuid.UUID
    order_name: str = Field(min_length=1, max_length=255)
    notes: str | None = Field(default=None, max_length=2000)
    status: OrderStatus = "draft"


class OrderUpdate(BaseModel):
    order_name: str = Field(min_length=1, max_length=255)
    notes: str | None = Field(default=None, max_length=2000)
    status: OrderStatus


def _display_name(full_name: str | None, email: str, fallback: str) -> str:
    text = str(full_name or "").strip()
    if text:
        return text
    text = str(email or "").strip()
    if text:
        return text
    return fallback


async def _get_order_with_relations(session: AsyncSession, order_id: uuid.UUID) -> Order | None:
    return await session.scalar(
        select(Order)
        .options(joinedload(Order.admin), joinedload(Order.user))
        .where(Order.id == order_id)
    )


def _to_response(item: Order) -> OrderItem:
    admin = item.admin
    user = item.user
    if not admin or not user:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Order relations are incomplete.")
    return OrderItem(
        id=item.id,
        order_name=str(item.order_name or "").strip(),
        order_number=str(item.order_number or "").strip(),
        status=str(item.status or "draft").strip().lower(),  # type: ignore[arg-type]
        notes=str(item.notes or "").strip() or None,
        submitted_at=item.submitted_at,
        admin_id=item.admin_id,
        admin_name=_display_name(admin.full_name, admin.email, "Admin"),
        user_id=item.user_id,
        user_name=_display_name(user.full_name, user.email, "User"),
    )


async def _require_accessible_user(session: AsyncSession, *, admin_id: uuid.UUID, user_id: uuid.UUID) -> User:
    user = await session.scalar(
        select(User).where(
            and_(
                User.id == user_id,
                User.admin_id == admin_id,
                User.deleted_at.is_(None),
            )
        )
    )
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found for this admin.")
    return user


async def _next_order_number(session: AsyncSession, *, admin_id: uuid.UUID) -> str:
    year = datetime.now(timezone.utc).year
    prefix = f"ORD-{year}-"
    rows = (
        await session.scalars(
            select(Order.order_number)
            .where(
                and_(
                    Order.admin_id == admin_id,
                    Order.order_number.like(f"{prefix}%"),
                )
            )
            .order_by(Order.order_number.desc())
        )
    ).all()
    max_seq = 0
    for value in rows:
        text = str(value or "").strip()
        if not text.startswith(prefix):
            continue
        suffix = text[len(prefix) :]
        if suffix.isdigit():
            max_seq = max(max_seq, int(suffix))
    return f"{prefix}{max_seq + 1:04d}"


@router.get("", response_model=list[OrderItem])
async def list_orders(
    admin_id: uuid.UUID = Query(...),
    session: AsyncSession = Depends(get_db_session),
) -> list[OrderItem]:
    await require_admin(session, admin_id)
    stmt = (
        select(Order)
        .options(joinedload(Order.admin), joinedload(Order.user))
        .where(and_(Order.admin_id == admin_id, Order.deleted_at.is_(None)))
        .order_by(Order.submitted_at.desc(), Order.order_number.asc())
    )
    items = (await session.scalars(stmt)).all()
    return [_to_response(item) for item in items]


@router.post("", response_model=OrderItem, status_code=status.HTTP_201_CREATED)
async def create_order(payload: OrderCreate, session: AsyncSession = Depends(get_db_session)) -> OrderItem:
    await require_admin(session, payload.admin_id)
    await _require_accessible_user(session, admin_id=payload.admin_id, user_id=payload.user_id)

    normalized_name = str(payload.order_name or "").strip()
    if not normalized_name:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Order name is required.")

    for _ in range(5):
        next_number = await _next_order_number(session, admin_id=payload.admin_id)
        duplicate_exists = await session.scalar(
            select(func.count())
            .select_from(Order)
            .where(
                and_(
                    Order.admin_id == payload.admin_id,
                    Order.order_number == next_number,
                )
            )
        )
        if not duplicate_exists:
            item = Order(
                order_name=normalized_name,
                order_number=next_number,
                status=payload.status,
                notes=str(payload.notes or "").strip() or None,
                admin_id=payload.admin_id,
                user_id=payload.user_id,
            )
            session.add(item)
            await session.commit()
            fresh = await _get_order_with_relations(session, item.id)
            if not fresh:
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Created order could not be reloaded.")
            return _to_response(fresh)
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Could not allocate a unique order number.")


@router.patch("/{order_id}", response_model=OrderItem)
async def update_order(
    order_id: uuid.UUID,
    payload: OrderUpdate,
    session: AsyncSession = Depends(get_db_session),
) -> OrderItem:
    item = await session.scalar(
        select(Order)
        .options(joinedload(Order.admin), joinedload(Order.user))
        .where(and_(Order.id == order_id, Order.deleted_at.is_(None)))
    )
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")

    normalized_name = str(payload.order_name or "").strip()
    if not normalized_name:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Order name is required.")

    item.order_name = normalized_name
    item.notes = str(payload.notes or "").strip() or None
    item.status = payload.status

    await session.commit()
    fresh = await _get_order_with_relations(session, item.id)
    if not fresh:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Updated order could not be reloaded.")
    return _to_response(fresh)


@router.delete("/{order_id}", status_code=status.HTTP_204_NO_CONTENT)
async def archive_order(order_id: uuid.UUID, session: AsyncSession = Depends(get_db_session)) -> Response:
    item = await session.scalar(select(Order).where(and_(Order.id == order_id, Order.deleted_at.is_(None))))
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")
    item.status = "archived"
    item.deleted_at = datetime.now(timezone.utc)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
