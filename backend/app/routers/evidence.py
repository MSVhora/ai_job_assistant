import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import SEARCHES_PAGE, TOTAL_COUNT_HEADER, Pagination
from app.deps import get_db, pagination
from app.models import EvidenceItemStatus, EvidenceKind
from app.schemas.evidence import (
    ChunkSummaryResponse,
    EmployerOption,
    EvidenceStatusResponse,
    ItemResponse,
    ItemUpdate,
    LinkCreate,
    NoteCreate,
    NoteUpdate,
    ResumeIngestRequest,
    ResumeIngestResponse,
    ScopeResponse,
    ScopeUpdateRequest,
    SyncRequest,
    SyncRunResponse,
    SyncStartResponse,
)
from app.services import (
    evidence_chunks,
    evidence_items,
    evidence_notes,
    evidence_sync,
)
from app.services.evidence_pipeline import resume_ingest

router = APIRouter(prefix="/api/evidence", tags=["evidence"])


@router.get("/github/status", response_model=EvidenceStatusResponse)
async def github_status(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> EvidenceStatusResponse:
    return await evidence_sync.get_status(session)


@router.get("/employers", response_model=list[EmployerOption])
async def list_employers(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[EmployerOption]:
    return await evidence_sync.employer_options(session)


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


async def _rebuild_later(session: AsyncSession, background_tasks: BackgroundTasks) -> None:
    candidate_id = await evidence_items.candidate_id_or_none(session)
    if candidate_id is not None:
        background_tasks.add_task(evidence_chunks.rebuild_chunks_background, candidate_id)


@router.post("/notes", response_model=ItemResponse, status_code=201)
async def create_note(
    payload: NoteCreate,
    background_tasks: BackgroundTasks,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ItemResponse:
    created = await evidence_notes.create_note(session, payload)
    await _rebuild_later(session, background_tasks)
    return created


@router.get("/notes", response_model=list[ItemResponse])
async def list_notes(
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[Pagination, Depends(pagination())],
) -> list[ItemResponse]:
    notes, total = await evidence_notes.list_notes(session, page)
    response.headers[TOTAL_COUNT_HEADER] = str(total)
    return notes


@router.patch("/notes/{item_id}", response_model=ItemResponse)
async def update_note(
    item_id: uuid.UUID,
    payload: NoteUpdate,
    background_tasks: BackgroundTasks,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ItemResponse:
    updated, _ = await evidence_notes.update_note(session, item_id, payload)
    await _rebuild_later(session, background_tasks)
    return updated


@router.delete("/notes/{item_id}", status_code=204, response_class=Response)
async def delete_note(
    item_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    await evidence_notes.delete_note(session, item_id)
    await _rebuild_later(session, background_tasks)
    return Response(status_code=204)


@router.post("/links", response_model=ItemResponse, status_code=201)
async def create_link(
    payload: LinkCreate,
    background_tasks: BackgroundTasks,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ItemResponse:
    created = await evidence_notes.create_link(session, payload)
    await _rebuild_later(session, background_tasks)
    return created


@router.post("/resume/ingest", response_model=ResumeIngestResponse)
async def ingest_resume(
    payload: ResumeIngestRequest,
    background_tasks: BackgroundTasks,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResumeIngestResponse:
    result = await resume_ingest.ingest_profile(session, payload.profile_id)
    await _rebuild_later(session, background_tasks)
    return result


def _item_filters(
    kind: Annotated[EvidenceKind | None, Query()] = None,
    project_key: Annotated[str | None, Query(max_length=255)] = None,
    status: Annotated[EvidenceItemStatus, Query()] = EvidenceItemStatus.kept,
    is_private: Annotated[bool | None, Query()] = None,
) -> evidence_items.ItemFilters:
    return evidence_items.ItemFilters(
        kind=kind, project_key=project_key, status=status, is_private=is_private
    )


@router.get("/items", response_model=list[ItemResponse])
async def list_items(
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db)],
    filters: Annotated[evidence_items.ItemFilters, Depends(_item_filters)],
    page: Annotated[Pagination, Depends(pagination())],
) -> list[ItemResponse]:
    response.headers[TOTAL_COUNT_HEADER] = str(await evidence_items.count_items(session, filters))
    return await evidence_items.list_items(session, filters, page)


@router.get("/items/{item_id}", response_model=ItemResponse)
async def get_item(
    item_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ItemResponse:
    return await evidence_items.get_item(session, item_id)


@router.patch("/items/{item_id}", response_model=ItemResponse)
async def update_item(
    item_id: uuid.UUID,
    payload: ItemUpdate,
    background_tasks: BackgroundTasks,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ItemResponse:
    updated, _ = await evidence_items.set_item_status(
        session, item_id, EvidenceItemStatus(payload.status)
    )
    await _rebuild_later(session, background_tasks)
    return updated


@router.get("/chunks/summary", response_model=ChunkSummaryResponse)
async def chunks_summary(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ChunkSummaryResponse:
    return await evidence_chunks.chunk_summary(session)
