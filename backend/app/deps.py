from collections.abc import AsyncIterator, Callable
from typing import Annotated

from fastapi import Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import session_factory
from app.core.pagination import DEFAULT_LIST_LIMIT, MAX_LIST_LIMIT, Pagination


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


def pagination(
    default_limit: int = DEFAULT_LIST_LIMIT, max_limit: int = MAX_LIST_LIMIT
) -> Callable[[int, int], Pagination]:
    def dependency(
        limit: Annotated[int, Query(ge=1, le=max_limit)] = default_limit,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> Pagination:
        return Pagination(limit=limit, offset=offset)

    return dependency
