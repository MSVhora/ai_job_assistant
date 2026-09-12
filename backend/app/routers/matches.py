from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db
from app.schemas.matching import MatchQueryParams, MatchResponse
from app.services import matching

router = APIRouter(prefix="/api", tags=["matches"])


@router.get("/matches", response_model=list[MatchResponse])
async def list_matches(
    params: Annotated[MatchQueryParams, Query()],
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[MatchResponse]:
    total = await matching.count_matches(session, params)
    response.headers["X-Total-Count"] = str(total)
    response.headers["Access-Control-Expose-Headers"] = "X-Total-Count"
    return await matching.list_matches(session, params)
