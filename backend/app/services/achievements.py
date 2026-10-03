from typing import TYPE_CHECKING

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import DEFAULT_PAGE, Pagination
from app.models import Achievement, AchievementEvidence, AchievementStatus
from app.schemas.achievement import AchievementResponse, EvidenceLinkResponse
from app.services.evidence_items import candidate_id_or_none

if TYPE_CHECKING:
    import uuid


async def count_achievements(session: AsyncSession, status: AchievementStatus) -> int:
    candidate_id = await candidate_id_or_none(session)
    if candidate_id is None:
        return 0
    return (
        await session.execute(
            select(func.count())
            .select_from(Achievement)
            .where(Achievement.candidate_id == candidate_id, Achievement.status == status)
        )
    ).scalar_one()


async def list_achievements(
    session: AsyncSession, status: AchievementStatus, page: Pagination = DEFAULT_PAGE
) -> list[AchievementResponse]:
    candidate_id = await candidate_id_or_none(session)
    if candidate_id is None:
        return []
    rows = (
        (
            await session.execute(
                select(Achievement)
                .where(Achievement.candidate_id == candidate_id, Achievement.status == status)
                .order_by(Achievement.created_at.desc(), Achievement.id)
                .limit(page.limit)
                .offset(page.offset)
            )
        )
        .scalars()
        .all()
    )
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
