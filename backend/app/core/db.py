from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


engine = create_async_engine(get_settings().database_url, pool_pre_ping=True)
session_factory = async_sessionmaker(engine, expire_on_commit=False)


class DbCommitMiddleware:
    """Commit the request session before the response reaches the client.

    A yield-dependency teardown runs after the response has been sent, so
    committing there lets a fast client act on the response before the
    transaction lands (upload -> extract read the uncommitted row). The commit
    therefore happens on http.response.start; unhandled errors roll back.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] == "OPTIONS":
            await self.app(scope, receive, send)
            return

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                session = scope.get("db_session")
                if session is not None and session.in_transaction():
                    await session.commit()
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:
            session = scope.get("db_session")
            if session is not None:
                await session.rollback()
            raise
