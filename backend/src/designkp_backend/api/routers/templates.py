from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from designkp_backend.db.dependencies import get_db_session
from designkp_backend.db.models.catalog import Template
from designkp_backend.services.admin_access import require_admin_if_present

router = APIRouter(prefix="/templates", tags=["templates"])


class TemplateItem(BaseModel):
    id: uuid.UUID
    admin_id: uuid.UUID | None
    temp_id: int
    temp_title: str
    code: str
    title: str
    sort_order: int
    is_system: bool

    model_config = {"from_attributes": True}


class TemplateCreate(BaseModel):
    admin_id: uuid.UUID | None = None
    temp_id: int | None = Field(default=None, ge=1)
    temp_title: str = Field(min_length=1, max_length=255)
    sort_order: int | None = Field(default=None, ge=0)
    is_system: bool = False


class TemplateUpdate(BaseModel):
    admin_id: uuid.UUID | None = None
    temp_id: int = Field(ge=1)
    temp_title: str = Field(min_length=1, max_length=255)
    sort_order: int = Field(ge=0)
    is_system: bool


def _to_response(item: Template) -> TemplateItem:
    return TemplateItem.model_validate(item)


def _template_code(temp_id: int) -> str:
    return f"template_{temp_id}"


async def _next_temp_id(session: AsyncSession) -> int:
    max_id = await session.scalar(select(func.max(Template.temp_id)))
    return int(max_id or 0) + 1


@router.get("", response_model=list[TemplateItem])
async def list_templates(
    admin_id: uuid.UUID | None = Query(default=None),
    session: AsyncSession = Depends(get_db_session),
) -> list[TemplateItem]:
    await require_admin_if_present(session, admin_id)
    stmt = (
        select(Template)
        .where(or_(Template.admin_id.is_(None), Template.admin_id == admin_id))
        .order_by(Template.sort_order.asc(), Template.temp_id.asc())
    )
    items = (await session.scalars(stmt)).all()
    return [_to_response(item) for item in items]


@router.post("", response_model=TemplateItem, status_code=status.HTTP_201_CREATED)
async def create_template(payload: TemplateCreate, session: AsyncSession = Depends(get_db_session)) -> TemplateItem:
    await require_admin_if_present(session, payload.admin_id)
    next_id = payload.temp_id or await _next_temp_id(session)
    item = Template(
        admin_id=payload.admin_id,
        temp_id=next_id,
        temp_title=payload.temp_title.strip(),
        code=_template_code(next_id),
        title=payload.temp_title.strip(),
        sort_order=payload.sort_order if payload.sort_order is not None else next_id,
        is_system=payload.is_system,
    )
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return _to_response(item)


@router.patch("/{template_uuid}", response_model=TemplateItem)
async def update_template(
    template_uuid: uuid.UUID,
    payload: TemplateUpdate,
    session: AsyncSession = Depends(get_db_session),
) -> TemplateItem:
    item = await session.get(Template, template_uuid)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found.")
    await require_admin_if_present(session, payload.admin_id)

    item.admin_id = payload.admin_id
    item.temp_id = payload.temp_id
    item.temp_title = payload.temp_title.strip()
    item.code = _template_code(payload.temp_id)
    item.title = payload.temp_title.strip()
    item.sort_order = payload.sort_order
    item.is_system = payload.is_system

    await session.commit()
    await session.refresh(item)
    return _to_response(item)


@router.delete("/{template_uuid}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(template_uuid: uuid.UUID, session: AsyncSession = Depends(get_db_session)) -> Response:
    item = await session.get(Template, template_uuid)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found.")

    await session.delete(item)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
