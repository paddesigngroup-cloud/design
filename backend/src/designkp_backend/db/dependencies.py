from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from .session import get_session


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    session = get_session()
    try:
        yield session
    finally:
        await session.close()
