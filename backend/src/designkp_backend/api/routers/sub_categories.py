from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from designkp_backend.db.dependencies import get_db_session
from designkp_backend.db.models.catalog import Category, Param, SubCategory, SubCategoryParamDefault, Template
from designkp_backend.services.admin_access import require_admin_if_present
from designkp_backend.services.admin_storage import admin_icon_exists, finalize_param_group_icon, normalize_icon_file_name
from designkp_backend.services.sub_category_defaults import get_params_for_scope, normalize_default_value, sync_defaults_for_sub_categories

router = APIRouter(prefix="/sub-categories", tags=["sub_categories"])


class SubCategoryItem(BaseModel):
    id: uuid.UUID
    admin_id: uuid.UUID | None
    temp_id: int
    cat_id: int
    sub_cat_id: int
    sub_cat_title: str
    code: str
    title: str
    sort_order: int
    is_system: bool
    param_defaults: dict[str, str | None]
    param_overrides: dict[str, "SubCategoryParamOverrideItem"]

    model_config = {"from_attributes": True}


class SubCategoryParamOverrideItem(BaseModel):
    display_title: str | None = None
    description_text: str | None = None
    icon_path: str | None = None
    input_mode: str = "value"
    binary_off_label: str | None = None
    binary_on_label: str | None = None
    binary_off_icon_path: str | None = None
    binary_on_icon_path: str | None = None


class SubCategoryCreate(BaseModel):
    admin_id: uuid.UUID | None = None
    temp_id: int = Field(ge=1)
    cat_id: int = Field(ge=1)
    sub_cat_id: int | None = Field(default=None, ge=1)
    sub_cat_title: str = Field(min_length=1, max_length=255)
    sort_order: int | None = Field(default=None, ge=0)
    is_system: bool = False
    param_defaults: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
    param_overrides: dict[str, "SubCategoryParamOverridePayload"] = Field(default_factory=dict)


class SubCategoryUpdate(BaseModel):
    admin_id: uuid.UUID | None = None
    temp_id: int = Field(ge=1)
    cat_id: int = Field(ge=1)
    sub_cat_id: int = Field(ge=1)
    sub_cat_title: str = Field(min_length=1, max_length=255)
    sort_order: int = Field(ge=0)
    is_system: bool
    param_defaults: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
    param_overrides: dict[str, "SubCategoryParamOverridePayload"] = Field(default_factory=dict)


class SubCategoryParamOverridePayload(BaseModel):
    display_title: str | None = Field(default=None, max_length=255)
    description_text: str | None = Field(default=None, max_length=4000)
    icon_path: str | None = Field(default=None, max_length=255)
    input_mode: str = Field(default="value", pattern="^(value|binary)$")
    binary_off_label: str | None = Field(default=None, max_length=255)
    binary_on_label: str | None = Field(default=None, max_length=255)
    binary_off_icon_path: str | None = Field(default=None, max_length=255)
    binary_on_icon_path: str | None = Field(default=None, max_length=255)


def _sub_category_code(sub_cat_id: int) -> str:
    return f"sub_category_{sub_cat_id}"


async def _next_sub_cat_id(session: AsyncSession) -> int:
    max_id = await session.scalar(select(func.max(SubCategory.sub_cat_id)))
    return int(max_id or 0) + 1


async def _require_accessible_category(
    session: AsyncSession,
    *,
    temp_id: int,
    cat_id: int,
    admin_id: uuid.UUID | None,
) -> Category:
    stmt = select(Category).where(Category.temp_id == temp_id, Category.cat_id == cat_id)
    if admin_id is None:
        stmt = stmt.where(Category.admin_id.is_(None))
    else:
        stmt = stmt.where(or_(Category.admin_id.is_(None), Category.admin_id == admin_id))
    category = await session.scalar(stmt)
    if not category:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Category not found for this admin scope.")
    return category


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


async def _allowed_params_by_code(session: AsyncSession, admin_id: uuid.UUID | None) -> dict[str, Param]:
    params = await get_params_for_scope(session, admin_id)
    return {item.param_code: item for item in params}


async def _apply_param_defaults(
    session: AsyncSession,
    item: SubCategory,
    param_defaults: dict[str, str | int | float | bool | None],
    param_overrides: dict[str, SubCategoryParamOverridePayload],
) -> None:
    await sync_defaults_for_sub_categories(session, [item])
    params_by_code = await _allowed_params_by_code(session, item.admin_id)
    defaults = (
        await session.scalars(
            select(SubCategoryParamDefault).where(SubCategoryParamDefault.sub_category_id == item.id)
        )
    ).all()
    defaults_by_param_id = {row.param_id: row for row in defaults}

    for param_code, raw_value in param_defaults.items():
        param = params_by_code.get(param_code)
        if not param:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown param code for this sub-category scope: {param_code}")
        defaults_by_param_id[param.param_id].default_value = normalize_default_value(raw_value)
    for param_code, override in param_overrides.items():
        param = params_by_code.get(param_code)
        if not param:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown param code for this sub-category scope: {param_code}")
        row = defaults_by_param_id[param.param_id]
        next_icon = normalize_icon_file_name(override.icon_path)
        next_binary_off_icon = normalize_icon_file_name(override.binary_off_icon_path)
        next_binary_on_icon = normalize_icon_file_name(override.binary_on_icon_path)
        if item.admin_id:
            next_icon = finalize_param_group_icon(item.admin_id, next_icon, previous_file_name=row.icon_path)
            next_binary_off_icon = finalize_param_group_icon(
                item.admin_id,
                next_binary_off_icon,
                previous_file_name=row.binary_off_icon_path,
            )
            next_binary_on_icon = finalize_param_group_icon(
                item.admin_id,
                next_binary_on_icon,
                previous_file_name=row.binary_on_icon_path,
            )
        row.display_title = (override.display_title or "").strip() or param.param_title_fa.strip()
        row.description_text = (override.description_text or "").strip() or None
        row.icon_path = next_icon
        row.input_mode = override.input_mode if override.input_mode in {"value", "binary"} else "value"
        row.binary_off_label = (override.binary_off_label or "").strip() or "0"
        row.binary_on_label = (override.binary_on_label or "").strip() or "1"
        row.binary_off_icon_path = next_binary_off_icon
        row.binary_on_icon_path = next_binary_on_icon
        if row.input_mode == "binary":
            normalized_value = normalize_default_value(param_defaults.get(param_code))
            row.default_value = normalized_value if normalized_value in {"0", "1"} else "0"


async def _serialize_items(session: AsyncSession, items: list[SubCategory], admin_id: uuid.UUID | None) -> list[SubCategoryItem]:
    await sync_defaults_for_sub_categories(session, items)
    params = await get_params_for_scope(session, admin_id)
    code_by_param_id = {item.param_id: item.param_code for item in params}
    admin_id_by_sub_category_id = {item.id: item.admin_id for item in items}
    sub_category_ids = [item.id for item in items]
    defaults = []
    if sub_category_ids:
        defaults = (
            await session.scalars(
                select(SubCategoryParamDefault).where(SubCategoryParamDefault.sub_category_id.in_(sub_category_ids))
            )
        ).all()
    defaults_map: dict[uuid.UUID, dict[str, str | None]] = {item.id: {} for item in items}
    overrides_map: dict[uuid.UUID, dict[str, SubCategoryParamOverrideItem]] = {item.id: {} for item in items}
    for row in defaults:
        code = code_by_param_id.get(row.param_id)
        if code:
            icon_path = normalize_icon_file_name(row.icon_path)
            binary_off_icon_path = normalize_icon_file_name(row.binary_off_icon_path)
            binary_on_icon_path = normalize_icon_file_name(row.binary_on_icon_path)
            row_admin_id = admin_id_by_sub_category_id.get(row.sub_category_id)
            if row_admin_id and icon_path and not admin_icon_exists(row_admin_id, icon_path):
                icon_path = None
            if row_admin_id and binary_off_icon_path and not admin_icon_exists(row_admin_id, binary_off_icon_path):
                binary_off_icon_path = None
            if row_admin_id and binary_on_icon_path and not admin_icon_exists(row_admin_id, binary_on_icon_path):
                binary_on_icon_path = None
            defaults_map.setdefault(row.sub_category_id, {})[code] = row.default_value
            overrides_map.setdefault(row.sub_category_id, {})[code] = SubCategoryParamOverrideItem(
                display_title=row.display_title,
                description_text=row.description_text,
                icon_path=icon_path,
                input_mode=row.input_mode if row.input_mode in {"value", "binary"} else "value",
                binary_off_label=(row.binary_off_label or "0").strip() or "0",
                binary_on_label=(row.binary_on_label or "1").strip() or "1",
                binary_off_icon_path=binary_off_icon_path,
                binary_on_icon_path=binary_on_icon_path,
            )
    return [
        SubCategoryItem(
            id=item.id,
            admin_id=item.admin_id,
            temp_id=item.temp_id,
            cat_id=item.cat_id,
            sub_cat_id=item.sub_cat_id,
            sub_cat_title=item.sub_cat_title,
            code=item.code,
            title=item.title,
            sort_order=item.sort_order,
            is_system=item.is_system,
            param_defaults=defaults_map.get(item.id, {}),
            param_overrides=overrides_map.get(item.id, {}),
        )
        for item in items
    ]


@router.get("", response_model=list[SubCategoryItem])
async def list_sub_categories(
    admin_id: uuid.UUID | None = Query(default=None),
    session: AsyncSession = Depends(get_db_session),
) -> list[SubCategoryItem]:
    await require_admin_if_present(session, admin_id)
    items = (
        await session.scalars(
            select(SubCategory)
            .where(or_(SubCategory.admin_id.is_(None), SubCategory.admin_id == admin_id))
            .order_by(SubCategory.sort_order.asc(), SubCategory.sub_cat_id.asc())
        )
    ).all()
    return await _serialize_items(session, items, admin_id)


@router.post("", response_model=SubCategoryItem, status_code=status.HTTP_201_CREATED)
async def create_sub_category(payload: SubCategoryCreate, session: AsyncSession = Depends(get_db_session)) -> SubCategoryItem:
    await require_admin_if_present(session, payload.admin_id)
    await _require_accessible_template(session, payload.temp_id, payload.admin_id)
    await _require_accessible_category(session, temp_id=payload.temp_id, cat_id=payload.cat_id, admin_id=payload.admin_id)
    next_id = payload.sub_cat_id or await _next_sub_cat_id(session)
    title = payload.sub_cat_title.strip()
    item = SubCategory(
        admin_id=payload.admin_id,
        temp_id=payload.temp_id,
        cat_id=payload.cat_id,
        sub_cat_id=next_id,
        sub_cat_title=title,
        code=_sub_category_code(next_id),
        title=title,
        sort_order=payload.sort_order if payload.sort_order is not None else next_id,
        is_system=payload.is_system,
    )
    session.add(item)
    await session.flush()
    await _apply_param_defaults(session, item, payload.param_defaults, payload.param_overrides)
    await session.commit()
    await session.refresh(item)
    return (await _serialize_items(session, [item], payload.admin_id))[0]


@router.patch("/{sub_category_uuid}", response_model=SubCategoryItem)
async def update_sub_category(
    sub_category_uuid: uuid.UUID,
    payload: SubCategoryUpdate,
    session: AsyncSession = Depends(get_db_session),
) -> SubCategoryItem:
    item = await session.get(SubCategory, sub_category_uuid)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sub-category not found.")
    await require_admin_if_present(session, payload.admin_id)
    await _require_accessible_template(session, payload.temp_id, payload.admin_id)
    await _require_accessible_category(session, temp_id=payload.temp_id, cat_id=payload.cat_id, admin_id=payload.admin_id)
    title = payload.sub_cat_title.strip()
    item.admin_id = payload.admin_id
    item.temp_id = payload.temp_id
    item.cat_id = payload.cat_id
    item.sub_cat_id = payload.sub_cat_id
    item.sub_cat_title = title
    item.code = _sub_category_code(payload.sub_cat_id)
    item.title = title
    item.sort_order = payload.sort_order
    item.is_system = payload.is_system
    await _apply_param_defaults(session, item, payload.param_defaults, payload.param_overrides)
    await session.commit()
    await session.refresh(item)
    return (await _serialize_items(session, [item], payload.admin_id))[0]


@router.delete("/{sub_category_uuid}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_sub_category(sub_category_uuid: uuid.UUID, session: AsyncSession = Depends(get_db_session)) -> Response:
    item = await session.get(SubCategory, sub_category_uuid)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sub-category not found.")
    await session.delete(item)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
