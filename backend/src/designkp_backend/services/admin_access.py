from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from designkp_backend.db.models.account import Admin


async def require_admin(session: AsyncSession, admin_id: uuid.UUID) -> Admin:
    admin = await session.scalar(select(Admin).where(Admin.id == admin_id))
    if not admin:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Admin not found.")
    return admin


async def require_admin_if_present(session: AsyncSession, admin_id: uuid.UUID | None) -> Admin | None:
    if admin_id is None:
        return None
    return await require_admin(session, admin_id)
