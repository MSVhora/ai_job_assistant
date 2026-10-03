import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import TOTAL_COUNT_HEADER, Pagination
from app.deps import get_db, pagination
from app.models import AchievementStatus
from app.schemas.achievement import (
    AchievementResponse,
    ExtractionEstimateResponse,
    ExtractionRunResponse,
    ExtractionStartResponse,
    ExtractRequest,
)
from app.services import achievement_extraction, achievements

router = APIRouter(prefix="/api", tags=["achievements"])


@router.post("/evidence/extract/estimate", response_model=ExtractionEstimateResponse)
async def estimate_extraction(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ExtractionEstimateResponse:
    return await achievement_extraction.estimate(session)


@router.post("/evidence/extract", response_model=ExtractionStartResponse, status_code=202)
async def start_extraction(
    payload: ExtractRequest,
    background_tasks: BackgroundTasks,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ExtractionStartResponse:
    return await achievement_extraction.start_extraction(
        session, background_tasks, payload.confirmed_estimate_id
    )


@router.get("/evidence/extract/runs/{run_id}", response_model=ExtractionRunResponse)
async def get_extraction_run(
    run_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ExtractionRunResponse:
    return await achievement_extraction.get_run(session, run_id)


@router.get("/achievements", response_model=list[AchievementResponse])
async def list_achievements(
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[Pagination, Depends(pagination())],
    status: Annotated[AchievementStatus, Query()] = AchievementStatus.draft,
) -> list[AchievementResponse]:
    response.headers[TOTAL_COUNT_HEADER] = str(
        await achievements.count_achievements(session, status)
    )
    return await achievements.list_achievements(session, status, page)
