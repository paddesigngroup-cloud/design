from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from designkp_backend.db.dependencies import get_db_session
from designkp_backend.db.models.catalog import DoorPartGroup, DoorPartGroupItem, DoorPartGroupParamDefault, DoorPartGroupParamGroup, Param, ParamGroup, PartFormula, PartKind
from designkp_backend.services.admin_access import require_admin_if_present
from designkp_backend.services.admin_storage import normalize_icon_file_name
from designkp_backend.services.sub_category_defaults import normalize_default_value

router = APIRouter(prefix="/door-part-groups", tags=["door_part_groups"])

DEFAULT_DOOR_LINE_COLOR = "#8A98A3"
DOOR_PART_GROUP_CONTROLLER_TYPE_BACK_TO_BACK_OPENING = "back_to_back_opening"
DOOR_PART_GROUP_CONTROLLER_TYPES = {DOOR_PART_GROUP_CONTROLLER_TYPE_BACK_TO_BACK_OPENING}
DOOR_PART_GROUP_CONTROLLER_AXES = ("vertical", "horizontal")
DOOR_PART_GROUP_CONTROLLER_BINDING_KEYS = ("width_back_to_back", "height_back_to_back")


def _normalize_hex_color(value: str | None, fallback: str = DEFAULT_DOOR_LINE_COLOR) -> str:
    raw = str(value or "").strip()
    if not raw:
        return fallback
    normalized = raw if raw.startswith("#") else f"#{raw}"
    if len(normalized) != 7 or not all(ch in "0123456789ABCDEFabcdef#" for ch in normalized):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Door part group line color must be a HEX value like #8A98A3.",
        )
    return normalized.upper()


class DoorPartGroupPartSelectionPayload(BaseModel):
    part_formula_id: int = Field(ge=1)
    enabled: bool = True
    ui_order: int = Field(default=0, ge=0)


class DoorPartGroupControllerSelectionPayload(BaseModel):
    axis: str = Field(min_length=1, max_length=32)
    part_formula_id: int = Field(ge=1)


class DoorPartGroupParamGroupSelectionPayload(BaseModel):
    param_group_id: int = Field(ge=1)
    enabled: bool = True
    ui_order: int = Field(default=0, ge=0)


class DoorPartGroupControllerBindingPayload(BaseModel):
    param_code: str | None = Field(default=None, max_length=128)


class DoorPartGroupPartItem(BaseModel):
    id: uuid.UUID
    part_formula_id: int
    part_kind_id: int
    part_code: str
    part_title: str
    enabled: bool
    ui_order: int

    model_config = {"from_attributes": True}


class DoorPartGroupParamGroupItem(BaseModel):
    id: uuid.UUID
    param_group_id: int
    param_group_code: str
    param_group_title: str
    param_group_icon_path: str | None = None
    enabled: bool
    ui_order: int

    model_config = {"from_attributes": True}


class DoorPartGroupControllerBindingItem(BaseModel):
    param_code: str | None = None


class DoorPartGroupItemResponse(BaseModel):
    id: uuid.UUID
    admin_id: uuid.UUID | None
    group_id: int
    group_title: str
    code: str
    title: str
    line_color: str
    sort_order: int
    is_system: bool
    parts: list[DoorPartGroupPartItem]
    param_groups: list[DoorPartGroupParamGroupItem]
    param_defaults: dict[str, str | None]
    controller_type: str | None = None
    controller_selection: list[DoorPartGroupControllerSelectionPayload] = Field(default_factory=list)
    controller_bindings: dict[str, DoorPartGroupControllerBindingItem] = Field(default_factory=dict)

    model_config = {"from_attributes": True}


class DoorPartGroupCreate(BaseModel):
    admin_id: uuid.UUID | None = None
    group_id: int | None = Field(default=None, ge=1)
    group_title: str = Field(min_length=1, max_length=255)
    code: str = Field(min_length=1, max_length=64)
    line_color: str = Field(default=DEFAULT_DOOR_LINE_COLOR, min_length=7, max_length=7)
    sort_order: int | None = Field(default=None, ge=0)
    is_system: bool = False
    parts: list[DoorPartGroupPartSelectionPayload] = Field(default_factory=list)
    param_groups: list[DoorPartGroupParamGroupSelectionPayload] = Field(default_factory=list)
    param_defaults: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
    controller_type: str | None = Field(default=None, max_length=128)
    controller_selection: list[DoorPartGroupControllerSelectionPayload] = Field(default_factory=list)
    controller_bindings: dict[str, DoorPartGroupControllerBindingPayload] = Field(default_factory=dict)


class DoorPartGroupUpdate(BaseModel):
    admin_id: uuid.UUID | None = None
    group_id: int = Field(ge=1)
    group_title: str = Field(min_length=1, max_length=255)
    code: str = Field(min_length=1, max_length=64)
    line_color: str = Field(default=DEFAULT_DOOR_LINE_COLOR, min_length=7, max_length=7)
    sort_order: int = Field(ge=0)
    is_system: bool
    parts: list[DoorPartGroupPartSelectionPayload] = Field(default_factory=list)
    param_groups: list[DoorPartGroupParamGroupSelectionPayload] = Field(default_factory=list)
    param_defaults: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
    controller_type: str | None = Field(default=None, max_length=128)
    controller_selection: list[DoorPartGroupControllerSelectionPayload] = Field(default_factory=list)
    controller_bindings: dict[str, DoorPartGroupControllerBindingPayload] = Field(default_factory=dict)


async def _next_group_id(session: AsyncSession) -> int:
    max_id = await session.scalar(select(func.max(DoorPartGroup.group_id)))
    return int(max_id or 0) + 1


async def door_part_group_param_groups_table_ready(session: AsyncSession) -> bool:
    result = await session.execute(select(func.to_regclass("door_part_group_param_groups")))
    return bool(result.one()[0])


async def door_part_group_param_defaults_table_ready(session: AsyncSession) -> bool:
    result = await session.execute(select(func.to_regclass("door_part_group_param_defaults")))
    return bool(result.one()[0])


async def _ensure_unique_group_code(session: AsyncSession, *, code: str, exclude_id: uuid.UUID | None = None) -> None:
    stmt = select(DoorPartGroup).where(DoorPartGroup.code == code)
    if exclude_id is not None:
        stmt = stmt.where(DoorPartGroup.id != exclude_id)
    duplicate = await session.scalar(stmt)
    if duplicate:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Door part group code is already used.")


async def _load_group(session: AsyncSession, group_uuid: uuid.UUID) -> DoorPartGroup:
    include_param_groups = await door_part_group_param_groups_table_ready(session)
    include_param_defaults = await door_part_group_param_defaults_table_ready(session)
    stmt = select(DoorPartGroup).options(selectinload(DoorPartGroup.parts))
    if include_param_groups:
        stmt = stmt.options(selectinload(DoorPartGroup.param_groups))
    if include_param_defaults:
        stmt = stmt.options(selectinload(DoorPartGroup.param_defaults).selectinload(DoorPartGroupParamDefault.param))
    item = await session.scalar(stmt.where(DoorPartGroup.id == group_uuid))
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Door part group not found.")
    return item


def _normalize_controller_type(value: str | None) -> str | None:
    normalized = str(value or "").strip()
    if not normalized:
        return None
    if normalized not in DOOR_PART_GROUP_CONTROLLER_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unsupported door group controller type: {normalized}")
    return normalized


def _normalize_optional_string(value: object) -> str | None:
    normalized = str(value or "").strip()
    return normalized or None


def _normalize_controller_selection_payload(
    controller_type: str | None,
    selection: list[DoorPartGroupControllerSelectionPayload] | list[dict[str, object]] | None,
) -> list[dict[str, object]]:
    normalized_type = _normalize_controller_type(controller_type)
    if not normalized_type:
        return []
    items = list(selection or [])
    if not items:
        return []
    normalized: list[dict[str, object]] = []
    seen_pairs: set[tuple[str, int]] = set()
    seen_axes: set[str] = set()
    for raw_item in items:
        payload = raw_item if isinstance(raw_item, DoorPartGroupControllerSelectionPayload) else DoorPartGroupControllerSelectionPayload.model_validate(raw_item)
        axis = str(payload.axis or "").strip()
        if axis not in DOOR_PART_GROUP_CONTROLLER_AXES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unsupported door group controller axis: {axis}")
        formula_id = int(payload.part_formula_id)
        pair = (axis, formula_id)
        if pair in seen_pairs:
            continue
        seen_pairs.add(pair)
        seen_axes.add(axis)
        normalized.append({
            "axis": axis,
            "part_formula_id": formula_id,
        })
    missing_axes = [axis for axis in DOOR_PART_GROUP_CONTROLLER_AXES if axis not in seen_axes]
    if normalized and missing_axes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Incomplete door group controller selection. Missing axes: {', '.join(missing_axes)}",
        )
    return normalized


def _normalize_controller_bindings_payload(
    controller_type: str | None,
    bindings: dict[str, DoorPartGroupControllerBindingPayload] | dict[str, object] | None,
    allowed_codes: set[str] | None = None,
) -> dict[str, dict[str, str | None]]:
    normalized_type = _normalize_controller_type(controller_type)
    if not normalized_type:
        return {}
    raw_bindings = dict(bindings or {})
    invalid_keys = sorted(str(key or "").strip() for key in raw_bindings if str(key or "").strip() not in DOOR_PART_GROUP_CONTROLLER_BINDING_KEYS)
    if invalid_keys:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported door group controller bindings: {', '.join(invalid_keys)}",
        )
    normalized: dict[str, dict[str, str | None]] = {}
    for key in DOOR_PART_GROUP_CONTROLLER_BINDING_KEYS:
        raw_value = raw_bindings.get(key)
        if isinstance(raw_value, DoorPartGroupControllerBindingPayload):
            param_code = _normalize_optional_string(raw_value.param_code)
        elif isinstance(raw_value, dict):
            param_code = _normalize_optional_string(raw_value.get("param_code"))
        else:
            param_code = None
        if param_code and allowed_codes is not None and param_code not in allowed_codes:
            param_code = None
        normalized[key] = {"param_code": param_code}
    return normalized


def _serialize_group(item: DoorPartGroup, *, include_param_groups: bool = True) -> DoorPartGroupItemResponse:
    loaded_param_defaults = list(getattr(item, "__dict__", {}).get("param_defaults") or [])
    defaults_map: dict[str, str | None] = {}
    for row in sorted(
        loaded_param_defaults,
        key=lambda current: int(current.param_id),
    ):
        param_code = getattr(getattr(row, "param", None), "param_code", None)
        if not param_code:
            continue
        defaults_map[str(param_code)] = row.default_value
    controller_type = _normalize_controller_type(getattr(item, "controller_type", None))
    controller_selection = _normalize_controller_selection_payload(
        controller_type,
        getattr(item, "controller_selection", None),
    )
    controller_bindings = _normalize_controller_bindings_payload(
        controller_type,
        getattr(item, "controller_bindings", None),
        None,
    )
    return DoorPartGroupItemResponse(
        id=item.id,
        admin_id=item.admin_id,
        group_id=int(item.group_id or 0),
        group_title=item.group_title,
        code=item.code,
        title=item.title,
        line_color=_normalize_hex_color(getattr(item, "line_color", DEFAULT_DOOR_LINE_COLOR), DEFAULT_DOOR_LINE_COLOR),
        sort_order=item.sort_order,
        is_system=item.is_system,
        parts=[
            DoorPartGroupPartItem.model_validate(part)
            for part in sorted(item.parts, key=lambda part: (int(part.ui_order), int(part.part_formula_id)))
        ],
        param_groups=[
            DoorPartGroupParamGroupItem.model_validate(param_group)
            for param_group in sorted(getattr(item, "param_groups", []) or [], key=lambda row: (int(row.ui_order), int(row.param_group_id)))
        ] if include_param_groups else [],
        param_defaults=defaults_map,
        controller_type=controller_type,
        controller_selection=[
            DoorPartGroupControllerSelectionPayload.model_validate(part)
            for part in controller_selection
        ],
        controller_bindings={
            key: DoorPartGroupControllerBindingItem.model_validate(value)
            for key, value in controller_bindings.items()
        },
    )


async def _require_accessible_part_formulas(
    session: AsyncSession,
    *,
    admin_id: uuid.UUID | None,
    part_formula_ids: list[int],
) -> list[PartFormula]:
    if not part_formula_ids:
        return []
    stmt = select(PartFormula).where(PartFormula.part_formula_id.in_(part_formula_ids))
    if admin_id is not None:
        stmt = stmt.where(or_(PartFormula.admin_id.is_(None), PartFormula.admin_id == admin_id))
    items = (await session.scalars(stmt.order_by(PartFormula.sort_order.asc(), PartFormula.part_formula_id.asc()))).all()
    found_ids = {int(item.part_formula_id) for item in items}
    missing = [str(item) for item in part_formula_ids if int(item) not in found_ids]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown part formulas for this admin scope: {', '.join(missing)}",
        )
    return items


async def _require_accessible_door_part_formulas(
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
        .where(PartKind.part_scope == "door")
    )
    if admin_id is not None:
        stmt = stmt.where(or_(PartFormula.admin_id.is_(None), PartFormula.admin_id == admin_id))
    items = (await session.scalars(stmt.order_by(PartFormula.sort_order.asc(), PartFormula.part_formula_id.asc()))).all()
    found_ids = {int(item.part_formula_id) for item in items}
    missing = [str(item) for item in part_formula_ids if int(item) not in found_ids]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown door part formulas for this admin scope: {', '.join(missing)}",
        )
    return items


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
    group: DoorPartGroup,
    param_groups: list[DoorPartGroupParamGroupSelectionPayload],
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
        icon_path = normalize_icon_file_name(param_group.param_group_icon_path) or None
        if existing is None:
            existing = DoorPartGroupParamGroup(
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


async def _params_for_door_group(session: AsyncSession, group: DoorPartGroup) -> list[Param]:
    selected_param_group_ids = sorted({
        int(row.param_group_id)
        for row in list(group.__dict__.get("param_groups") or [])
        if row.enabled is not False and row.param_group_id is not None
    })
    if not selected_param_group_ids:
        return []
    stmt = select(Param).where(Param.param_group_id.in_(selected_param_group_ids))
    if group.admin_id is not None:
        stmt = stmt.where(or_(Param.admin_id.is_(None), Param.admin_id == group.admin_id))
    return (await session.scalars(stmt.order_by(Param.sort_order.asc(), Param.param_id.asc()))).all()


async def _sync_group_param_defaults(session: AsyncSession, group: DoorPartGroup) -> bool:
    changed = False
    params = await _params_for_door_group(session, group)
    allowed_param_ids = {int(param.param_id) for param in params if param.param_id is not None}
    defaults = (
        await session.scalars(
            select(DoorPartGroupParamDefault).where(DoorPartGroupParamDefault.door_part_group_id == group.id)
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
            continue
        session.add(
            DoorPartGroupParamDefault(
                door_part_group_id=group.id,
                param_id=param_id,
                default_value=None,
            )
        )
        changed = True
    await session.flush()
    return changed


async def _apply_group_param_defaults(
    session: AsyncSession,
    group: DoorPartGroup,
    param_defaults: dict[str, str | int | float | bool | None],
) -> None:
    await _sync_group_param_defaults(session, group)
    params = await _params_for_door_group(session, group)
    params_by_code = {
        str(param.param_code).strip(): param
        for param in params
        if str(param.param_code or "").strip()
    }
    defaults = (
        await session.scalars(
            select(DoorPartGroupParamDefault).where(DoorPartGroupParamDefault.door_part_group_id == group.id)
        )
    ).all()
    defaults_by_param_id = {int(row.param_id): row for row in defaults}
    for param_code, raw_value in param_defaults.items():
        param = params_by_code.get(str(param_code or "").strip())
        if not param:
            continue
        defaults_by_param_id[int(param.param_id)].default_value = normalize_default_value(raw_value)


async def _replace_group_parts(
    session: AsyncSession,
    *,
    group: DoorPartGroup,
    parts: list[DoorPartGroupPartSelectionPayload],
) -> None:
    next_formulas = await _require_accessible_door_part_formulas(
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
            existing = DoorPartGroupItem(
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


async def _apply_group_controller_config(
    session: AsyncSession,
    *,
    group: DoorPartGroup,
    controller_type: str | None,
    controller_selection: list[DoorPartGroupControllerSelectionPayload] | list[dict[str, object]] | None,
    controller_bindings: dict[str, DoorPartGroupControllerBindingPayload] | dict[str, object] | None,
) -> None:
    normalized_type = _normalize_controller_type(controller_type)
    normalized_selection = _normalize_controller_selection_payload(normalized_type, controller_selection)
    formulas = await _require_accessible_door_part_formulas(
        session,
        admin_id=group.admin_id,
        part_formula_ids=[int(item["part_formula_id"]) for item in normalized_selection],
    )
    formula_ids = {int(item.part_formula_id) for item in formulas}
    invalid_formula_ids = [
        str(item["part_formula_id"])
        for item in normalized_selection
        if int(item["part_formula_id"]) not in formula_ids
    ]
    if invalid_formula_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown controller part formulas for this admin scope: {', '.join(invalid_formula_ids)}",
        )
    params = await _params_for_door_group(session, group)
    selected_codes = {
        str(param.param_code).strip()
        for param in params
        if str(param.param_code or "").strip()
    }
    normalized_bindings = _normalize_controller_bindings_payload(
        normalized_type,
        controller_bindings,
        selected_codes,
    )
    group.controller_type = normalized_type
    group.controller_selection = normalized_selection or None
    group.controller_bindings = normalized_bindings or None


@router.get("", response_model=list[DoorPartGroupItemResponse])
async def list_door_part_groups(
    admin_id: uuid.UUID | None = Query(default=None),
    session: AsyncSession = Depends(get_db_session),
) -> list[DoorPartGroupItemResponse]:
    await require_admin_if_present(session, admin_id)
    include_param_groups = await door_part_group_param_groups_table_ready(session)
    include_param_defaults = await door_part_group_param_defaults_table_ready(session)
    stmt = select(DoorPartGroup).options(selectinload(DoorPartGroup.parts))
    if include_param_groups:
        stmt = stmt.options(selectinload(DoorPartGroup.param_groups))
    if include_param_defaults:
        stmt = stmt.options(selectinload(DoorPartGroup.param_defaults).selectinload(DoorPartGroupParamDefault.param))
    if admin_id is None:
        stmt = stmt.where(DoorPartGroup.admin_id.is_(None))
    else:
        stmt = stmt.where(or_(DoorPartGroup.admin_id.is_(None), DoorPartGroup.admin_id == admin_id))
    stmt = stmt.order_by(DoorPartGroup.is_system.desc(), DoorPartGroup.sort_order.asc(), DoorPartGroup.group_id.asc())
    items = (await session.scalars(stmt)).all()
    if include_param_defaults:
        for item in items:
            await _sync_group_param_defaults(session, item)
        await session.commit()
        items = (await session.scalars(stmt)).all()
    return [_serialize_group(item, include_param_groups=include_param_groups) for item in items]


@router.post("", response_model=DoorPartGroupItemResponse, status_code=status.HTTP_201_CREATED)
async def create_door_part_group(payload: DoorPartGroupCreate, session: AsyncSession = Depends(get_db_session)) -> DoorPartGroupItemResponse:
    await require_admin_if_present(session, payload.admin_id)
    include_param_defaults = await door_part_group_param_defaults_table_ready(session)
    next_group_id = payload.group_id or await _next_group_id(session)
    title = payload.group_title.strip()
    code = payload.code.strip()
    if not code:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Door part group code is required.")
    await _ensure_unique_group_code(session, code=code)
    item = DoorPartGroup(
        admin_id=payload.admin_id,
        group_id=next_group_id,
        group_title=title,
        code=code,
        title=title,
        line_color=_normalize_hex_color(payload.line_color, DEFAULT_DOOR_LINE_COLOR),
        sort_order=payload.sort_order if payload.sort_order is not None else next_group_id,
        is_system=payload.is_system,
    )
    session.add(item)
    await session.flush()
    await _replace_group_parts(session, group=item, parts=payload.parts)
    if payload.param_groups:
        await _replace_group_param_groups(session, group=item, param_groups=payload.param_groups)
    if payload.param_defaults and not include_param_defaults:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Door-group defaults table is not available yet. Run database migrations first.")
    if include_param_defaults:
        await _apply_group_param_defaults(session, item, payload.param_defaults)
    await _apply_group_controller_config(
        session,
        group=item,
        controller_type=payload.controller_type,
        controller_selection=payload.controller_selection,
        controller_bindings=payload.controller_bindings,
    )
    await session.commit()
    item = await _load_group(session, item.id)
    return _serialize_group(item, include_param_groups=await door_part_group_param_groups_table_ready(session))


@router.patch("/{group_uuid}", response_model=DoorPartGroupItemResponse)
async def update_door_part_group(
    group_uuid: uuid.UUID,
    payload: DoorPartGroupUpdate,
    session: AsyncSession = Depends(get_db_session),
) -> DoorPartGroupItemResponse:
    item = await _load_group(session, group_uuid)
    await require_admin_if_present(session, payload.admin_id)
    include_param_defaults = await door_part_group_param_defaults_table_ready(session)
    title = payload.group_title.strip()
    code = payload.code.strip()
    if not code:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Door part group code is required.")
    await _ensure_unique_group_code(session, code=code, exclude_id=item.id)
    item.admin_id = payload.admin_id
    item.group_id = payload.group_id
    item.group_title = title
    item.code = code
    item.title = title
    item.line_color = _normalize_hex_color(payload.line_color, DEFAULT_DOOR_LINE_COLOR)
    item.sort_order = payload.sort_order
    item.is_system = payload.is_system
    await _replace_group_parts(session, group=item, parts=payload.parts)
    await _replace_group_param_groups(session, group=item, param_groups=payload.param_groups)
    if payload.param_defaults and not include_param_defaults:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Door-group defaults table is not available yet. Run database migrations first.")
    if include_param_defaults:
        await _apply_group_param_defaults(session, item, payload.param_defaults)
    await _apply_group_controller_config(
        session,
        group=item,
        controller_type=payload.controller_type,
        controller_selection=payload.controller_selection,
        controller_bindings=payload.controller_bindings,
    )
    await session.commit()
    item = await _load_group(session, item.id)
    return _serialize_group(item, include_param_groups=await door_part_group_param_groups_table_ready(session))


@router.delete("/{group_uuid}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_door_part_group(group_uuid: uuid.UUID, session: AsyncSession = Depends(get_db_session)) -> Response:
    item = await session.get(DoorPartGroup, group_uuid)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Door part group not found.")
    await session.delete(item)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
