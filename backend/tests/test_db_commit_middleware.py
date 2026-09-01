import pytest
from sqlalchemy import func, select

from app.core.db import DbCommitMiddleware, session_factory
from app.models import Candidate

pytestmark = pytest.mark.usefixtures("clean_tables")


async def test_commit_lands_before_response_start_reaches_client() -> None:
    async with session_factory() as writer:
        scope: dict = {"type": "http", "method": "POST", "db_session": writer}

        async def inner_app(scope: dict, receive, send) -> None:
            session = scope["db_session"]
            session.add(Candidate())
            await session.flush()
            await send({"type": "http.response.start", "status": 201, "headers": []})
            await send({"type": "http.response.body", "body": b"{}"})

        async def receive() -> dict:
            return {"type": "http.request"}

        async def send(message: dict) -> None:
            if message["type"] == "http.response.start":
                async with session_factory() as observer:
                    total = (
                        await observer.execute(select(func.count()).select_from(Candidate))
                    ).scalar_one()
                assert total == 1, "client-visible response must imply committed state"

        await DbCommitMiddleware(inner_app)(scope, receive, send)


async def test_unhandled_error_rolls_back_pending_writes() -> None:
    async with session_factory() as writer:
        scope: dict = {"type": "http", "method": "POST", "db_session": writer}

        async def inner_app(scope: dict, receive, send) -> None:
            scope["db_session"].add(Candidate())
            await scope["db_session"].flush()
            raise RuntimeError("boom")

        async def receive() -> dict:
            return {"type": "http.request"}

        async def send(message: dict) -> None:
            raise AssertionError("error responses must not be sent for unhandled errors")

        with pytest.raises(RuntimeError):
            await DbCommitMiddleware(inner_app)(scope, receive, send)

    async with session_factory() as observer:
        total = (await observer.execute(select(func.count()).select_from(Candidate))).scalar_one()
    assert total == 0
