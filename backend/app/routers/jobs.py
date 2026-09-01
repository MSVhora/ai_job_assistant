import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.job_sources import registry
from app.deps import get_db
from app.schemas.job_search import (
    JobSearchRequest,
    JobSearchStartResponse,
    JobSearchStatusResponse,
    SourceInfoResponse,
)
from app.services import ingestion

router = APIRouter(prefix="/api", tags=["jobs"])


@router.post("/jobs/search", response_model=JobSearchStartResponse, status_code=202)
async def start_job_search(
    payload: JobSearchRequest,
    background_tasks: BackgroundTasks,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> JobSearchStartResponse:
    return await ingestion.start_search(session, background_tasks, payload)


@router.get("/jobs/searches/{search_id}", response_model=JobSearchStatusResponse)
async def get_job_search_status(
    search_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> JobSearchStatusResponse:
    return await ingestion.get_search_status(session, search_id)


@router.get("/sources", response_model=list[SourceInfoResponse])
async def list_sources() -> list[SourceInfoResponse]:
    return [
        SourceInfoResponse(
            name=source.name,
            is_official_api=source.is_official_api,
            disclosure_required=source.disclosure_required,
            is_configured=source.is_configured(),
        )
        for source in registry.all_sources()
    ]
