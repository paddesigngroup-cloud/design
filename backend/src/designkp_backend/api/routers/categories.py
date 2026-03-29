from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from designkp_backend.db.dependencies import get_db_session
from designkp_backend.db.models.catalog import Category, Template
from designkp_backend.services.admin_access import require_admin_if_present

router = APIRouter(prefix="/categories", tags=["categories"])


def _normalize_hex_color(value: str | None, fallback: str = "#7A4A2B") -> str:
    raw = str(value or "").strip()
    if not raw:
        return fallback
    normalized = raw if raw.startswith("#") else f"#{raw}"
    if len(normalized) == 7 and normalized.startswith("#") and all(ch in "0123456789ABCDEFabcdef" for ch in normalized[1:]):
        return normalized.upper()
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Category design outline color must be a HEX value like #7A4A2B.")


class CategoryItem(BaseModel):
    id: uuid.UUID
    admin_id: uuid.UUID | None
    temp_id: int
    cat_id: int
    cat_title: str
    design_outline_color: str
    code: str
    title: str
    sort_order: int
    is_system: bool

    model_config = {"from_attributes": True}


class CategoryCreate(BaseModel):
    admin_id: uuid.UUID | None = None
    temp_id: int = Field(ge=1)
    cat_id: int | None = Field(default=None, ge=1)
    cat_title: str = Field(min_length=1, max_length=255)
    design_outline_color: str = Field(default="#7A4A2B", min_length=7, max_length=7)
    sort_order: int | None = Field(default=None, ge=0)
    is_system: bool = False


class CategoryUpdate(BaseModel):
    admin_id: uuid.UUID | None = None
    temp_id: int = Field(ge=1)
    cat_id: int = Field(ge=1)
    cat_title: str = Field(min_length=1, max_length=255)
    design_outline_color: str = Field(default="#7A4A2B", min_length=7, max_length=7)
    sort_order: int = Field(ge=0)
    is_system: bool


def _to_response(item: Category) -> CategoryItem:
    return CategoryItem(
        id=item.id,
        admin_id=item.admin_id,
        temp_id=item.temp_id,
        cat_id=int(item.cat_id or 0),
        cat_title=item.cat_title,
        design_outline_color=_normalize_hex_color(item.design_outline_color),
        code=item.code,
        title=item.title,
        sort_order=int(item.sort_order or 0),
        is_system=bool(item.is_system),
    )


def _category_code(cat_id: int) -> str:
    return f"category_{cat_id}"


async def _next_cat_id(session: AsyncSession) -> int:
    max_id = await session.scalar(select(func.max(Category.cat_id)))
    return int(max_id or 0) + 1


async def _require_accessible_template(session: AsyncSession, temp_id: int, admin_id: uuid.UUID | None) -> Template:
    stmt = select(Template).where(Template.temp_id == temp_id)
    if admin_id is None:
        stmt = stmt.where(Template.admin_id.is_(None))
    else:
        stmt = stmt.where(or_(Template.admin_id.is_(None), Template.admin_id == admin_id))
    template = await session.scalar(stmt)
    if not template:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Template not found for this admin scope.")
    return template


@router.get("", response_model=list[CategoryItem])
async def list_categories(
    admin_id: uuid.UUID | None = Query(default=None),
    temp_id: int | None = Query(default=None, ge=1),
    session: AsyncSession = Depends(get_db_session),
) -> list[CategoryItem]:
    await require_admin_if_present(session, admin_id)
    stmt = (
        select(Category)
        .where(or_(Category.admin_id.is_(None), Category.admin_id == admin_id))
        .order_by(Category.sort_order.asc(), Category.cat_id.asc())
    )
    if temp_id is not None:
        stmt = stmt.where(Category.temp_id == temp_id)
    items = (await session.scalars(stmt)).all()
    return [_to_response(item) for item in items]


@router.post("", response_model=CategoryItem, status_code=status.HTTP_201_CREATED)
async def create_category(payload: CategoryCreate, session: AsyncSession = Depends(get_db_session)) -> CategoryItem:
    await require_admin_if_present(session, payload.admin_id)
    await _require_accessible_template(session, payload.temp_id, payload.admin_id)
    next_id = payload.cat_id or await _next_cat_id(session)
    title = payload.cat_title.strip()
    item = Category(
        admin_id=payload.admin_id,
        temp_id=payload.temp_id,
        cat_id=next_id,
        cat_title=title,
        design_outline_color=_normalize_hex_color(payload.design_outline_color),
        code=_category_code(next_id),
        title=title,
        sort_order=payload.sort_order if payload.sort_order is not None else next_id,
        is_system=payload.is_system,
    )
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return _to_response(item)


@router.patch("/{category_uuid}", response_model=CategoryItem)
async def update_category(
    category_uuid: uuid.UUID,
    payload: CategoryUpdate,
    session: AsyncSession = Depends(get_db_session),
) -> CategoryItem:
    item = await session.get(Category, category_uuid)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found.")
    await require_admin_if_present(session, payload.admin_id)
    await _require_accessible_template(session, payload.temp_id, payload.admin_id)

    title = payload.cat_title.strip()
    item.admin_id = payload.admin_id
    item.temp_id = payload.temp_id
    item.cat_id = payload.cat_id
    item.cat_title = title
    item.design_outline_color = _normalize_hex_color(payload.design_outline_color)
    item.code = _category_code(payload.cat_id)
    item.title = title
    item.sort_order = payload.sort_order
    item.is_system = payload.is_system

    await session.commit()
    await session.refresh(item)
    return _to_response(item)


@router.delete("/{category_uuid}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(category_uuid: uuid.UUID, session: AsyncSession = Depends(get_db_session)) -> Response:
    item = await session.get(Category, category_uuid)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found.")

    await session.delete(item)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
