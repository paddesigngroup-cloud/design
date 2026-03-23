from __future__ import annotations

import uuid

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from designkp_backend.db.models.catalog import Param, SubCategory, SubCategoryParamDefault
from designkp_backend.services.admin_storage import normalize_icon_file_name


def normalize_default_value(value: object) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None


async def get_params_for_scope(session: AsyncSession, admin_id: uuid.UUID | None) -> list[Param]:
    stmt = select(Param).where(Param.admin_id.is_(None))
    if admin_id is not None:
        stmt = select(Param).where(or_(Param.admin_id.is_(None), Param.admin_id == admin_id))
    stmt = stmt.order_by(Param.sort_order.asc(), Param.param_id.asc())
    return (await session.scalars(stmt)).all()


async def sync_defaults_for_sub_categories(session: AsyncSession, items: list[SubCategory]) -> None:
    if not items:
        return
    sub_category_ids = [item.id for item in items if item.id is not None]
    if not sub_category_ids:
        return

    existing_rows = (
        await session.scalars(
            select(SubCategoryParamDefault).where(SubCategoryParamDefault.sub_category_id.in_(sub_category_ids))
        )
    ).all()
    existing_pairs = {(row.sub_category_id, row.param_id) for row in existing_rows}
    params_by_scope: dict[uuid.UUID | None, list[Param]] = {}

    for item in items:
        if item.admin_id not in params_by_scope:
            params_by_scope[item.admin_id] = await get_params_for_scope(session, item.admin_id)
        for param in params_by_scope[item.admin_id]:
            pair = (item.id, param.param_id)
            if pair in existing_pairs:
                continue
            session.add(
                SubCategoryParamDefault(
                    sub_category_id=item.id,
                    param_id=param.param_id,
                    default_value=None,
                    display_title=param.param_title_fa.strip(),
                    description_text=None,
                    icon_path=None,
                    input_mode="value",
                    binary_off_label="0",
                    binary_on_label="1",
                    binary_off_icon_path=None,
                    binary_on_icon_path=None,
                )
            )
            existing_pairs.add(pair)
    for row in existing_rows:
        if not row.display_title:
            param = next((item for item in params_by_scope.get(next((sub.admin_id for sub in items if sub.id == row.sub_category_id), None), []) if item.param_id == row.param_id), None)
            if param:
                row.display_title = param.param_title_fa.strip()
        row.icon_path = normalize_icon_file_name(row.icon_path)
        row.input_mode = row.input_mode if row.input_mode in {"value", "binary"} else "value"
        row.binary_off_label = str(row.binary_off_label or "0").strip() or "0"
        row.binary_on_label = str(row.binary_on_label or "1").strip() or "1"
        row.binary_off_icon_path = normalize_icon_file_name(row.binary_off_icon_path)
        row.binary_on_icon_path = normalize_icon_file_name(row.binary_on_icon_path)
    await session.flush()
