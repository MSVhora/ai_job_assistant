from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db
from app.schemas.ats import AtsScoreRequest, AtsScoreResponse
from app.services import ats_scoring

router = APIRouter(prefix="/api", tags=["ats"])


@router.post("/ats/score", response_model=AtsScoreResponse)
async def score_ats(
    payload: AtsScoreRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AtsScoreResponse:
    return await ats_scoring.score_ats(session, payload)
