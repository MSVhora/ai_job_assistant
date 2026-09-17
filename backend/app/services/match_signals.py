"""Match engagement signal recording (#39).

Implicit signals ride behavior the user already exhibits: `first_opened_at`
fires from the frontend's detail-panel open (the server stays idempotent —
first-write-wins), `clicked_apply_at` rides the server-side `/apply` redirect
so the timestamp is trustworthy without trusting the client. `saved_at` /
`dismissed_at` are one-click explicit kinds; `unsave`/`undismiss` clear them
so a hidden-then-regretted match stays recoverable. Signals never touch
scoring — they feed query tuning only.
"""

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import MatchNotFoundError
from app.models import JobPosting, Match
from app.schemas.job_search import JobPostingSummary
from app.schemas.matching import MatchResponse, MatchSignalKind

logger = logging.getLogger(__name__)

_SET_KINDS: dict[MatchSignalKind, str] = {
    MatchSignalKind.open: "first_opened_at",
    MatchSignalKind.save: "saved_at",
    MatchSignalKind.dismiss: "dismissed_at",
}
_CLEAR_KINDS: dict[MatchSignalKind, str] = {
    MatchSignalKind.unsave: "saved_at",
    MatchSignalKind.undismiss: "dismissed_at",
}


def match_response(match: Match, posting: JobPosting) -> MatchResponse:
    return MatchResponse(
        id=match.id,
        job_posting=JobPostingSummary.from_posting(posting),
        vector_score=match.vector_score,
        skill_score=match.skill_score,
        recency_score=match.recency_score,
        salary_score=match.salary_score,
        role_fit=match.role_fit,
        company_fit=match.company_fit,
        final_score=match.final_score,
        rationale=match.rationale,
        created_at=match.created_at,
        updated_at=match.updated_at,
        first_opened_at=match.first_opened_at,
        clicked_apply_at=match.clicked_apply_at,
        saved_at=match.saved_at,
        dismissed_at=match.dismissed_at,
    )


async def _load_match(session: AsyncSession, match_id: uuid.UUID) -> tuple[Match, JobPosting]:
    row = (
        await session.execute(
            select(Match, JobPosting)
            .join(JobPosting, Match.job_posting_id == JobPosting.id)
            .where(Match.id == match_id)
        )
    ).first()
    if row is None:
        raise MatchNotFoundError()
    return row[0], row[1]


async def record_match_signal(
    session: AsyncSession, match_id: uuid.UUID, kind: MatchSignalKind
) -> MatchResponse:
    match, posting = await _load_match(session, match_id)
    now = datetime.now(UTC)
    column = _SET_KINDS.get(kind)
    if column is not None:
        if getattr(match, column) is None:
            setattr(match, column, now)
            logger.info(
                "match.signal kind=%s match_id=%s",
                kind.value,
                match_id,
            )
    else:
        clear_column = _CLEAR_KINDS[kind]
        if getattr(match, clear_column) is not None:
            setattr(match, clear_column, None)
            logger.info("match.signal kind=%s match_id=%s", kind.value, match_id)
    await session.flush()
    # onupdate expires `updated_at`; re-load inside the greenlet before
    # serialization (raw attribute access would lazy-IO outside async).
    await session.refresh(match)
    return match_response(match, posting)


async def resolve_apply_target(session: AsyncSession, match_id: uuid.UUID) -> str:
    """Record the apply click (first hit wins) and return the redirect target.

    A missing posting URL is a 404 recorded *before* any timestamp write — a
    dead link must not fabricate an engagement signal.
    """
    match, posting = await _load_match(session, match_id)
    if not posting.url:
        raise MatchNotFoundError("job posting has no external apply URL")
    if match.clicked_apply_at is None:
        match.clicked_apply_at = datetime.now(UTC)
        logger.info("match.signal kind=apply_clicked match_id=%s", match_id)
        await session.flush()
    return posting.url
