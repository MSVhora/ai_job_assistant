import logging

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text

from app.adapters.llm import is_llm_configured
from app.core.db import engine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["health"])


class HealthResponse(BaseModel):
    status: str
    database: bool
    llm_configured: bool


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    try:
        async with engine.connect() as connection:
            await connection.execute(text("select 1"))
        database_ok = True
    except Exception:
        logger.warning("health check: database unreachable", exc_info=True)
        database_ok = False
    llm_ok = is_llm_configured()
    return HealthResponse(
        status="ok" if database_ok else "degraded",
        database=database_ok,
        llm_configured=llm_ok,
    )
