"""DoD for issue #36: parallel start_search calls cannot both create a run
for the same (profile, source) — one inserts, the loser hits the partial
unique index at flush (or the advisory pre-flight first) and surfaces as
DuplicateRunError."""

import asyncio
import uuid
from datetime import UTC, datetime

import pytest
from fakes import FakeJobSource, seed_profile_light
from fastapi import BackgroundTasks
from sqlalchemy import select

from app.adapters.job_sources import registry
from app.core.db import session_factory
from app.core.errors import DuplicateRunError
from app.models import JobSearch, SourceState
from app.schemas.job_search import JobSearchRequest
from app.services import ingestion
from app.services.ingestion import start_search

pytestmark = pytest.mark.usefixtures("clean_tables")


def request_for(profile_id: uuid.UUID, source: str = "adzuna") -> JobSearchRequest:
    return JobSearchRequest(
        query="python developer", country="de", source=source, profile_id=profile_id
    )


def only_sources(monkeypatch: pytest.MonkeyPatch, *sources: FakeJobSource) -> None:
    monkeypatch.setattr(registry, "all_sources", lambda: tuple(sources))


async def acknowledge(name: str) -> None:
    async with session_factory() as session:
        session.add(SourceState(source_name=name, acknowledged_at=datetime.now(UTC)))
        await session.commit()


async def _start(payload: JobSearchRequest) -> uuid.UUID:
    async with session_factory() as session:
        response = await start_search(session, BackgroundTasks(), payload)
        await session.commit()
        return response.search_id


async def count_active(profile_id: uuid.UUID) -> int:
    async with session_factory() as session:
        result = await session.execute(
            select(JobSearch).where(
                JobSearch.profile_id == profile_id,
                JobSearch.status.in_(("pending", "running")),
            )
        )
        return len(result.scalars().all())


async def test_parallel_starts_admit_one_run_each_pair(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    only_sources(monkeypatch, FakeJobSource("adzuna"))
    profile_id = await seed_profile_light()
    payload = request_for(profile_id)

    results = await asyncio.gather(_start(payload), _start(payload), return_exceptions=True)
    successes = [r for r in results if not isinstance(r, BaseException)]
    duplicates = [r for r in results if isinstance(r, DuplicateRunError)]
    assert len(successes) == 1
    assert len(duplicates) == 1
    assert await count_active(profile_id) == 1


async def test_index_race_with_preflight_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Even with the advisory SELECT removed, the index alone holds the guard."""
    only_sources(monkeypatch, FakeJobSource("adzuna"))
    profile_id = await seed_profile_light()
    payload = request_for(profile_id)

    async def _no_preflight(session: object, profile_id_: object, source_name_: object) -> None:
        return None

    monkeypatch.setattr(ingestion, "_raise_if_duplicate_run", _no_preflight)
    results = await asyncio.gather(_start(payload), _start(payload), return_exceptions=True)
    monkeypatch.undo()

    successes = [r for r in results if not isinstance(r, BaseException)]
    duplicates = [r for r in results if isinstance(r, DuplicateRunError)]
    assert len(successes) == 1
    assert len(duplicates) == 1
    assert duplicates[0].active_search_id is not None
    assert await count_active(profile_id) == 1


async def test_parallel_starts_allow_concurrent_sources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    only_sources(
        monkeypatch,
        FakeJobSource("adzuna", postings=[]),
        FakeJobSource("apify_linkedin", postings=[]),
    )
    await acknowledge("adzuna")
    await acknowledge("apify_linkedin")
    profile_id = await seed_profile_light()

    results = await asyncio.gather(
        _start(request_for(profile_id, "adzuna")),
        _start(request_for(profile_id, "apify_linkedin")),
        return_exceptions=True,
    )
    assert all(not isinstance(r, BaseException) for r in results)
    assert len(set(results)) == 2
    assert await count_active(profile_id) == 2
