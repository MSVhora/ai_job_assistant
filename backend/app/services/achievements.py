import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import load_only

from app.core.config import get_settings
from app.core.pagination import DEFAULT_PAGE, Pagination
from app.models import Achievement, AchievementEvidence, AchievementStatus
from app.schemas.achievement import AchievementResponse, EvidenceLinkResponse
from app.services.evidence_items import candidate_id_or_none
from app.services.resume_priority import CONFIRMED_METRICS, base_priority


@dataclass(frozen=True)
class AchievementFilters:
    status: AchievementStatus = AchievementStatus.draft
    project_key: str | None = None
    employer: str | None = None
    employer_kind: Literal["personal", "unassigned"] | None = None
    impact_type: str | None = None
    has_metric: bool | None = None
    private: bool | None = None
    stale: bool | None = None
    sort: Literal["rank", "recent"] = "rank"


def _by_employer(
    query: Select[tuple[Achievement]], filters: AchievementFilters
) -> Select[tuple[Achievement]]:
    company = Achievement.employer_ref["company"].as_string()
    kind = Achievement.employer_ref["kind"].as_string()
    if filters.employer is not None:
        return query.where(company == filters.employer)
    if filters.employer_kind == "personal":
        return query.where(kind == "personal")
    if filters.employer_kind == "unassigned":
        return query.where(
            or_(company.is_(None), company == ""), or_(kind.is_(None), kind != "personal")
        )
    return query


def _filtered(candidate_id: uuid.UUID, filters: AchievementFilters) -> Select[tuple[Achievement]]:
    query = select(Achievement).where(
        Achievement.candidate_id == candidate_id, Achievement.status == filters.status
    )
    if filters.project_key is not None:
        query = query.where(Achievement.project_key == filters.project_key)
    query = _by_employer(query, filters)
    if filters.impact_type is not None:
        query = query.where(Achievement.impact_type == filters.impact_type)
    if filters.has_metric is not None:
        confirmed = or_(
            *(Achievement.metrics.contains([{"verified": kind}]) for kind in CONFIRMED_METRICS)
        )
        query = query.where(confirmed if filters.has_metric else ~confirmed)
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


async def evidence_counts(
    session: AsyncSession, achievement_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, int]:
    if not achievement_ids:
        return {}
    counted = await session.execute(
        select(AchievementEvidence.achievement_id, func.count())
        .where(AchievementEvidence.achievement_id.in_(achievement_ids))
        .group_by(AchievementEvidence.achievement_id)
    )
    return dict(counted.tuples().all())


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


RANK_COLUMNS = (
    Achievement.metrics,
    Achievement.impact_type,
    Achievement.difficulty,
    Achievement.time_start,
    Achievement.time_end,
    Achievement.created_at,
)


async def _ranked_ids(session: AsyncSession, query: Select[tuple[Achievement]]) -> list[uuid.UUID]:
    """Ids best first by the resume builder's base priority (impact, metric, difficulty, recency);
    more evidence, then newer, break ties."""
    rows = (await session.execute(query.options(load_only(*RANK_COLUMNS)))).scalars().all()
    counts = await evidence_counts(session, [row.id for row in rows])
    settings, today = get_settings(), datetime.now(UTC).date()
    scored = sorted(
        rows,
        key=lambda row: (
            -base_priority(row, today, settings),
            -counts.get(row.id, 0),
            -row.created_at.timestamp(),
            str(row.id),
        ),
    )
    return [row.id for row in scored]


async def list_achievements(
    session: AsyncSession, filters: AchievementFilters, page: Pagination = DEFAULT_PAGE
) -> list[AchievementResponse]:
    candidate_id = await candidate_id_or_none(session)
    if candidate_id is None:
        return []
    query = _filtered(candidate_id, filters)
    if filters.sort == "rank":
        ids = (await _ranked_ids(session, query))[page.offset : page.offset + page.limit]
        found = (
            (await session.execute(select(Achievement).where(Achievement.id.in_(ids))))
            .scalars()
            .all()
        )
        by_id = {row.id: row for row in found}
        return await build_responses(session, [by_id[achievement_id] for achievement_id in ids])
    query = query.order_by(Achievement.created_at.desc(), Achievement.id)
    rows = list((await session.execute(query.limit(page.limit).offset(page.offset))).scalars())
    return await build_responses(session, rows)
