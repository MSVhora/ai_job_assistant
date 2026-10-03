import uuid
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import DEFAULT_PAGE, Pagination
from app.models import Achievement, AchievementEvidence, AchievementStatus
from app.schemas.achievement import AchievementResponse, EvidenceLinkResponse
from app.services.evidence_items import candidate_id_or_none


@dataclass(frozen=True)
class AchievementFilters:
    status: AchievementStatus = AchievementStatus.draft
    project_key: str | None = None
    private: bool | None = None
    stale: bool | None = None
    sort: Literal["rank", "recent"] = "rank"


def _filtered(candidate_id: uuid.UUID, filters: AchievementFilters) -> Select[tuple[Achievement]]:
    query = select(Achievement).where(
        Achievement.candidate_id == candidate_id, Achievement.status == filters.status
    )
    if filters.project_key is not None:
        query = query.where(Achievement.project_key == filters.project_key)
    if filters.private is not None:
        query = query.where(Achievement.derived_from_private.is_(filters.private))
    if filters.stale is not None:
        stale = Achievement.evidence_stale_at.is_not(None)
        query = query.where(stale if filters.stale else ~stale)
    return query


async def count_achievements(session: AsyncSession, filters: AchievementFilters) -> int:
    candidate_id = await candidate_id_or_none(session)
    if candidate_id is None:
        return 0
    subquery = _filtered(candidate_id, filters).subquery()
    return (await session.execute(select(func.count()).select_from(subquery))).scalar_one()


async def build_responses(
    session: AsyncSession, rows: list[Achievement]
) -> list[AchievementResponse]:
    links: dict[uuid.UUID, list[EvidenceLinkResponse]] = {}
    if rows:
        evidence = (
            (
                await session.execute(
                    select(AchievementEvidence)
                    .where(AchievementEvidence.achievement_id.in_([row.id for row in rows]))
                    .order_by(AchievementEvidence.role.desc(), AchievementEvidence.id)
                )
            )
            .scalars()
            .all()
        )
        for link in evidence:
            links.setdefault(link.achievement_id, []).append(
                EvidenceLinkResponse(item_id=link.item_id, role=link.role, quote=link.quote)
            )
    responses: list[AchievementResponse] = []
    for row in rows:
        response = AchievementResponse.model_validate(row)
        response.evidence = links.get(row.id, [])
        responses.append(response)
    return responses


async def list_achievements(
    session: AsyncSession, filters: AchievementFilters, page: Pagination = DEFAULT_PAGE
) -> list[AchievementResponse]:
    candidate_id = await candidate_id_or_none(session)
    if candidate_id is None:
        return []
    query = _filtered(candidate_id, filters)
    if filters.sort == "rank":
        evidence_count = (
            select(func.count())
            .select_from(AchievementEvidence)
            .where(AchievementEvidence.achievement_id == Achievement.id)
            .correlate(Achievement)
            .scalar_subquery()
        )
        query = query.order_by(
            (Achievement.difficulty * (1 + evidence_count)).desc(),
            Achievement.created_at.desc(),
            Achievement.id,
        )
    else:
        query = query.order_by(Achievement.created_at.desc(), Achievement.id)
    rows = list((await session.execute(query.limit(page.limit).offset(page.offset))).scalars())
    return await build_responses(session, rows)
