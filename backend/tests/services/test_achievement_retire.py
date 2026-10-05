import uuid

import pytest
from fakes import seed_achievement, seed_evidence_chunk
from sqlalchemy import select

from app.core.db import session_factory
from app.models import Achievement, AchievementRevision, AchievementStatus, EvidenceChunk
from app.services import achievement_retire
from app.services.achievement_extraction import ACHIEVEMENT_PROMPT_VERSION
from app.services.evidence_pipeline.dedupe import digest

pytestmark = pytest.mark.usefixtures("clean_tables")

OLD = "achievement_v1"


async def chunk_hash(chunk_id: uuid.UUID, *, reextracted: bool) -> str:
    async with session_factory() as session:
        chunk = await session.get_one(EvidenceChunk, chunk_id)
        if reextracted:
            chunk.extracted_hash = digest(chunk.content_hash, ACHIEVEMENT_PROMPT_VERSION)
        await session.commit()
        return chunk.content_hash


async def status_of(achievement_id: uuid.UUID) -> AchievementStatus:
    async with session_factory() as session:
        return (await session.get_one(Achievement, achievement_id)).status


async def seed_old(
    candidate_id: uuid.UUID, item: uuid.UUID, source_hash: str | None, **kwargs: object
) -> uuid.UUID:
    return await seed_achievement(
        candidate_id,
        item_ids=[item],
        status="approved",
        prompt_version=OLD,
        source_chunk_hash=source_hash,
        **kwargs,  # type: ignore[arg-type]
    )


async def test_older_approved_rows_are_replaced_only_where_their_chunk_was_reextracted() -> None:
    candidate_id, done_chunk, done_items = await seed_evidence_chunk(
        bodies=["done"], project_key="ada/done"
    )
    _, todo_chunk, todo_items = await seed_evidence_chunk(
        bodies=["todo"], project_key="ada/todo", candidate_id=candidate_id
    )
    done_hash = await chunk_hash(done_chunk, reextracted=True)
    todo_hash = await chunk_hash(todo_chunk, reextracted=False)
    replaced = await seed_old(candidate_id, done_items[0], done_hash)
    edited = await seed_old(candidate_id, done_items[0], done_hash, edited=True)
    waiting = await seed_old(candidate_id, todo_items[0], todo_hash)
    current = await seed_achievement(
        candidate_id,
        item_ids=done_items,
        status="approved",
        prompt_version=ACHIEVEMENT_PROMPT_VERSION,
        source_chunk_hash=done_hash,
    )

    async with session_factory() as session:
        shown = await achievement_retire.preview(session)
    async with session_factory() as session:
        result = await achievement_retire.retire_older(session)
        await session.commit()

    assert (shown.would_archive, shown.kept_edited, shown.kept_not_reextracted) == (1, 1, 1)
    assert shown.prompt_version == ACHIEVEMENT_PROMPT_VERSION
    assert result.archived == 1
    assert await status_of(replaced) is AchievementStatus.archived
    assert await status_of(edited) is AchievementStatus.approved
    assert await status_of(waiting) is AchievementStatus.approved
    assert await status_of(current) is AchievementStatus.approved


async def test_retiring_records_a_revision_with_the_reason() -> None:
    candidate_id, chunk, items = await seed_evidence_chunk(bodies=["done"])
    source_hash = await chunk_hash(chunk, reextracted=True)
    row = await seed_old(candidate_id, items[0], source_hash)

    async with session_factory() as session:
        await achievement_retire.retire_older(session)
        await session.commit()

    async with session_factory() as session:
        (revision,) = (
            (
                await session.execute(
                    select(AchievementRevision).where(AchievementRevision.achievement_id == row)
                )
            )
            .scalars()
            .all()
        )
    assert revision.diff == {
        "status": ["approved", "archived"],
        "reason": "replaced_by_new_prompt",
        "replaced_prompt_version": OLD,
        "bulk": True,
    }


async def test_with_nothing_to_replace_the_preview_and_result_are_zero() -> None:
    async with session_factory() as session:
        shown = await achievement_retire.preview(session)
        result = await achievement_retire.retire_older(session)

    assert (shown.would_archive, shown.kept_edited, shown.kept_not_reextracted) == (0, 0, 0)
    assert result.archived == 0
