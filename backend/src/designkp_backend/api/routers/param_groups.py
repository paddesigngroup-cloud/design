from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from designkp_backend.db.dependencies import get_db_session
from designkp_backend.db.models.catalog import ParamGroup
from designkp_backend.services.admin_access import require_admin_if_present
from designkp_backend.services.admin_storage import delete_final_icon, finalize_param_group_icon, normalize_icon_file_name

router = APIRouter(prefix="/param-groups", tags=["param_groups"])


class ParamGroupItem(BaseModel):
    id: uuid.UUID
    admin_id: uuid.UUID | None
    param_group_id: int
    param_group_code: str
    org_param_group_title: str
    param_group_icon_path: str | None
    show_in_order_attrs: bool
    ui_order: int
    code: str
    title: str
    sort_order: int
    is_system: bool

    model_config = {"from_attributes": True}


class ParamGroupCreate(BaseModel):
    admin_id: uuid.UUID | None = None
    param_group_id: int | None = Field(default=None, ge=1)
    param_group_code: str = Field(min_length=1, max_length=64)
    org_param_group_title: str = Field(min_length=1, max_length=255)
    param_group_icon_path: str | None = Field(default=None, max_length=255)
    show_in_order_attrs: bool = True
    ui_order: int | None = Field(default=None, ge=0)
    sort_order: int | None = Field(default=None, ge=0)
    is_system: bool = False


class ParamGroupUpdate(BaseModel):
    admin_id: uuid.UUID | None = None
    param_group_id: int = Field(ge=1)
    param_group_code: str = Field(min_length=1, max_length=64)
    org_param_group_title: str = Field(min_length=1, max_length=255)
    param_group_icon_path: str | None = Field(default=None, max_length=255)
    show_in_order_attrs: bool = True
    ui_order: int = Field(ge=0)
    sort_order: int = Field(ge=0)
    is_system: bool


def _to_response(item: ParamGroup) -> ParamGroupItem:
    payload = ParamGroupItem.model_validate(item).model_dump()
    payload["param_group_icon_path"] = normalize_icon_file_name(payload["param_group_icon_path"])
    return ParamGroupItem.model_validate(payload)


async def _next_param_group_id(session: AsyncSession) -> int:
    max_id = await session.scalar(select(func.max(ParamGroup.param_group_id)))
    return int(max_id or 0) + 1


@router.get("", response_model=list[ParamGroupItem])
async def list_param_groups(
    admin_id: uuid.UUID | None = Query(default=None),
    session: AsyncSession = Depends(get_db_session),
) -> list[ParamGroupItem]:
    await require_admin_if_present(session, admin_id)
    stmt = (
        select(ParamGroup)
        .where(or_(ParamGroup.admin_id.is_(None), ParamGroup.admin_id == admin_id))
        .order_by(ParamGroup.ui_order.asc(), ParamGroup.param_group_id.asc())
    )
    items = (await session.scalars(stmt)).all()
    return [_to_response(item) for item in items]


@router.post("", response_model=ParamGroupItem, status_code=status.HTTP_201_CREATED)
async def create_param_group(payload: ParamGroupCreate, session: AsyncSession = Depends(get_db_session)) -> ParamGroupItem:
    await require_admin_if_present(session, payload.admin_id)
    normalized_admin_id = payload.admin_id
    next_id = payload.param_group_id or await _next_param_group_id(session)
    ui_order = payload.ui_order if payload.ui_order is not None else next_id - 1
    sort_order = payload.sort_order if payload.sort_order is not None else next_id
    final_icon_file_name = finalize_param_group_icon(normalized_admin_id, payload.param_group_icon_path) if normalized_admin_id else normalize_icon_file_name(payload.param_group_icon_path)
    item = ParamGroup(
        admin_id=normalized_admin_id,
        param_group_id=next_id,
        param_group_code=payload.param_group_code.strip(),
        org_param_group_title=payload.org_param_group_title.strip(),
        param_group_icon_path=final_icon_file_name,
        show_in_order_attrs=payload.show_in_order_attrs,
        ui_order=ui_order,
        code=payload.param_group_code.strip(),
        title=payload.org_param_group_title.strip(),
        sort_order=sort_order,
        is_system=payload.is_system,
    )
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return _to_response(item)


@router.patch("/{param_group_uuid}", response_model=ParamGroupItem)
async def update_param_group(
    param_group_uuid: uuid.UUID,
    payload: ParamGroupUpdate,
    session: AsyncSession = Depends(get_db_session),
) -> ParamGroupItem:
    item = await session.get(ParamGroup, param_group_uuid)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Param group not found.")
    await require_admin_if_present(session, payload.admin_id)
    previous_admin_id = item.admin_id
    previous_icon_file_name = item.param_group_icon_path
    next_admin_id = payload.admin_id
    if next_admin_id:
        next_icon_file_name = finalize_param_group_icon(next_admin_id, payload.param_group_icon_path, previous_file_name=previous_icon_file_name if previous_admin_id == next_admin_id else None)
        if previous_admin_id and previous_admin_id != next_admin_id and previous_icon_file_name:
            delete_final_icon(previous_admin_id, previous_icon_file_name)
    else:
        next_icon_file_name = normalize_icon_file_name(payload.param_group_icon_path)
        if previous_admin_id and previous_icon_file_name:
            delete_final_icon(previous_admin_id, previous_icon_file_name)

    item.admin_id = next_admin_id
    item.param_group_id = payload.param_group_id
    item.param_group_code = payload.param_group_code.strip()
    item.org_param_group_title = payload.org_param_group_title.strip()
    item.param_group_icon_path = next_icon_file_name
    item.show_in_order_attrs = payload.show_in_order_attrs
    item.ui_order = payload.ui_order
    item.code = payload.param_group_code.strip()
    item.title = payload.org_param_group_title.strip()
    item.sort_order = payload.sort_order
    item.is_system = payload.is_system

    await session.commit()
    await session.refresh(item)
    return _to_response(item)


@router.delete("/{param_group_uuid}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_param_group(param_group_uuid: uuid.UUID, session: AsyncSession = Depends(get_db_session)) -> Response:
    item = await session.get(ParamGroup, param_group_uuid)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Param group not found.")
    if item.admin_id and item.param_group_icon_path:
        delete_final_icon(item.admin_id, item.param_group_icon_path)

    await session.delete(item)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
