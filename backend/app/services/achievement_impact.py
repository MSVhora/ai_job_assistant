"""The add-impact queue: the top achievements that have no confirmed metric, so the user can supply
the real number (commits rarely contain one) or say there is none."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import Pagination
from app.models import Achievement, AchievementRevisionSource, AchievementStatus
from app.schemas.achievement import AchievementResponse, AddImpactRequest
from app.services.achievement_review import add_revision, owned_achievement, respond
from app.services.achievements import build_responses, has_confirmed_metric, ranked_ids
from app.services.evidence_items import candidate_id_or_none

IMPACT_SKIPPED = "impact_skipped"
QUEUE_STATUSES = (AchievementStatus.draft, AchievementStatus.approved)


async def impact_queue(
    session: AsyncSession, page: Pagination
) -> tuple[list[AchievementResponse], int]:
    """Best first by the shared priority; the total is how many qualify, not just this page."""
    candidate_id = await candidate_id_or_none(session)
    if candidate_id is None:
        return [], 0
    query = select(Achievement).where(
        Achievement.candidate_id == candidate_id,
        Achievement.status.in_(QUEUE_STATUSES),
        ~has_confirmed_metric(),
        ~Achievement.review_flags.contains([IMPACT_SKIPPED]),
    )
    ids = await ranked_ids(session, query)
    chosen = ids[page.offset : page.offset + page.limit]
    found = (
        (await session.execute(select(Achievement).where(Achievement.id.in_(chosen))))
        .scalars()
        .all()
    )
    by_id = {row.id: row for row in found}
    return await build_responses(session, [by_id[item] for item in chosen]), len(ids)


async def add_impact(
    session: AsyncSession, achievement_id: uuid.UUID, payload: AddImpactRequest
) -> AchievementResponse:
    achievement = await owned_achievement(session, achievement_id)
    achievement.metrics = [
        *achievement.metrics,
        {"text": payload.text, "source_quote": "", "evidence_ids": [], "verified": "user"},
    ]
    achievement.review_flags = [flag for flag in achievement.review_flags if flag != IMPACT_SKIPPED]
    achievement.edited_by_user = True
    add_revision(
        session,
        achievement.id,
        AchievementRevisionSource.metric_confirmation,
        {"added": {"text": payload.text, "verified": "user"}},
    )
    return await respond(session, achievement)


async def skip_impact(session: AsyncSession, achievement_id: uuid.UUID) -> AchievementResponse:
    achievement = await owned_achievement(session, achievement_id)
    if IMPACT_SKIPPED not in achievement.review_flags:
        achievement.review_flags = [*achievement.review_flags, IMPACT_SKIPPED]
        add_revision(
            session,
            achievement.id,
            AchievementRevisionSource.manual_edit,
            {"review_flags": {"added": [IMPACT_SKIPPED]}},
        )
    return await respond(session, achievement)
