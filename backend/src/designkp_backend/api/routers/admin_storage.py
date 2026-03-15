from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import FileResponse, Response
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from designkp_backend.db.dependencies import get_db_session
from designkp_backend.db.models.catalog import ParamGroup, PartKind
from designkp_backend.services.admin_access import require_admin
from designkp_backend.services.admin_storage import (
    csv_bytes,
    normalize_icon_file_name,
    resolve_admin_icon_path,
    save_param_group_icon,
    write_table_snapshot,
)

router = APIRouter(prefix="/admin-storage", tags=["admin_storage"])


def _part_kind_headers() -> list[str]:
    return ["part_kind_id", "part_kind_code", "org_part_kind_title", "admin_mode"]


def _param_group_headers() -> list[str]:
    return [
        "param_group_id",
        "param_group_code",
        "org_param_group_title",
        "param_group_icon_path",
        "ui_order",
        "admin_mode",
    ]


async def _part_kind_rows(session: AsyncSession, admin_id: uuid.UUID) -> list[list[object]]:
    rows = (
        await session.scalars(
            select(PartKind)
            .where(or_(PartKind.admin_id.is_(None), PartKind.admin_id == admin_id))
            .order_by(PartKind.sort_order.asc(), PartKind.part_kind_id.asc())
        )
    ).all()
    return [
        [
            row.part_kind_id,
            row.part_kind_code,
            row.org_part_kind_title,
            "system" if row.admin_id is None else "admin",
        ]
        for row in rows
    ]


async def _param_group_rows(session: AsyncSession, admin_id: uuid.UUID) -> list[list[object]]:
    rows = (
        await session.scalars(
            select(ParamGroup)
            .where(or_(ParamGroup.admin_id.is_(None), ParamGroup.admin_id == admin_id))
            .order_by(ParamGroup.ui_order.asc(), ParamGroup.param_group_id.asc())
        )
    ).all()
    return [
        [
            row.param_group_id,
            row.param_group_code,
            row.org_param_group_title,
            normalize_icon_file_name(row.param_group_icon_path) or "",
            row.ui_order,
            "system" if row.admin_id is None else "admin",
        ]
        for row in rows
    ]


@router.get("/{admin_id}/tables/part-kinds/export")
async def export_part_kinds(admin_id: uuid.UUID, session: AsyncSession = Depends(get_db_session)) -> Response:
    await require_admin(session, admin_id)
    headers = _part_kind_headers()
    rows = await _part_kind_rows(session, admin_id)
    write_table_snapshot(admin_id, "part_kinds", headers, rows)
    return Response(
        content=csv_bytes(headers, rows),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="part_kinds_excel_template.csv"'},
    )


@router.get("/{admin_id}/tables/param-groups/export")
async def export_param_groups(admin_id: uuid.UUID, session: AsyncSession = Depends(get_db_session)) -> Response:
    await require_admin(session, admin_id)
    headers = _param_group_headers()
    rows = await _param_group_rows(session, admin_id)
    write_table_snapshot(admin_id, "param_groups", headers, rows)
    return Response(
        content=csv_bytes(headers, rows),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="param_groups_excel_template.csv"'},
    )


@router.post("/{admin_id}/param-group-icons")
async def upload_param_group_icon(
    admin_id: uuid.UUID,
    slug_hint: str = Query(..., min_length=1, max_length=64),
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, str]:
    await require_admin(session, admin_id)
    file_name, disk_path = await save_param_group_icon(admin_id, file, slug_hint=slug_hint)
    return {
        "icon_path": file_name,
        "file_name": disk_path.name,
    }


@router.get("/{admin_id}/icons/{file_name}")
async def get_admin_icon(admin_id: uuid.UUID, file_name: str, session: AsyncSession = Depends(get_db_session)) -> FileResponse:
    await require_admin(session, admin_id)
    target = resolve_admin_icon_path(admin_id, file_name)
    return FileResponse(target)
