import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db
from app.schemas.matching import (
    MatchQueryParams,
    MatchResponse,
    MatchSignalRequest,
)
from app.services import match_signals, matching

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


@router.post("/matches/{match_id}/signals", response_model=MatchResponse)
async def record_match_signal(
    match_id: uuid.UUID,
    payload: MatchSignalRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> MatchResponse:
    return await match_signals.record_match_signal(session, match_id, payload.kind)


@router.get("/matches/{match_id}/apply", response_class=RedirectResponse, status_code=302)
async def apply_redirect(
    match_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> RedirectResponse:
    # Redirect endpoint, not JSON: the click must transit the server for
    # `clicked_apply_at` to be an honest engagement signal (#39).
    target = await match_signals.resolve_apply_target(session, match_id)
    return RedirectResponse(target, status_code=302)
