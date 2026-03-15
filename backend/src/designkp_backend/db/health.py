from __future__ import annotations

import asyncio

from sqlalchemy import text

from .session import session_scope


async def ping_database() -> bool:
    async with session_scope() as session:
        await session.execute(text("SELECT 1"))
    return True


if __name__ == "__main__":
    asyncio.run(ping_database())
    print("Database health check OK.")
