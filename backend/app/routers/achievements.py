import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import TOTAL_COUNT_HEADER, Pagination
from app.deps import get_db, pagination
from app.models import AchievementStatus
from app.schemas.achievement import (
    AchievementResponse,
    AchievementUpdate,
    BulkApproveRequest,
    BulkApproveResponse,
    BulkEligibleResponse,
    ConfirmMetricRequest,
    EvidenceLinkCreate,
    ExtractionEstimateResponse,
    ExtractionRunResponse,
    ExtractionStartResponse,
    ExtractRequest,
    MergeProposalResponse,
    MergeRequest,
    RevisionResponse,
    SplitRequest,
)
from app.services import achievement_extraction, achievement_merge, achievement_review, achievements

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


def _achievement_filters(
    status: Annotated[AchievementStatus, Query()] = AchievementStatus.draft,
    project_key: Annotated[str | None, Query(max_length=255)] = None,
    private: Annotated[bool | None, Query()] = None,
    stale: Annotated[bool | None, Query()] = None,
    sort: Annotated[Literal["rank", "recent"], Query()] = "rank",
) -> achievements.AchievementFilters:
    return achievements.AchievementFilters(
        status=status, project_key=project_key, private=private, stale=stale, sort=sort
    )


@router.get("/achievements", response_model=list[AchievementResponse])
async def list_achievements(
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db)],
    filters: Annotated[achievements.AchievementFilters, Depends(_achievement_filters)],
    page: Annotated[Pagination, Depends(pagination())],
) -> list[AchievementResponse]:
    total = await achievements.count_achievements(session, filters)
    response.headers[TOTAL_COUNT_HEADER] = str(total)
    return await achievements.list_achievements(session, filters, page)


@router.get("/achievements/merge-proposals", response_model=list[MergeProposalResponse])
async def merge_proposals(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[MergeProposalResponse]:
    return await achievement_merge.propose_merges(session)


@router.post("/achievements/merge", response_model=AchievementResponse, status_code=201)
async def merge_achievements(
    payload: MergeRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AchievementResponse:
    return await achievement_merge.merge(session, payload)


@router.get("/achievements/bulk-approve/eligible", response_model=BulkEligibleResponse)
async def bulk_approve_eligible(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> BulkEligibleResponse:
    return await achievement_review.bulk_eligible(session)


@router.post("/achievements/bulk-approve", response_model=BulkApproveResponse)
async def bulk_approve(
    payload: BulkApproveRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> BulkApproveResponse:
    return await achievement_review.bulk_approve(session, payload.ids)


@router.get("/achievements/{achievement_id}", response_model=AchievementResponse)
async def get_achievement(
    achievement_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AchievementResponse:
    return await achievement_review.get_achievement(session, achievement_id)


@router.patch("/achievements/{achievement_id}", response_model=AchievementResponse)
async def edit_achievement(
    achievement_id: uuid.UUID,
    payload: AchievementUpdate,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AchievementResponse:
    return await achievement_review.edit(session, achievement_id, payload)


@router.post("/achievements/{achievement_id}/approve", response_model=AchievementResponse)
async def approve_achievement(
    achievement_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AchievementResponse:
    return await achievement_review.transition(session, achievement_id, AchievementStatus.approved)


@router.post("/achievements/{achievement_id}/reject", response_model=AchievementResponse)
async def reject_achievement(
    achievement_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AchievementResponse:
    return await achievement_review.transition(session, achievement_id, AchievementStatus.rejected)


@router.post("/achievements/{achievement_id}/archive", response_model=AchievementResponse)
async def archive_achievement(
    achievement_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AchievementResponse:
    return await achievement_review.transition(session, achievement_id, AchievementStatus.archived)


@router.post("/achievements/{achievement_id}/unapprove", response_model=AchievementResponse)
async def unapprove_achievement(
    achievement_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AchievementResponse:
    return await achievement_review.transition(session, achievement_id, AchievementStatus.draft)


@router.post("/achievements/{achievement_id}/restore", response_model=AchievementResponse)
async def restore_achievement(
    achievement_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AchievementResponse:
    return await achievement_review.transition(session, achievement_id, AchievementStatus.draft)


@router.post("/achievements/{achievement_id}/acknowledge", response_model=AchievementResponse)
async def acknowledge_achievement(
    achievement_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AchievementResponse:
    return await achievement_review.acknowledge(session, achievement_id)


@router.post("/achievements/{achievement_id}/confirm-metric", response_model=AchievementResponse)
async def confirm_metric(
    achievement_id: uuid.UUID,
    payload: ConfirmMetricRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AchievementResponse:
    return await achievement_review.confirm_metric(session, achievement_id, payload)


@router.post(
    "/achievements/{achievement_id}/split", response_model=AchievementResponse, status_code=201
)
async def split_achievement(
    achievement_id: uuid.UUID,
    payload: SplitRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AchievementResponse:
    return await achievement_merge.split(session, achievement_id, payload)


@router.post(
    "/achievements/{achievement_id}/evidence", response_model=AchievementResponse, status_code=201
)
async def link_evidence(
    achievement_id: uuid.UUID,
    payload: EvidenceLinkCreate,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AchievementResponse:
    return await achievement_review.link_evidence(session, achievement_id, payload)


@router.delete(
    "/achievements/{achievement_id}/evidence/{item_id}", response_model=AchievementResponse
)
async def unlink_evidence(
    achievement_id: uuid.UUID,
    item_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AchievementResponse:
    return await achievement_review.unlink_evidence(session, achievement_id, item_id)


@router.get("/achievements/{achievement_id}/revisions", response_model=list[RevisionResponse])
async def list_revisions(
    achievement_id: uuid.UUID,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[Pagination, Depends(pagination())],
) -> list[RevisionResponse]:
    revisions, total = await achievement_review.list_revisions(session, achievement_id, page)
    response.headers[TOTAL_COUNT_HEADER] = str(total)
    return revisions
