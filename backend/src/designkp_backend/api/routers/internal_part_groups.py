from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from designkp_backend.db.dependencies import get_db_session
from designkp_backend.db.models.catalog import (
    InternalPartGroup,
    InternalPartGroupItem,
    InternalPartGroupParamDefault,
    InternalPartGroupParamGroup,
    Param,
    ParamGroup,
    PartFormula,
    PartKind,
    SubCategory,
    SubCategoryParamDefault,
)
from designkp_backend.services.admin_access import require_admin_if_present
from designkp_backend.services.admin_storage import normalize_icon_file_name
from designkp_backend.services.sub_category_defaults import normalize_default_value

router = APIRouter(prefix="/internal-part-groups", tags=["internal_part_groups"])
DEFAULT_INTERNAL_LINE_COLOR = "#8A98A3"
INTERNAL_GROUP_CONTROLLER_TYPE_WIDTH = "width_controler_internal_group_parts"
INTERNAL_GROUP_CONTROLLER_TYPE_WIDTH_RIGHT = "width_controler_internal_group_parts_right"
INTERNAL_GROUP_CONTROLLER_TYPE_WIDTH_LEFT = "width_controler_internal_group_parts_left"
INTERNAL_GROUP_CONTROLLER_TYPE_WIDTH_NO_TOP = "width_controller_internal_group_part"
INTERNAL_GROUP_CONTROLLER_TYPE_WIDTH_NO_TOP_RIGHT = "width_controller_internal_group_part_right"
INTERNAL_GROUP_CONTROLLER_TYPE_WIDTH_NO_TOP_LEFT = "width_controller_internal_group_part_left"
INTERNAL_GROUP_CONTROLLER_TYPE_HEIGHT_RIGHT = "height_controller_internal_group_part"
INTERNAL_GROUP_CONTROLLER_TYPE_HEIGHT_LEFT = "height_controller_internal_group_part_left"
INTERNAL_GROUP_CONTROLLER_SLOTS_BY_TYPE = {
    INTERNAL_GROUP_CONTROLLER_TYPE_WIDTH: ("left", "top", "right", "bottom_offset"),
    INTERNAL_GROUP_CONTROLLER_TYPE_WIDTH_RIGHT: ("left", "top", "right", "bottom_offset"),
    INTERNAL_GROUP_CONTROLLER_TYPE_WIDTH_LEFT: ("left", "top", "right", "bottom_offset"),
    INTERNAL_GROUP_CONTROLLER_TYPE_WIDTH_NO_TOP: ("left", "top", "right", "bottom_offset"),
    INTERNAL_GROUP_CONTROLLER_TYPE_WIDTH_NO_TOP_RIGHT: ("left", "top", "right", "bottom_offset"),
    INTERNAL_GROUP_CONTROLLER_TYPE_WIDTH_NO_TOP_LEFT: ("left", "top", "right", "bottom_offset"),
    INTERNAL_GROUP_CONTROLLER_TYPE_HEIGHT_RIGHT: ("left", "top", "right", "bottom_offset"),
    INTERNAL_GROUP_CONTROLLER_TYPE_HEIGHT_LEFT: ("left", "top", "right", "bottom_offset"),
}


def _normalize_hex_color(value: str | None, fallback: str = DEFAULT_INTERNAL_LINE_COLOR) -> str:
    raw = str(value or "").strip()
    if not raw:
        return fallback
    normalized = raw if raw.startswith("#") else f"#{raw}"
    if not normalized or len(normalized) != 7:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Internal part group line color must be a HEX value like #8A98A3.",
        )
    if not all(ch in "0123456789ABCDEFabcdef#" for ch in normalized):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Internal part group line color must be a HEX value like #8A98A3.",
        )
    return normalized.upper()


class InternalPartGroupPartSelectionPayload(BaseModel):
    part_formula_id: int = Field(ge=1)
    enabled: bool = True
    ui_order: int = Field(default=0, ge=0)


class InternalPartGroupPartItem(BaseModel):
    id: uuid.UUID
    part_formula_id: int
    part_kind_id: int
    part_code: str
    part_title: str
    enabled: bool
    ui_order: int

    model_config = {"from_attributes": True}


class InternalPartGroupParamGroupSelectionPayload(BaseModel):
    param_group_id: int = Field(ge=1)
    enabled: bool = True
    ui_order: int = Field(default=0, ge=0)


class InternalPartGroupParamGroupItem(BaseModel):
    id: uuid.UUID
    param_group_id: int
    param_group_code: str
    param_group_title: str
    param_group_icon_path: str | None = None
    enabled: bool
    ui_order: int

    model_config = {"from_attributes": True}


class InternalPartGroupItemResponse(BaseModel):
    id: uuid.UUID
    admin_id: uuid.UUID | None
    group_id: int
    group_title: str
    code: str
    title: str
    line_color: str
    sort_order: int
    is_system: bool
    parts: list[InternalPartGroupPartItem]
    param_groups: list[InternalPartGroupParamGroupItem]
    param_defaults: dict[str, str | None]
    param_overrides: dict[str, "InternalPartGroupParamOverrideItem"]
    controller_type: str | None = None
    controller_bindings: dict[str, "InternalPartGroupControllerBindingItem"]

    model_config = {"from_attributes": True}


class InternalPartGroupParamOverrideItem(BaseModel):
    display_title: str | None = None
    description_text: str | None = None
    icon_path: str | None = None
    input_mode: str = "value"
    binary_off_label: str | None = None
    binary_on_label: str | None = None
    binary_off_icon_path: str | None = None
    binary_on_icon_path: str | None = None


class InternalPartGroupControllerBindingItem(BaseModel):
    param_code: str | None = None


class InternalPartGroupCreate(BaseModel):
    admin_id: uuid.UUID | None = None
    group_id: int | None = Field(default=None, ge=1)
    group_title: str = Field(min_length=1, max_length=255)
    code: str = Field(min_length=1, max_length=64)
    line_color: str = Field(default=DEFAULT_INTERNAL_LINE_COLOR, min_length=7, max_length=7)
    sort_order: int | None = Field(default=None, ge=0)
    is_system: bool = False
    parts: list[InternalPartGroupPartSelectionPayload] = Field(default_factory=list)
    param_groups: list[InternalPartGroupParamGroupSelectionPayload] = Field(default_factory=list)
    param_defaults: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
    param_overrides: dict[str, "InternalPartGroupParamOverridePayload"] = Field(default_factory=dict)
    controller_type: str | None = Field(default=None, max_length=128)
    controller_bindings: dict[str, "InternalPartGroupControllerBindingPayload"] = Field(default_factory=dict)


class InternalPartGroupUpdate(BaseModel):
    admin_id: uuid.UUID | None = None
    group_id: int = Field(ge=1)
    group_title: str = Field(min_length=1, max_length=255)
    code: str = Field(min_length=1, max_length=64)
    line_color: str = Field(default=DEFAULT_INTERNAL_LINE_COLOR, min_length=7, max_length=7)
    sort_order: int = Field(ge=0)
    is_system: bool
    parts: list[InternalPartGroupPartSelectionPayload] = Field(default_factory=list)
    param_groups: list[InternalPartGroupParamGroupSelectionPayload] = Field(default_factory=list)
    param_defaults: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
    param_overrides: dict[str, "InternalPartGroupParamOverridePayload"] = Field(default_factory=dict)
    controller_type: str | None = Field(default=None, max_length=128)
    controller_bindings: dict[str, "InternalPartGroupControllerBindingPayload"] = Field(default_factory=dict)


class InternalPartGroupParamOverridePayload(BaseModel):
    display_title: str | None = Field(default=None, max_length=255)
    description_text: str | None = Field(default=None, max_length=4000)
    icon_path: str | None = Field(default=None, max_length=255)
    input_mode: str = Field(default="value", pattern="^(value|binary)$")
    binary_off_label: str | None = Field(default=None, max_length=255)
    binary_on_label: str | None = Field(default=None, max_length=255)
    binary_off_icon_path: str | None = Field(default=None, max_length=255)
    binary_on_icon_path: str | None = Field(default=None, max_length=255)


class InternalPartGroupControllerBindingPayload(BaseModel):
    param_code: str | None = Field(default=None, max_length=128)


InternalPartGroupItemResponse.model_rebuild()


async def _next_group_id(session: AsyncSession) -> int:
    max_id = await session.scalar(select(func.max(InternalPartGroup.group_id)))
    return int(max_id or 0) + 1


async def internal_part_group_param_groups_table_ready(session: AsyncSession) -> bool:
    result = await session.execute(select(func.to_regclass("internal_part_group_param_groups")))
    return bool(result.one()[0])


async def internal_part_group_param_defaults_table_ready(session: AsyncSession) -> bool:
    result = await session.execute(select(func.to_regclass("internal_part_group_param_defaults")))
    return bool(result.one()[0])


def _normalize_controller_type(value: str | None) -> str | None:
    normalized = str(value or "").strip()
    return normalized or None


def _normalize_optional_string(value: object) -> str | None:
    normalized = str(value or "").strip()
    return normalized or None


def _normalize_controller_bindings_payload(
    controller_type: str | None,
    bindings: dict[str, InternalPartGroupControllerBindingPayload] | dict[str, object] | None,
) -> dict[str, dict[str, str | None]]:
    normalized_type = _normalize_controller_type(controller_type)
    if not normalized_type:
        return {}
    allowed_slots = INTERNAL_GROUP_CONTROLLER_SLOTS_BY_TYPE.get(normalized_type)
    if not allowed_slots:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unsupported internal group controller type: {normalized_type}")
    raw_bindings = dict(bindings or {})
    invalid_slots = sorted(str(key or "").strip() for key in raw_bindings if str(key or "").strip() not in allowed_slots)
    if invalid_slots:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported controller bindings for {normalized_type}: {', '.join(invalid_slots)}",
        )
    normalized: dict[str, dict[str, str | None]] = {}
    for slot in allowed_slots:
        raw_value = raw_bindings.get(slot)
        if isinstance(raw_value, InternalPartGroupControllerBindingPayload):
            param_code = _normalize_optional_string(raw_value.param_code)
        elif isinstance(raw_value, dict):
            param_code = _normalize_optional_string(raw_value.get("param_code"))
        else:
            param_code = None
        normalized[slot] = {"param_code": param_code}
    return normalized


async def _ensure_unique_group_code(session: AsyncSession, *, code: str, exclude_id: uuid.UUID | None = None) -> None:
    stmt = select(InternalPartGroup).where(InternalPartGroup.code == code)
    if exclude_id is not None:
        stmt = stmt.where(InternalPartGroup.id != exclude_id)
    duplicate = await session.scalar(stmt)
    if duplicate:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Internal part group code is already used.")


async def _load_group(
    session: AsyncSession,
    group_uuid: uuid.UUID,
    *,
    include_param_groups: bool | None = None,
    include_param_defaults: bool | None = None,
) -> InternalPartGroup:
    if include_param_groups is None:
        include_param_groups = await internal_part_group_param_groups_table_ready(session)
    if include_param_defaults is None:
        include_param_defaults = await internal_part_group_param_defaults_table_ready(session)
    stmt = select(InternalPartGroup).options(selectinload(InternalPartGroup.parts))
    if include_param_groups:
        stmt = stmt.options(selectinload(InternalPartGroup.param_groups))
    if include_param_defaults:
        stmt = stmt.options(selectinload(InternalPartGroup.param_defaults).selectinload(InternalPartGroupParamDefault.param))
    item = await session.scalar(stmt.where(InternalPartGroup.id == group_uuid))
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Internal part group not found.")
    return item


def _serialize_group(
    item: InternalPartGroup,
    *,
    include_param_groups: bool = True,
    include_param_defaults: bool = True,
) -> InternalPartGroupItemResponse:
    defaults_map: dict[str, str | None] = {}
    for row in sorted(
        item.param_defaults if include_param_defaults else [],
        key=lambda current: int(current.param_id),
    ):
        param_code = getattr(getattr(row, "param", None), "param_code", None)
        if not param_code:
            continue
        defaults_map[str(param_code)] = row.default_value
    controller_type = _normalize_controller_type(getattr(item, "controller_type", None))
    controller_bindings = _normalize_controller_bindings_payload(
        controller_type,
        getattr(item, "controller_bindings", None),
    )
    return InternalPartGroupItemResponse(
        id=item.id,
        admin_id=item.admin_id,
        group_id=int(item.group_id or 0),
        group_title=item.group_title,
        code=item.code,
        title=item.title,
        line_color=_normalize_hex_color(getattr(item, "line_color", DEFAULT_INTERNAL_LINE_COLOR), DEFAULT_INTERNAL_LINE_COLOR),
        sort_order=item.sort_order,
        is_system=item.is_system,
        parts=[
            InternalPartGroupPartItem.model_validate(part)
            for part in sorted(item.parts, key=lambda part: (int(part.ui_order), int(part.part_formula_id)))
        ],
        param_groups=[
            InternalPartGroupParamGroupItem.model_validate(param_group)
            for param_group in sorted(item.param_groups, key=lambda row: (int(row.ui_order), int(row.param_group_id)))
        ] if include_param_groups else [],
        param_defaults=defaults_map,
        param_overrides={},
        controller_type=controller_type,
        controller_bindings=controller_bindings,
    )


async def _require_accessible_internal_part_formulas(
    session: AsyncSession,
    *,
    admin_id: uuid.UUID | None,
    part_formula_ids: list[int],
) -> list[PartFormula]:
    if not part_formula_ids:
        return []
    stmt = (
        select(PartFormula)
        .join(PartKind, PartKind.part_kind_id == PartFormula.part_kind_id)
        .where(PartFormula.part_formula_id.in_(part_formula_ids))
        .where(PartKind.is_internal.is_(True))
    )
    if admin_id is not None:
        stmt = stmt.where(or_(PartFormula.admin_id.is_(None), PartFormula.admin_id == admin_id))
    items = (await session.scalars(stmt.order_by(PartFormula.sort_order.asc(), PartFormula.part_formula_id.asc()))).all()
    found_ids = {int(item.part_formula_id) for item in items}
    missing = [str(item) for item in part_formula_ids if int(item) not in found_ids]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown internal part formulas for this admin scope: {', '.join(missing)}",
        )
    return items


async def _replace_group_parts(
    session: AsyncSession,
    *,
    group: InternalPartGroup,
    parts: list[InternalPartGroupPartSelectionPayload],
) -> None:
    next_formulas = await _require_accessible_internal_part_formulas(
        session,
        admin_id=group.admin_id,
        part_formula_ids=[int(item.part_formula_id) for item in parts if item.enabled],
    )
    by_formula_id = {int(item.part_formula_id): item for item in next_formulas}
    existing_parts = list(group.__dict__.get("parts") or [])
    existing_by_formula_id = {int(item.part_formula_id): item for item in existing_parts}
    next_formula_ids = {int(item.part_formula_id) for item in parts}
    for formula_id, row in list(existing_by_formula_id.items()):
        if formula_id not in next_formula_ids:
            await session.delete(row)

    for selection in parts:
        formula_id = int(selection.part_formula_id)
        formula = by_formula_id.get(formula_id)
        existing = existing_by_formula_id.get(formula_id)
        if not formula:
            if existing is not None:
                existing.enabled = False
                existing.ui_order = int(selection.ui_order)
            continue
        if existing is None:
            existing = InternalPartGroupItem(
                group=group,
                part_formula_id=formula_id,
                part_kind_id=int(formula.part_kind_id),
                part_code=formula.part_code,
                part_title=formula.part_title,
                enabled=selection.enabled,
                ui_order=int(selection.ui_order),
            )
            session.add(existing)
        else:
            existing.part_kind_id = int(formula.part_kind_id)
            existing.part_code = formula.part_code
            existing.part_title = formula.part_title
            existing.enabled = selection.enabled
            existing.ui_order = int(selection.ui_order)


async def _require_accessible_param_groups(
    session: AsyncSession,
    *,
    admin_id: uuid.UUID | None,
    param_group_ids: list[int],
) -> list[ParamGroup]:
    if not param_group_ids:
        return []
    stmt = select(ParamGroup).where(ParamGroup.param_group_id.in_(param_group_ids))
    if admin_id is not None:
        stmt = stmt.where(or_(ParamGroup.admin_id.is_(None), ParamGroup.admin_id == admin_id))
    items = (await session.scalars(stmt.order_by(ParamGroup.ui_order.asc(), ParamGroup.param_group_id.asc()))).all()
    found_ids = {int(item.param_group_id) for item in items if item.param_group_id is not None}
    missing = [str(item) for item in param_group_ids if int(item) not in found_ids]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown param groups for this admin scope: {', '.join(missing)}",
        )
    return items


async def _replace_group_param_groups(
    session: AsyncSession,
    *,
    group: InternalPartGroup,
    param_groups: list[InternalPartGroupParamGroupSelectionPayload],
) -> None:
    next_groups = await _require_accessible_param_groups(
        session,
        admin_id=group.admin_id,
        param_group_ids=[int(item.param_group_id) for item in param_groups if item.enabled],
    )
    by_param_group_id = {int(item.param_group_id): item for item in next_groups if item.param_group_id is not None}
    existing_rows = list(group.__dict__.get("param_groups") or [])
    existing_by_param_group_id = {int(item.param_group_id): item for item in existing_rows}
    next_param_group_ids = {int(item.param_group_id) for item in param_groups}
    for param_group_id, row in list(existing_by_param_group_id.items()):
        if param_group_id not in next_param_group_ids:
            await session.delete(row)

    for selection in param_groups:
        param_group_id = int(selection.param_group_id)
        param_group = by_param_group_id.get(param_group_id)
        existing = existing_by_param_group_id.get(param_group_id)
        if not param_group:
            if existing is not None:
                existing.enabled = False
                existing.ui_order = int(selection.ui_order)
            continue
        title = str(param_group.org_param_group_title or param_group.title or param_group.param_group_code or "").strip()
        code = str(param_group.param_group_code or param_group.code or "").strip()
        icon_path = str(param_group.param_group_icon_path or "").strip() or None
        if existing is None:
            existing = InternalPartGroupParamGroup(
                group=group,
                param_group_id=param_group_id,
                param_group_code=code,
                param_group_title=title,
                param_group_icon_path=icon_path,
                enabled=selection.enabled,
                ui_order=int(selection.ui_order),
            )
            session.add(existing)
        else:
            existing.param_group_code = code
            existing.param_group_title = title
            existing.param_group_icon_path = icon_path
            existing.enabled = selection.enabled
            existing.ui_order = int(selection.ui_order)


async def _params_for_internal_group(session: AsyncSession, group: InternalPartGroup) -> list[Param]:
    await session.flush()
    selected_param_group_ids = sorted({
        int(row.param_group_id)
        for row in (
            await session.scalars(
                select(InternalPartGroupParamGroup).where(
                    InternalPartGroupParamGroup.group_ref_id == group.id
                )
            )
        ).all()
        if row.enabled is not False and row.param_group_id is not None
    })
    if not selected_param_group_ids:
        return []
    stmt = select(Param).where(Param.param_group_id.in_(selected_param_group_ids))
    if group.admin_id is None:
        stmt = stmt.where(Param.admin_id.is_(None))
    else:
        stmt = stmt.where(or_(Param.admin_id.is_(None), Param.admin_id == group.admin_id))
    stmt = stmt.order_by(Param.sort_order.asc(), Param.param_id.asc())
    return (await session.scalars(stmt)).all()


async def _load_first_sub_category_default_seed(
    session: AsyncSession,
    *,
    admin_id: uuid.UUID | None,
    param_ids: set[int],
) -> dict[int, SubCategoryParamDefault]:
    if not param_ids:
        return {}
    sub_category_stmt = (
        select(SubCategory.id)
        .where(SubCategory.deleted_at.is_(None))
        .order_by(SubCategory.sort_order.asc(), SubCategory.sub_cat_id.asc())
    )
    if admin_id is None:
        sub_category_stmt = sub_category_stmt.where(SubCategory.admin_id.is_(None))
    else:
        sub_category_stmt = sub_category_stmt.where(or_(SubCategory.admin_id.is_(None), SubCategory.admin_id == admin_id))
    sub_category_ids = list((await session.scalars(sub_category_stmt)).all())
    if not sub_category_ids:
        return {}
    rows = (
        await session.scalars(
            select(SubCategoryParamDefault).where(
                SubCategoryParamDefault.sub_category_id.in_(sub_category_ids),
                SubCategoryParamDefault.param_id.in_(sorted(param_ids)),
            )
        )
    ).all()
    rows_by_sub_category_id: dict[uuid.UUID, dict[int, SubCategoryParamDefault]] = {}
    for row in rows:
        rows_by_sub_category_id.setdefault(row.sub_category_id, {})[int(row.param_id)] = row
    seeded_by_param_id: dict[int, SubCategoryParamDefault] = {}
    for sub_category_id in sub_category_ids:
        rows_for_sub_category = rows_by_sub_category_id.get(sub_category_id, {})
        for param_id, row in rows_for_sub_category.items():
            seeded_by_param_id.setdefault(param_id, row)
        if len(seeded_by_param_id) >= len(param_ids):
            break
    return seeded_by_param_id


async def _sync_group_param_defaults(session: AsyncSession, group: InternalPartGroup) -> bool:
    changed = False
    params = await _params_for_internal_group(session, group)
    allowed_param_ids = {int(param.param_id) for param in params if param.param_id is not None}
    seed_rows_by_param_id = await _load_first_sub_category_default_seed(
        session,
        admin_id=group.admin_id,
        param_ids=allowed_param_ids,
    )
    defaults = (
        await session.scalars(
            select(InternalPartGroupParamDefault).where(InternalPartGroupParamDefault.internal_part_group_id == group.id)
        )
    ).all()
    defaults_by_param_id = {int(row.param_id): row for row in defaults}
    for row in defaults:
        if int(row.param_id) not in allowed_param_ids:
            await session.delete(row)
            changed = True
    for param in params:
        param_id = int(param.param_id)
        if param_id in defaults_by_param_id:
            row = defaults_by_param_id[param_id]
            seed_row = seed_rows_by_param_id.get(param_id)
            if (row.default_value is None or str(row.default_value).strip() == "") and seed_row and seed_row.default_value is not None:
                row.default_value = seed_row.default_value
                changed = True
            continue
        seed_row = seed_rows_by_param_id.get(param_id)
        session.add(
            InternalPartGroupParamDefault(
                internal_part_group_id=group.id,
                param_id=param_id,
                default_value=seed_row.default_value if seed_row else None,
            )
        )
        changed = True
    await session.flush()
    return changed


async def _apply_group_param_defaults(
    session: AsyncSession,
    group: InternalPartGroup,
    param_defaults: dict[str, str | int | float | bool | None],
    param_overrides: dict[str, InternalPartGroupParamOverridePayload],
) -> None:
    await _sync_group_param_defaults(session, group)
    params = await _params_for_internal_group(session, group)
    params_by_code = {
        str(param.param_code).strip(): param
        for param in params
        if str(param.param_code or "").strip()
    }
    defaults = (
        await session.scalars(
            select(InternalPartGroupParamDefault).where(InternalPartGroupParamDefault.internal_part_group_id == group.id)
        )
    ).all()
    defaults_by_param_id = {int(row.param_id): row for row in defaults}

    for param_code, raw_value in param_defaults.items():
        param = params_by_code.get(str(param_code or "").strip())
        if not param:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown param code for this internal group scope: {param_code}")
        defaults_by_param_id[int(param.param_id)].default_value = normalize_default_value(raw_value)


async def _apply_group_controller_config(
    session: AsyncSession,
    group: InternalPartGroup,
    *,
    controller_type: str | None,
    controller_bindings: dict[str, InternalPartGroupControllerBindingPayload],
) -> None:
    normalized_type = _normalize_controller_type(controller_type)
    normalized_bindings = _normalize_controller_bindings_payload(normalized_type, controller_bindings)
    if not normalized_type:
        group.controller_type = None
        group.controller_bindings = {}
        return
    params = await _params_for_internal_group(session, group)
    allowed_codes = {
        str(param.param_code).strip()
        for param in params
        if str(param.param_code or "").strip()
    }
    for slot, binding in normalized_bindings.items():
        param_code = _normalize_optional_string(binding.get("param_code"))
        if param_code and param_code not in allowed_codes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown controller param code for this internal group scope: {param_code}",
            )
        normalized_bindings[slot] = {"param_code": param_code}
    group.controller_type = normalized_type
    group.controller_bindings = normalized_bindings


@router.get("", response_model=list[InternalPartGroupItemResponse])
async def list_internal_part_groups(
    admin_id: uuid.UUID | None = Query(default=None),
    session: AsyncSession = Depends(get_db_session),
) -> list[InternalPartGroupItemResponse]:
    await require_admin_if_present(session, admin_id)
    include_param_groups = await internal_part_group_param_groups_table_ready(session)
    include_param_defaults = include_param_groups and await internal_part_group_param_defaults_table_ready(session)
    stmt = select(InternalPartGroup).options(selectinload(InternalPartGroup.parts))
    if include_param_groups:
        stmt = stmt.options(selectinload(InternalPartGroup.param_groups))
    if include_param_defaults:
        stmt = stmt.options(selectinload(InternalPartGroup.param_defaults).selectinload(InternalPartGroupParamDefault.param))
    if admin_id is None:
        stmt = stmt.where(InternalPartGroup.admin_id.is_(None))
    else:
        stmt = stmt.where(or_(InternalPartGroup.admin_id.is_(None), InternalPartGroup.admin_id == admin_id))
    stmt = stmt.order_by(
        InternalPartGroup.is_system.desc(),
        InternalPartGroup.sort_order.asc(),
        InternalPartGroup.group_id.asc(),
    )
    items = (await session.scalars(stmt)).all()
    if include_param_defaults:
        seeded = False
        for item in items:
            if await _sync_group_param_defaults(session, item):
                seeded = True
        if seeded:
            await session.commit()
            items = (
                await session.scalars(stmt)
            ).all()
    return [
        _serialize_group(
            item,
            include_param_groups=include_param_groups,
            include_param_defaults=include_param_defaults,
        )
        for item in items
    ]


@router.post("", response_model=InternalPartGroupItemResponse, status_code=status.HTTP_201_CREATED)
async def create_internal_part_group(payload: InternalPartGroupCreate, session: AsyncSession = Depends(get_db_session)) -> InternalPartGroupItemResponse:
    await require_admin_if_present(session, payload.admin_id)
    include_param_groups = await internal_part_group_param_groups_table_ready(session)
    include_param_defaults = include_param_groups and await internal_part_group_param_defaults_table_ready(session)
    next_group_id = payload.group_id or await _next_group_id(session)
    title = payload.group_title.strip()
    code = payload.code.strip()
    if not code:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Internal part group code is required.")
    await _ensure_unique_group_code(session, code=code)
    item = InternalPartGroup(
        admin_id=payload.admin_id,
        group_id=next_group_id,
        group_title=title,
        code=code,
        title=title,
        line_color=_normalize_hex_color(payload.line_color, DEFAULT_INTERNAL_LINE_COLOR),
        controller_type=None,
        controller_bindings={},
        sort_order=payload.sort_order if payload.sort_order is not None else next_group_id,
        is_system=payload.is_system,
    )
    session.add(item)
    await session.flush()
    await _replace_group_parts(session, group=item, parts=payload.parts)
    if payload.param_groups and not include_param_groups:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Param-group links table is not available yet. Run database migrations first.")
    if include_param_groups:
        await _replace_group_param_groups(session, group=item, param_groups=payload.param_groups)
    if (payload.param_defaults or payload.param_overrides) and not include_param_defaults:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Internal-group defaults table is not available yet. Run database migrations first.")
    if include_param_defaults:
        await _apply_group_param_defaults(session, item, payload.param_defaults, payload.param_overrides)
    await _apply_group_controller_config(
        session,
        item,
        controller_type=payload.controller_type,
        controller_bindings=payload.controller_bindings,
    )
    await session.commit()
    item = await _load_group(
        session,
        item.id,
        include_param_groups=include_param_groups,
        include_param_defaults=include_param_defaults,
    )
    return _serialize_group(item, include_param_groups=include_param_groups, include_param_defaults=include_param_defaults)


@router.patch("/{group_uuid}", response_model=InternalPartGroupItemResponse)
async def update_internal_part_group(
    group_uuid: uuid.UUID,
    payload: InternalPartGroupUpdate,
    session: AsyncSession = Depends(get_db_session),
) -> InternalPartGroupItemResponse:
    include_param_groups = await internal_part_group_param_groups_table_ready(session)
    include_param_defaults = include_param_groups and await internal_part_group_param_defaults_table_ready(session)
    item = await _load_group(
        session,
        group_uuid,
        include_param_groups=include_param_groups,
        include_param_defaults=include_param_defaults,
    )
    await require_admin_if_present(session, payload.admin_id)
    title = payload.group_title.strip()
    code = payload.code.strip()
    if not code:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Internal part group code is required.")
    await _ensure_unique_group_code(session, code=code, exclude_id=item.id)
    item.admin_id = payload.admin_id
    item.group_id = payload.group_id
    item.group_title = title
    item.code = code
    item.title = title
    item.line_color = _normalize_hex_color(payload.line_color, DEFAULT_INTERNAL_LINE_COLOR)
    item.sort_order = payload.sort_order
    item.is_system = payload.is_system
    await _replace_group_parts(session, group=item, parts=payload.parts)
    if payload.param_groups and not include_param_groups:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Param-group links table is not available yet. Run database migrations first.")
    if include_param_groups:
        await _replace_group_param_groups(session, group=item, param_groups=payload.param_groups)
    if (payload.param_defaults or payload.param_overrides) and not include_param_defaults:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Internal-group defaults table is not available yet. Run database migrations first.")
    if include_param_defaults:
        await _apply_group_param_defaults(session, item, payload.param_defaults, payload.param_overrides)
    await _apply_group_controller_config(
        session,
        item,
        controller_type=payload.controller_type,
        controller_bindings=payload.controller_bindings,
    )
    await session.commit()
    item = await _load_group(
        session,
        item.id,
        include_param_groups=include_param_groups,
        include_param_defaults=include_param_defaults,
    )
    return _serialize_group(item, include_param_groups=include_param_groups, include_param_defaults=include_param_defaults)


@router.delete("/{group_uuid}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_internal_part_group(group_uuid: uuid.UUID, session: AsyncSession = Depends(get_db_session)) -> Response:
    item = await session.get(InternalPartGroup, group_uuid)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Internal part group not found.")
    await session.delete(item)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
