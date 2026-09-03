from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db
from app.schemas.matching import MatchQueryParams, MatchResponse
from app.services import matching

router = APIRouter(prefix="/api", tags=["matches"])


@router.get("/matches", response_model=list[MatchResponse])
async def list_matches(
    params: Annotated[MatchQueryParams, Query()],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[MatchResponse]:
    return await matching.list_matches(session, params)
