import uuid
from collections.abc import Sequence
from datetime import date
from typing import TYPE_CHECKING, cast

from sqlalchemy import Float, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.errors import InvalidAchievementInputError
from app.models import (
    Achievement,
    AchievementEvidence,
    AchievementOrigin,
    AchievementRevisionSource,
    AchievementStatus,
)
from app.schemas.achievement import (
    AchievementResponse,
    MergeProposalResponse,
    MergeRequest,
    SplitRequest,
)
from app.services.achievement_review import (
    add_revision,
    links_of,
    owned_achievement,
    recompute_private,
    refresh_embedding,
    respond,
)
from app.services.evidence_items import candidate_id_or_none
from app.services.skill_canon import canonicalize

if TYPE_CHECKING:
    from sqlalchemy import ColumnElement

PROPOSAL_MIN_SIMILARITY = 0.90
PROPOSAL_LIMIT = 50
MIN_MERGE_SOURCES = 2
MERGEABLE = (AchievementStatus.draft, AchievementStatus.approved, AchievementStatus.rejected)


def _earliest(values: Sequence[date | None]) -> date | None:
    present = [value for value in values if value is not None]
    return min(present) if present else None


def _latest(values: Sequence[date | None]) -> date | None:
    present = [value for value in values if value is not None]
    return max(present) if present else None


def _union_metrics(sources: Sequence[Achievement]) -> list[dict[str, object]]:
    seen: set[str] = set()
    merged: list[dict[str, object]] = []
    for source in sources:
        for metric in source.metrics:
            key = " ".join(str(metric.get("text", "")).split()).casefold()
            if key and key not in seen:
                seen.add(key)
                merged.append(dict(metric))
    return merged


async def merge(session: AsyncSession, payload: MergeRequest) -> AchievementResponse:
    """Manual merge: a new `merged` draft; the sources are archived and point at it."""
    ids = list(dict.fromkeys(payload.ids))
    if len(ids) < MIN_MERGE_SOURCES:
        msg = "pick at least two different achievements to merge"
        raise InvalidAchievementInputError(msg)
    sources = [await owned_achievement(session, achievement_id) for achievement_id in ids]
    if any(source.status not in MERGEABLE for source in sources):
        msg = "archived achievements cannot be merged"
        raise InvalidAchievementInputError(msg)
    base = sources[0]
    merged = Achievement(
        candidate_id=base.candidate_id,
        status=AchievementStatus.draft,
        origin=AchievementOrigin.merged,
        title=payload.title or base.title,
        situation=payload.situation or base.situation,
        task=payload.task or base.task,
        action=payload.action or base.action,
        result=payload.result if payload.result is not None else base.result,
        metrics=_union_metrics(sources),
        skills=canonicalize([skill for source in sources for skill in source.skills]),
        impact_type=base.impact_type,
        difficulty=max(source.difficulty for source in sources),
        project_key=base.project_key,
        employer_ref=base.employer_ref,
        time_start=_earliest([source.time_start for source in sources]),
        time_end=_latest([source.time_end for source in sources]),
        prompt_version=base.prompt_version,
        edited_by_user=True,
        review_flags=sorted(
            {flag for source in sources for flag in source.review_flags} | {"merged"}
        ),
    )
    session.add(merged)
    await session.flush()
    seen: set[uuid.UUID] = set()
    for source in sources:
        for link in await links_of(session, source.id):
            if link.item_id in seen:
                continue
            seen.add(link.item_id)
            session.add(
                AchievementEvidence(
                    achievement_id=merged.id,
                    item_id=link.item_id,
                    role="primary" if len(seen) == 1 else "supporting",
                    quote=link.quote,
                )
            )
    await session.flush()
    await recompute_private(session, merged)
    await refresh_embedding(merged)
    add_revision(
        session,
        merged.id,
        AchievementRevisionSource.merge,
        {"merged_from": [str(source.id) for source in sources]},
    )
    for source in sources:
        add_revision(
            session,
            source.id,
            AchievementRevisionSource.merge,
            {"merged_into": str(merged.id), "status": [source.status.value, "archived"]},
        )
        source.status = AchievementStatus.archived
        source.evidence_stale_at = None
    return await respond(session, merged)


async def split(
    session: AsyncSession, achievement_id: uuid.UUID, payload: SplitRequest
) -> AchievementResponse:
    """Move the chosen evidence to a new draft; both rows are drafts afterwards."""
    original = await owned_achievement(session, achievement_id)
    if original.status is AchievementStatus.archived:
        msg = "archived achievements cannot be split"
        raise InvalidAchievementInputError(msg)
    links = await links_of(session, original.id)
    moving_ids = set(payload.evidence_item_ids)
    moving = [link for link in links if link.item_id in moving_ids]
    if len(moving) != len(moving_ids):
        msg = "every evidence item to move must be linked to this achievement"
        raise InvalidAchievementInputError(msg)
    if len(moving) >= len(links):
        msg = "the original must keep at least one evidence link"
        raise InvalidAchievementInputError(msg)
    flags = sorted({*original.review_flags, "split"})
    part = Achievement(
        candidate_id=original.candidate_id,
        status=AchievementStatus.draft,
        origin=original.origin,
        title=payload.title or f"{original.title} (part 2)",
        situation=original.situation,
        task=original.task,
        action=original.action,
        result=original.result,
        metrics=[dict(metric) for metric in original.metrics],
        skills=list(original.skills),
        impact_type=original.impact_type,
        difficulty=original.difficulty,
        project_key=original.project_key,
        employer_ref=original.employer_ref,
        time_start=original.time_start,
        time_end=original.time_end,
        embedding=original.embedding,
        prompt_version=original.prompt_version,
        source_chunk_hash=original.source_chunk_hash,
        edited_by_user=True,
        review_flags=flags,
    )
    session.add(part)
    await session.flush()
    await session.execute(
        update(AchievementEvidence)
        .where(AchievementEvidence.id.in_([link.id for link in moving]))
        .values(achievement_id=part.id)
    )
    moving[0].role = "primary"
    remaining = [link for link in links if link.item_id not in moving_ids]
    if not any(link.role == "primary" for link in remaining):
        remaining[0].role = "primary"
    await session.flush()
    await recompute_private(session, original)
    await recompute_private(session, part)
    previous = original.status
    original.status = AchievementStatus.draft
    original.evidence_stale_at = None
    original.review_flags = flags
    add_revision(
        session,
        original.id,
        AchievementRevisionSource.split_,
        {
            "split_to": str(part.id),
            "moved_evidence": [str(link.item_id) for link in moving],
            "status": [previous.value, "draft"],
        },
    )
    add_revision(
        session, part.id, AchievementRevisionSource.split_, {"split_from": str(original.id)}
    )
    return await respond(session, part)


async def propose_merges(session: AsyncSession) -> list[MergeProposalResponse]:
    """Likely duplicates (cosine >= 0.90, same project, overlapping dates); never auto-applied."""
    candidate_id = await candidate_id_or_none(session)
    if candidate_id is None:
        return []
    first, second = aliased(Achievement), aliased(Achievement)
    distance = cast(
        "ColumnElement[float]", first.embedding.op("<=>", return_type=Float)(second.embedding)
    )
    live = (AchievementStatus.draft, AchievementStatus.approved)
    rows = (
        await session.execute(
            select(first.id, first.title, second.id, second.title, first.project_key, distance)
            .where(
                first.candidate_id == candidate_id,
                second.candidate_id == candidate_id,
                first.id < second.id,
                first.status.in_(live),
                second.status.in_(live),
                first.project_key.is_not(None),
                first.project_key == second.project_key,
                first.embedding.is_not(None),
                second.embedding.is_not(None),
                first.time_start.is_not(None),
                second.time_start.is_not(None),
                func.coalesce(first.time_end, first.time_start) >= second.time_start,
                func.coalesce(second.time_end, second.time_start) >= first.time_start,
                distance <= 1 - PROPOSAL_MIN_SIMILARITY,
            )
            .order_by(distance)
            .limit(PROPOSAL_LIMIT)
        )
    ).all()
    return [
        MergeProposalResponse(
            first_id=row[0],
            first_title=row[1],
            second_id=row[2],
            second_title=row[3],
            project_key=row[4],
            similarity=round(1 - float(row[5]), 4),
        )
        for row in rows
    ]
