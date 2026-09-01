from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import session_factory


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    existing = request.scope.get("db_session")
    if existing is not None:
        yield existing
        return
    async with session_factory() as session:
        request.scope["db_session"] = session
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
