from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from designkp_backend.db.dependencies import get_db_session
from designkp_backend.db.models.catalog import Category, Param, SubCategory, SubCategoryDesign, SubCategoryParamDefault, Template
from designkp_backend.services.admin_access import require_admin_if_present
from designkp_backend.services.admin_storage import admin_icon_exists, finalize_param_group_icon, normalize_icon_file_name
from designkp_backend.services.sub_category_defaults import get_params_for_scope, normalize_default_value, sync_defaults_for_sub_categories

router = APIRouter(prefix="/sub-categories", tags=["sub_categories"])


def _normalize_hex_color(value: str | None, fallback: str = "#7A4A2B") -> str:
    raw = str(value or "").strip()
    if not raw:
        return fallback
    normalized = raw if raw.startswith("#") else f"#{raw}"
    if len(normalized) == 7 and normalized.startswith("#") and all(ch in "0123456789ABCDEFabcdef" for ch in normalized[1:]):
        return normalized.upper()
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Sub-category design outline color must be a HEX value like #7A4A2B.")


class SubCategoryItem(BaseModel):
    id: uuid.UUID
    admin_id: uuid.UUID | None
    temp_id: int
    cat_id: int
    sub_cat_id: int
    sub_cat_title: str
    design_outline_color: str
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
    design_outline_color: str = Field(default="#7A4A2B", min_length=7, max_length=7)
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
    design_outline_color: str = Field(default="#7A4A2B", min_length=7, max_length=7)
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


async def _resolve_available_sub_cat_id(
    session: AsyncSession,
    requested_id: int | None,
    *,
    exclude_uuid: uuid.UUID | None = None,
) -> int:
    candidate = int(requested_id or 0)
    if candidate >= 1:
        stmt = select(SubCategory.id).where(SubCategory.sub_cat_id == candidate)
        if exclude_uuid is not None:
            stmt = stmt.where(SubCategory.id != exclude_uuid)
        existing = await session.scalar(stmt.limit(1))
        if not existing:
            return candidate
    return await _next_sub_cat_id(session)


def _deleted_sub_category_code(code: str, item_id: uuid.UUID) -> str:
    suffix = f"__deleted__{str(item_id).replace('-', '')[:12]}"
    base = (code or "sub_category").strip() or "sub_category"
    max_base_len = max(1, 64 - len(suffix))
    return f"{base[:max_base_len]}{suffix}"


def _deleted_sub_category_title(title: str, item_id: uuid.UUID) -> str:
    suffix = f" [deleted {str(item_id).replace('-', '')[:8]}]"
    base = (title or "ساب‌کت حذف‌شده").strip() or "ساب‌کت حذف‌شده"
    max_base_len = max(1, 255 - len(suffix))
    return f"{base[:max_base_len]}{suffix}"


def _sub_category_integrity_message(exc: IntegrityError) -> str:
    text = str(getattr(exc, "orig", exc))
    if "uq_sub_categories_sub_cat_id" in text:
        return "شناسه ساب‌کت تکراری است."
    if "uq_sub_categories_system_title" in text or "uq_sub_categories_admin_title" in text:
        return "عنوان ساب‌کت در همین دسته و همین مالک تکراری است."
    return "ذخیره ساب‌کت به‌دلیل تداخل داده انجام نشد."


async def _release_deleted_sub_category_title_conflicts(
    session: AsyncSession,
    *,
    admin_id: uuid.UUID | None,
    cat_id: int,
    title: str,
    exclude_uuid: uuid.UUID | None = None,
) -> None:
    normalized_title = str(title or "").strip()
    if not normalized_title:
        return
    stmt = select(SubCategory).where(
        and_(
            SubCategory.cat_id == cat_id,
            SubCategory.sub_cat_title == normalized_title,
            SubCategory.deleted_at.is_not(None),
        )
    )
    if admin_id is None:
        stmt = stmt.where(SubCategory.admin_id.is_(None))
    else:
        stmt = stmt.where(SubCategory.admin_id == admin_id)
    if exclude_uuid is not None:
        stmt = stmt.where(SubCategory.id != exclude_uuid)
    items = (await session.scalars(stmt)).all()
    for row in items:
        next_title = _deleted_sub_category_title(row.sub_cat_title, row.id)
        row.sub_cat_title = next_title
        row.title = next_title


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
            design_outline_color=_normalize_hex_color(item.design_outline_color),
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
            .where(
                and_(
                    or_(SubCategory.admin_id.is_(None), SubCategory.admin_id == admin_id),
                    SubCategory.deleted_at.is_(None),
                )
            )
            .order_by(SubCategory.sort_order.asc(), SubCategory.sub_cat_id.asc())
        )
    ).all()
    return await _serialize_items(session, items, admin_id)


@router.post("", response_model=SubCategoryItem, status_code=status.HTTP_201_CREATED)
async def create_sub_category(payload: SubCategoryCreate, session: AsyncSession = Depends(get_db_session)) -> SubCategoryItem:
    await require_admin_if_present(session, payload.admin_id)
    await _require_accessible_template(session, payload.temp_id, payload.admin_id)
    await _require_accessible_category(session, temp_id=payload.temp_id, cat_id=payload.cat_id, admin_id=payload.admin_id)
    next_id = await _resolve_available_sub_cat_id(session, payload.sub_cat_id)
    title = payload.sub_cat_title.strip()
    await _release_deleted_sub_category_title_conflicts(
        session,
        admin_id=payload.admin_id,
        cat_id=payload.cat_id,
        title=title,
    )
    item = SubCategory(
        admin_id=payload.admin_id,
        temp_id=payload.temp_id,
        cat_id=payload.cat_id,
        sub_cat_id=next_id,
        sub_cat_title=title,
        design_outline_color=_normalize_hex_color(payload.design_outline_color),
        code=_sub_category_code(next_id),
        title=title,
        sort_order=payload.sort_order if payload.sort_order is not None else next_id,
        is_system=payload.is_system,
    )
    session.add(item)
    try:
        await session.flush()
        await _apply_param_defaults(session, item, payload.param_defaults, payload.param_overrides)
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=_sub_category_integrity_message(exc)) from exc
    await session.refresh(item)
    return (await _serialize_items(session, [item], payload.admin_id))[0]


@router.patch("/{sub_category_uuid}", response_model=SubCategoryItem)
async def update_sub_category(
    sub_category_uuid: uuid.UUID,
    payload: SubCategoryUpdate,
    session: AsyncSession = Depends(get_db_session),
) -> SubCategoryItem:
    item = await session.get(SubCategory, sub_category_uuid)
    if not item or item.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sub-category not found.")
    await require_admin_if_present(session, payload.admin_id)
    await _require_accessible_template(session, payload.temp_id, payload.admin_id)
    await _require_accessible_category(session, temp_id=payload.temp_id, cat_id=payload.cat_id, admin_id=payload.admin_id)
    next_sub_cat_id = await _resolve_available_sub_cat_id(session, payload.sub_cat_id, exclude_uuid=item.id)
    title = payload.sub_cat_title.strip()
    await _release_deleted_sub_category_title_conflicts(
        session,
        admin_id=payload.admin_id,
        cat_id=payload.cat_id,
        title=title,
        exclude_uuid=item.id,
    )
    item.admin_id = payload.admin_id
    item.temp_id = payload.temp_id
    item.cat_id = payload.cat_id
    item.sub_cat_id = next_sub_cat_id
    item.sub_cat_title = title
    item.design_outline_color = _normalize_hex_color(payload.design_outline_color)
    item.code = _sub_category_code(next_sub_cat_id)
    item.title = title
    item.sort_order = payload.sort_order
    item.is_system = payload.is_system
    try:
        await _apply_param_defaults(session, item, payload.param_defaults, payload.param_overrides)
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=_sub_category_integrity_message(exc)) from exc
    await session.refresh(item)
    return (await _serialize_items(session, [item], payload.admin_id))[0]


@router.delete("/{sub_category_uuid}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_sub_category(sub_category_uuid: uuid.UUID, session: AsyncSession = Depends(get_db_session)) -> Response:
    item = await session.get(SubCategory, sub_category_uuid)
    if not item or item.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sub-category not found.")
    deleted_at = datetime.now(timezone.utc)
    item.deleted_at = deleted_at
    item.sub_cat_id = None
    item.code = _deleted_sub_category_code(item.code, item.id)
    next_title = _deleted_sub_category_title(item.sub_cat_title, item.id)
    item.sub_cat_title = next_title
    item.title = next_title
    designs = (
        await session.scalars(
            select(SubCategoryDesign).where(
                and_(
                    SubCategoryDesign.sub_category_id == sub_category_uuid,
                    SubCategoryDesign.deleted_at.is_(None),
                )
            )
        )
    ).all()
    for design in designs:
        design.deleted_at = deleted_at
        design.design_id = None
        design.code = f"{(design.code or 'design')[:41]}__deleted__{str(design.id).replace('-', '')[:12]}"
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
