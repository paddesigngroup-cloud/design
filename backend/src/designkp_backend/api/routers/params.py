from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from designkp_backend.db.dependencies import get_db_session
from designkp_backend.db.models.catalog import Param
from designkp_backend.services.admin_access import require_admin_if_present

router = APIRouter(prefix="/params", tags=["params"])


class ParamItem(BaseModel):
    id: uuid.UUID
    admin_id: uuid.UUID | None
    param_id: int
    part_kind_id: int
    param_code: str
    param_title_en: str
    param_title_fa: str
    param_group_id: int
    ui_order: int
    code: str
    title: str
    sort_order: int
    is_system: bool

    model_config = {"from_attributes": True}


class ParamCreate(BaseModel):
    admin_id: uuid.UUID | None = None
    param_id: int | None = Field(default=None, ge=1)
    part_kind_id: int = Field(ge=1)
    param_code: str = Field(min_length=1, max_length=64)
    param_title_en: str = Field(min_length=1, max_length=255)
    param_title_fa: str = Field(min_length=1, max_length=255)
    param_group_id: int = Field(ge=1)
    ui_order: int | None = Field(default=None, ge=0)
    sort_order: int | None = Field(default=None, ge=0)
    is_system: bool = False


class ParamUpdate(BaseModel):
    admin_id: uuid.UUID | None = None
    param_id: int = Field(ge=1)
    part_kind_id: int = Field(ge=1)
    param_code: str = Field(min_length=1, max_length=64)
    param_title_en: str = Field(min_length=1, max_length=255)
    param_title_fa: str = Field(min_length=1, max_length=255)
    param_group_id: int = Field(ge=1)
    ui_order: int = Field(ge=0)
    sort_order: int = Field(ge=0)
    is_system: bool


def _to_response(item: Param) -> ParamItem:
    return ParamItem.model_validate(item)


async def _next_param_id(session: AsyncSession) -> int:
    max_id = await session.scalar(select(func.max(Param.param_id)))
    return int(max_id or 0) + 1


@router.get("", response_model=list[ParamItem])
async def list_params(
    admin_id: uuid.UUID | None = Query(default=None),
    session: AsyncSession = Depends(get_db_session),
) -> list[ParamItem]:
    await require_admin_if_present(session, admin_id)
    stmt = (
        select(Param)
        .where(or_(Param.admin_id.is_(None), Param.admin_id == admin_id))
        .order_by(Param.sort_order.asc(), Param.param_id.asc())
    )
    items = (await session.scalars(stmt)).all()
    return [_to_response(item) for item in items]


@router.post("", response_model=ParamItem, status_code=status.HTTP_201_CREATED)
async def create_param(payload: ParamCreate, session: AsyncSession = Depends(get_db_session)) -> ParamItem:
    await require_admin_if_present(session, payload.admin_id)
    next_id = payload.param_id or await _next_param_id(session)
    ui_order = payload.ui_order if payload.ui_order is not None else 0
    sort_order = payload.sort_order if payload.sort_order is not None else next_id
    item = Param(
        admin_id=payload.admin_id,
        param_id=next_id,
        part_kind_id=payload.part_kind_id,
        param_code=payload.param_code.strip(),
        param_title_en=payload.param_title_en.strip(),
        param_title_fa=payload.param_title_fa.strip(),
        param_group_id=payload.param_group_id,
        ui_order=ui_order,
        code=payload.param_code.strip(),
        title=payload.param_title_fa.strip(),
        sort_order=sort_order,
        is_system=payload.is_system,
    )
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return _to_response(item)


@router.patch("/{param_uuid}", response_model=ParamItem)
async def update_param(
    param_uuid: uuid.UUID,
    payload: ParamUpdate,
    session: AsyncSession = Depends(get_db_session),
) -> ParamItem:
    item = await session.get(Param, param_uuid)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Param not found.")
    await require_admin_if_present(session, payload.admin_id)

    item.admin_id = payload.admin_id
    item.param_id = payload.param_id
    item.part_kind_id = payload.part_kind_id
    item.param_code = payload.param_code.strip()
    item.param_title_en = payload.param_title_en.strip()
    item.param_title_fa = payload.param_title_fa.strip()
    item.param_group_id = payload.param_group_id
    item.ui_order = payload.ui_order
    item.code = payload.param_code.strip()
    item.title = payload.param_title_fa.strip()
    item.sort_order = payload.sort_order
    item.is_system = payload.is_system

    await session.commit()
    await session.refresh(item)
    return _to_response(item)


@router.delete("/{param_uuid}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_param(param_uuid: uuid.UUID, session: AsyncSession = Depends(get_db_session)) -> Response:
    item = await session.get(Param, param_uuid)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Param not found.")

    await session.delete(item)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
