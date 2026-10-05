"""Parallel extraction starts admit one active run per candidate: the loser hits the partial
unique index (or the pre-flight select first) and surfaces as DuplicateExtractionError."""

import asyncio
import uuid

import pytest
from fakes import seed_evidence_chunk
from fastapi import BackgroundTasks
from sqlalchemy import select, text

from app.core.config import get_settings
from app.core.db import session_factory
from app.core.errors import DuplicateExtractionError
from app.models import AchievementExtractionRun, SyncStatus
from app.services import achievement_extraction
from app.services.achievement_extraction import estimate, start_extraction

pytestmark = pytest.mark.usefixtures("clean_tables")


@pytest.fixture(autouse=True)
def _key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "gemini_api_key", "test-key")
    monkeypatch.setattr(get_settings(), "extraction_min_chunk_chars", 0)


async def _start(estimate_id: str) -> uuid.UUID:
    async with session_factory() as session:
        response = await start_extraction(session, BackgroundTasks(), estimate_id)
        await session.commit()
        return response.run_id


async def _estimate_id() -> str:
    async with session_factory() as session:
        return (await estimate(session)).estimate_id


async def count_active() -> int:
    async with session_factory() as session:
        rows = await session.execute(
            select(AchievementExtractionRun).where(
                AchievementExtractionRun.status.in_((SyncStatus.pending, SyncStatus.running))
            )
        )
        return len(rows.scalars().all())


async def test_parallel_starts_admit_one_run() -> None:
    await seed_evidence_chunk(bodies=["Reduce import time"])
    estimate_id = await _estimate_id()

    results = await asyncio.gather(_start(estimate_id), _start(estimate_id), return_exceptions=True)

    successes = [r for r in results if not isinstance(r, BaseException)]
    duplicates = [r for r in results if isinstance(r, DuplicateExtractionError)]
    assert (len(successes), len(duplicates)) == (1, 1)
    assert await count_active() == 1


async def test_index_race_with_preflight_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Even with the advisory SELECT removed, the index alone holds the guard."""
    await seed_evidence_chunk(bodies=["Reduce import time"])
    estimate_id = await _estimate_id()

    async def _no_preflight(session: object, candidate_id: object) -> None:
        return None

    monkeypatch.setattr(achievement_extraction, "_raise_if_duplicate_run", _no_preflight)
    results = await asyncio.gather(_start(estimate_id), _start(estimate_id), return_exceptions=True)
    monkeypatch.undo()

    duplicates = [r for r in results if isinstance(r, DuplicateExtractionError)]
    assert len([r for r in results if not isinstance(r, BaseException)]) == 1
    assert len(duplicates) == 1
    assert duplicates[0].active_run_id is not None
    assert await count_active() == 1


async def test_the_sweeper_releases_a_stale_run() -> None:
    candidate_id, _, _ = await seed_evidence_chunk(bodies=["Reduce import time"])
    async with session_factory() as session:
        stale = AchievementExtractionRun(candidate_id=candidate_id, status=SyncStatus.running)
        session.add(stale)
        await session.commit()
        stale_id = stale.id
        await session.execute(
            text("UPDATE achievement_extraction_run SET updated_at = now() - interval '2 hours'")
        )
        await session.commit()
    estimate_id = await _estimate_id()

    run_id = await _start(estimate_id)

    async with session_factory() as session:
        swept = await session.get_one(AchievementExtractionRun, stale_id)
    assert swept.status is SyncStatus.failed
    assert swept.error is not None
    assert "abandoned" in swept.error
    assert run_id != stale_id
    assert await count_active() == 1


async def test_a_fresh_active_run_blocks_with_its_id() -> None:
    candidate_id, _, _ = await seed_evidence_chunk(bodies=["Reduce import time"])
    async with session_factory() as session:
        active = AchievementExtractionRun(candidate_id=candidate_id, status=SyncStatus.running)
        session.add(active)
        await session.commit()
        active_id = active.id
    estimate_id = await _estimate_id()

    with pytest.raises(DuplicateExtractionError) as caught:
        await _start(estimate_id)

    assert caught.value.active_run_id == active_id
