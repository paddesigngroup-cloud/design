from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import FileResponse, Response
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from designkp_backend.db.dependencies import get_db_session
from designkp_backend.db.models.catalog import BaseFormula, Category, Param, ParamGroup, PartFormula, PartKind, SubCategory, SubCategoryParamDefault, Template
from designkp_backend.services.admin_access import require_admin
from designkp_backend.services.admin_storage import (
    finalize_param_group_icon,
    csv_bytes,
    discard_all_staged_icons,
    discard_staged_icon,
    normalize_icon_file_name,
    resolve_admin_icon_path,
    save_param_group_icon,
    write_table_snapshot_async,
)
from designkp_backend.services.sub_category_defaults import get_params_for_scope, sync_defaults_for_sub_categories

router = APIRouter(prefix="/admin-storage", tags=["admin_storage"])


def _part_kind_headers() -> list[str]:
    return ["part_kind_id", "part_kind_code", "org_part_kind_title", "part_scope", "admin_mode"]


def _param_group_headers() -> list[str]:
    return [
        "param_group_id",
        "param_group_code",
        "org_param_group_title",
        "param_group_icon_path",
        "ui_order",
        "show_in_order_attrs",
        "admin_mode",
    ]


def _param_headers() -> list[str]:
    return [
        "param_id",
        "part_kind_id",
        "param_code",
        "param_title_en",
        "param_title_fa",
        "param_group_id",
        "ui_order",
        "admin_mode",
    ]


def _base_formula_headers() -> list[str]:
    return [
        "fo_id",
        "param_formula",
        "formula",
        "admin_mode",
    ]


def _part_formula_headers() -> list[str]:
    return [
        "part_formula_id",
        "part_kind_id",
        "part_sub_kind_id",
        "part_code",
        "part_title",
        "formula_l",
        "formula_w",
        "formula_width",
        "formula_depth",
        "formula_height",
        "formula_cx",
        "formula_cy",
        "formula_cz",
        "door_dependent",
        "admin_mode",
    ]


def _template_headers() -> list[str]:
    return [
        "temp_id",
        "temp_title",
        "admin_mode",
    ]


def _category_headers() -> list[str]:
    return [
        "temp_id",
        "cat_id",
        "cat_title",
        "design_outline_color",
        "admin_mode",
    ]


async def _sub_category_headers(session: AsyncSession, admin_id: uuid.UUID) -> list[str]:
    params = await get_params_for_scope(session, admin_id)
    param_headers: list[str] = []
    for item in params:
        param_headers.extend([
            item.param_code,
            f"{item.param_code}__display_title",
            f"{item.param_code}__description_text",
            f"{item.param_code}__icon_path",
            f"{item.param_code}__input_mode",
            f"{item.param_code}__binary_off_label",
            f"{item.param_code}__binary_on_label",
            f"{item.param_code}__binary_off_icon_path",
            f"{item.param_code}__binary_on_icon_path",
        ])
    return [
        "temp_id",
        "cat_id",
        "sub_cat_id",
        "sub_cat_title",
        *param_headers,
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
            row.part_scope,
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
            1 if row.show_in_order_attrs else 0,
            "system" if row.admin_id is None else "admin",
        ]
        for row in rows
    ]


async def _param_rows(session: AsyncSession, admin_id: uuid.UUID) -> list[list[object]]:
    rows = (
        await session.scalars(
            select(Param)
            .where(or_(Param.admin_id.is_(None), Param.admin_id == admin_id))
            .order_by(Param.sort_order.asc(), Param.param_id.asc())
        )
    ).all()
    return [
        [
            row.param_id,
            row.part_kind_id,
            row.param_code,
            row.param_title_en,
            row.param_title_fa,
            row.param_group_id,
            row.ui_order,
            "system" if row.admin_id is None else "admin",
        ]
        for row in rows
    ]


async def _base_formula_rows(session: AsyncSession, admin_id: uuid.UUID) -> list[list[object]]:
    rows = (
        await session.scalars(
            select(BaseFormula)
            .where(or_(BaseFormula.admin_id.is_(None), BaseFormula.admin_id == admin_id))
            .order_by(BaseFormula.sort_order.asc(), BaseFormula.fo_id.asc())
        )
    ).all()
    return [
        [
            row.fo_id,
            row.param_formula,
            row.formula,
            "system" if row.admin_id is None else "admin",
        ]
        for row in rows
    ]


async def _part_formula_rows(session: AsyncSession, admin_id: uuid.UUID) -> list[list[object]]:
    rows = (
        await session.scalars(
            select(PartFormula)
            .where(or_(PartFormula.admin_id.is_(None), PartFormula.admin_id == admin_id))
            .order_by(PartFormula.sort_order.asc(), PartFormula.part_formula_id.asc())
        )
    ).all()
    return [
        [
            row.part_formula_id,
            row.part_kind_id,
            row.part_sub_kind_id,
            row.part_code,
            row.part_title,
            row.formula_l,
            row.formula_w,
            row.formula_width,
            row.formula_depth,
            row.formula_height,
            row.formula_cx,
            row.formula_cy,
            row.formula_cz,
            1 if row.door_dependent else 0,
            "system" if row.admin_id is None else "admin",
        ]
        for row in rows
    ]


async def _template_rows(session: AsyncSession, admin_id: uuid.UUID) -> list[list[object]]:
    rows = (
        await session.scalars(
            select(Template)
            .where(or_(Template.admin_id.is_(None), Template.admin_id == admin_id))
            .order_by(Template.sort_order.asc(), Template.temp_id.asc())
        )
    ).all()
    return [
        [
            row.temp_id,
            row.temp_title,
            "system" if row.admin_id is None else "admin",
        ]
        for row in rows
    ]


async def _category_rows(session: AsyncSession, admin_id: uuid.UUID) -> list[list[object]]:
    rows = (
        await session.scalars(
            select(Category)
            .where(or_(Category.admin_id.is_(None), Category.admin_id == admin_id))
            .order_by(Category.sort_order.asc(), Category.cat_id.asc())
        )
    ).all()
    return [
        [
            row.temp_id,
            row.cat_id,
            row.cat_title,
            row.design_outline_color or "#7A4A2B",
            "system" if row.admin_id is None else "admin",
        ]
        for row in rows
    ]


async def _sub_category_rows(session: AsyncSession, admin_id: uuid.UUID) -> list[list[object]]:
    items = (
        await session.scalars(
            select(SubCategory)
            .where(
                or_(SubCategory.admin_id.is_(None), SubCategory.admin_id == admin_id),
                SubCategory.deleted_at.is_(None),
            )
            .order_by(SubCategory.sort_order.asc(), SubCategory.sub_cat_id.asc())
        )
    ).all()
    await sync_defaults_for_sub_categories(session, items)
    params = await get_params_for_scope(session, admin_id)
    code_by_param_id = {item.param_id: item.param_code for item in params}
    sub_category_ids = [item.id for item in items]
    defaults = []
    if sub_category_ids:
        defaults = (
            await session.scalars(
                select(SubCategoryParamDefault).where(SubCategoryParamDefault.sub_category_id.in_(sub_category_ids))
            )
        ).all()
    defaults_map: dict[uuid.UUID, dict[str, object]] = {item.id: {} for item in items}
    for row in defaults:
        code = code_by_param_id.get(row.param_id)
        if code:
            defaults_map.setdefault(row.sub_category_id, {})[code] = {
                "default_value": row.default_value or "",
                "display_title": row.display_title or "",
                "description_text": row.description_text or "",
                "icon_path": normalize_icon_file_name(row.icon_path) or "",
                "input_mode": row.input_mode if row.input_mode in {"value", "binary"} else "value",
                "binary_off_label": (row.binary_off_label or "0").strip() or "0",
                "binary_on_label": (row.binary_on_label or "1").strip() or "1",
                "binary_off_icon_path": normalize_icon_file_name(row.binary_off_icon_path) or "",
                "binary_on_icon_path": normalize_icon_file_name(row.binary_on_icon_path) or "",
            }
    return [
        [
            row.temp_id,
            row.cat_id,
            row.sub_cat_id,
            row.sub_cat_title,
            *[
                value
                for param in params
                for value in (
                    defaults_map.get(row.id, {}).get(param.param_code, {}).get("default_value", ""),
                    defaults_map.get(row.id, {}).get(param.param_code, {}).get("display_title", ""),
                    defaults_map.get(row.id, {}).get(param.param_code, {}).get("description_text", ""),
                    defaults_map.get(row.id, {}).get(param.param_code, {}).get("icon_path", ""),
                    defaults_map.get(row.id, {}).get(param.param_code, {}).get("input_mode", "value"),
                    defaults_map.get(row.id, {}).get(param.param_code, {}).get("binary_off_label", "0"),
                    defaults_map.get(row.id, {}).get(param.param_code, {}).get("binary_on_label", "1"),
                    defaults_map.get(row.id, {}).get(param.param_code, {}).get("binary_off_icon_path", ""),
                    defaults_map.get(row.id, {}).get(param.param_code, {}).get("binary_on_icon_path", ""),
                )
            ],
            "system" if row.admin_id is None else "admin",
        ]
        for row in items
    ]


@router.get("/{admin_id}/tables/part-kinds/export")
async def export_part_kinds(admin_id: uuid.UUID, session: AsyncSession = Depends(get_db_session)) -> Response:
    await require_admin(session, admin_id)
    headers = _part_kind_headers()
    rows = await _part_kind_rows(session, admin_id)
    await write_table_snapshot_async(admin_id, "part_kinds", headers, rows)
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
    await write_table_snapshot_async(admin_id, "param_groups", headers, rows)
    return Response(
        content=csv_bytes(headers, rows),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="param_groups_excel_template.csv"'},
    )


@router.get("/{admin_id}/tables/params/export")
async def export_params(admin_id: uuid.UUID, session: AsyncSession = Depends(get_db_session)) -> Response:
    await require_admin(session, admin_id)
    headers = _param_headers()
    rows = await _param_rows(session, admin_id)
    await write_table_snapshot_async(admin_id, "params", headers, rows)
    return Response(
        content=csv_bytes(headers, rows),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="params_excel_template.csv"'},
    )


@router.get("/{admin_id}/tables/base-formulas/export")
async def export_base_formulas(admin_id: uuid.UUID, session: AsyncSession = Depends(get_db_session)) -> Response:
    await require_admin(session, admin_id)
    headers = _base_formula_headers()
    rows = await _base_formula_rows(session, admin_id)
    await write_table_snapshot_async(admin_id, "base_formulas", headers, rows)
    return Response(
        content=csv_bytes(headers, rows),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="base_formulas_excel_template.csv"'},
    )


@router.get("/{admin_id}/tables/part-formulas/export")
async def export_part_formulas(admin_id: uuid.UUID, session: AsyncSession = Depends(get_db_session)) -> Response:
    await require_admin(session, admin_id)
    headers = _part_formula_headers()
    rows = await _part_formula_rows(session, admin_id)
    await write_table_snapshot_async(admin_id, "part_formulas", headers, rows)
    return Response(
        content=csv_bytes(headers, rows),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="part_formulas_excel_template.csv"'},
    )


@router.get("/{admin_id}/tables/templates/export")
async def export_templates(admin_id: uuid.UUID, session: AsyncSession = Depends(get_db_session)) -> Response:
    await require_admin(session, admin_id)
    headers = _template_headers()
    rows = await _template_rows(session, admin_id)
    await write_table_snapshot_async(admin_id, "templates", headers, rows)
    return Response(
        content=csv_bytes(headers, rows),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="templates_excel_template.csv"'},
    )


@router.get("/{admin_id}/tables/categories/export")
async def export_categories(admin_id: uuid.UUID, session: AsyncSession = Depends(get_db_session)) -> Response:
    await require_admin(session, admin_id)
    headers = _category_headers()
    rows = await _category_rows(session, admin_id)
    await write_table_snapshot_async(admin_id, "categories", headers, rows)
    return Response(
        content=csv_bytes(headers, rows),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="categories_excel_template.csv"'},
    )


@router.get("/{admin_id}/tables/sub-categories/export")
async def export_sub_categories(admin_id: uuid.UUID, session: AsyncSession = Depends(get_db_session)) -> Response:
    await require_admin(session, admin_id)
    headers = await _sub_category_headers(session, admin_id)
    rows = await _sub_category_rows(session, admin_id)
    await write_table_snapshot_async(admin_id, "sub_categories", headers, rows)
    return Response(
        content=csv_bytes(headers, rows),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="sub_categories_excel_template.csv"'},
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

@router.post("/{admin_id}/param-group-icons/finalize")
async def finalize_uploaded_param_group_icon(
    admin_id: uuid.UUID,
    file_name: str = Query(..., min_length=1, max_length=255),
    previous_file_name: str | None = Query(default=None, max_length=255),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, str | None]:
    await require_admin(session, admin_id)
    final_name = finalize_param_group_icon(admin_id, file_name, previous_file_name=previous_file_name)
    return {
        "icon_path": final_name,
        "file_name": final_name,
    }

@router.delete("/{admin_id}/param-group-icons/{file_name}", status_code=204)
async def discard_param_group_icon(admin_id: uuid.UUID, file_name: str, session: AsyncSession = Depends(get_db_session)) -> Response:
    await require_admin(session, admin_id)
    discard_staged_icon(admin_id, file_name)
    return Response(status_code=204)


@router.delete("/{admin_id}/param-group-icons", status_code=204)
async def discard_all_param_group_icons(admin_id: uuid.UUID, session: AsyncSession = Depends(get_db_session)) -> Response:
    await require_admin(session, admin_id)
    discard_all_staged_icons(admin_id)
    return Response(status_code=204)


@router.get("/{admin_id}/icons/{file_name}")
async def get_admin_icon(admin_id: uuid.UUID, file_name: str, session: AsyncSession = Depends(get_db_session)) -> FileResponse:
    await require_admin(session, admin_id)
    target = resolve_admin_icon_path(admin_id, file_name)
    return FileResponse(target)
