"""Replace approved achievements from an older extraction prompt once their chunk has been
re-extracted: an explicit, previewed step, because approved rows are never changed implicitly."""

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Achievement,
    AchievementRevision,
    AchievementRevisionSource,
    AchievementStatus,
    EvidenceChunk,
)
from app.schemas.achievement import RetireOlderResult, RetirePreview
from app.services.achievement_extraction import ACHIEVEMENT_PROMPT_VERSION
from app.services.evidence_items import candidate_id_or_none
from app.services.evidence_pipeline.dedupe import digest

REASON = "replaced_by_new_prompt"


@dataclass
class _Split:
    replace: list[Achievement]
    kept_edited: int = 0
    kept_not_reextracted: int = 0


async def _reextracted_hashes(session: AsyncSession, candidate_id: uuid.UUID) -> set[str]:
    """Content hashes of chunks whose extraction ran under the current prompt version."""
    rows = (
        await session.execute(
            select(EvidenceChunk.content_hash, EvidenceChunk.extracted_hash).where(
                EvidenceChunk.candidate_id == candidate_id
            )
        )
    ).all()
    return {
        content_hash
        for content_hash, extracted in rows
        if extracted == digest(content_hash, ACHIEVEMENT_PROMPT_VERSION)
    }


async def _split(session: AsyncSession, candidate_id: uuid.UUID) -> _Split:
    older = (
        (
            await session.execute(
                select(Achievement).where(
                    Achievement.candidate_id == candidate_id,
                    Achievement.status == AchievementStatus.approved,
                    Achievement.origin == "ai_extracted",
                    Achievement.prompt_version.is_not(None),
                    Achievement.prompt_version != ACHIEVEMENT_PROMPT_VERSION,
                )
            )
        )
        .scalars()
        .all()
    )
    covered = await _reextracted_hashes(session, candidate_id)
    split = _Split(replace=[])
    for row in older:
        if row.edited_by_user:
            split.kept_edited += 1
        elif row.source_chunk_hash not in covered:
            split.kept_not_reextracted += 1
        else:
            split.replace.append(row)
    return split


async def preview(session: AsyncSession) -> RetirePreview:
    candidate_id = await candidate_id_or_none(session)
    split = await _split(session, candidate_id) if candidate_id else _Split(replace=[])
    return RetirePreview(
        prompt_version=ACHIEVEMENT_PROMPT_VERSION,
        would_archive=len(split.replace),
        kept_edited=split.kept_edited,
        kept_not_reextracted=split.kept_not_reextracted,
    )


async def retire_older(session: AsyncSession) -> RetireOlderResult:
    candidate_id = await candidate_id_or_none(session)
    if candidate_id is None:
        return RetireOlderResult(archived=0)
    split = await _split(session, candidate_id)
    for row in split.replace:
        diff: dict[str, object] = {
            "status": ["approved", "archived"],
            "reason": REASON,
            "replaced_prompt_version": row.prompt_version,
            "bulk": True,
        }
        row.status = AchievementStatus.archived
        row.evidence_stale_at = None
        session.add(
            AchievementRevision(
                achievement_id=row.id, source=AchievementRevisionSource.status_change, diff=diff
            )
        )
    return RetireOlderResult(archived=len(split.replace))
