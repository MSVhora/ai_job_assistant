import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import SEARCHES_PAGE, TOTAL_COUNT_HEADER, Pagination
from app.deps import get_db, pagination
from app.schemas.evidence import (
    EvidenceStatusResponse,
    ScopeResponse,
    ScopeUpdateRequest,
    SyncRequest,
    SyncRunResponse,
    SyncStartResponse,
)
from app.services import evidence_sync

router = APIRouter(prefix="/api/evidence", tags=["evidence"])


@router.get("/github/status", response_model=EvidenceStatusResponse)
async def github_status(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> EvidenceStatusResponse:
    return await evidence_sync.get_status(session)


@router.get("/github/scopes", response_model=list[ScopeResponse])
async def list_github_scopes(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[ScopeResponse]:
    return await evidence_sync.list_scopes(session)


@router.patch("/github/scopes", response_model=list[ScopeResponse])
async def update_github_scopes(
    payload: ScopeUpdateRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[ScopeResponse]:
    return await evidence_sync.update_scopes(session, payload)


@router.post("/github/sync", response_model=SyncStartResponse, status_code=202)
async def start_github_sync(
    background_tasks: BackgroundTasks,
    session: Annotated[AsyncSession, Depends(get_db)],
    payload: SyncRequest | None = None,
) -> SyncStartResponse:
    mode = payload.mode if payload is not None else "incremental"
    return await evidence_sync.start_sync(session, background_tasks, mode)


@router.get("/syncs", response_model=list[SyncRunResponse])
async def list_syncs(
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[Pagination, Depends(pagination(SEARCHES_PAGE.limit))],
) -> list[SyncRunResponse]:
    response.headers[TOTAL_COUNT_HEADER] = str(await evidence_sync.count_syncs(session))
    return await evidence_sync.list_syncs(session, page)


@router.get("/syncs/{sync_id}", response_model=SyncRunResponse)
async def get_sync(
    sync_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> SyncRunResponse:
    return await evidence_sync.get_sync(session, sync_id)
