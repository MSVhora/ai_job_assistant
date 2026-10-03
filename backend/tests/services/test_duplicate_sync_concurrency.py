"""Parallel evidence sync starts admit one active run per source: the loser hits the partial
unique index (or the pre-flight select first) and surfaces as DuplicateSyncError."""

import asyncio
import uuid

import pytest
from fakes import ScriptedEvidenceSource, install_evidence_source
from fastapi import BackgroundTasks
from sqlalchemy import select, text

from app.core.db import session_factory
from app.core.errors import DuplicateSyncError
from app.models import (
    Candidate,
    EvidenceScope,
    EvidenceSourceAccount,
    EvidenceSyncRun,
    SyncStatus,
)
from app.services import evidence_sync
from app.services.evidence_sync import start_sync

pytestmark = pytest.mark.usefixtures("clean_tables")


async def seed_enabled_scope() -> None:
    async with session_factory() as session:
        candidate = Candidate()
        session.add(candidate)
        await session.flush()
        account = EvidenceSourceAccount(candidate_id=candidate.id, kind="github")
        session.add(account)
        await session.flush()
        session.add(EvidenceScope(source_id=account.id, ref="ada/engine", enabled=True))
        await session.commit()


async def _start() -> uuid.UUID:
    async with session_factory() as session:
        response = await start_sync(session, BackgroundTasks(), "incremental")
        await session.commit()
        return response.sync_id


async def count_active() -> int:
    async with session_factory() as session:
        rows = await session.execute(
            select(EvidenceSyncRun).where(
                EvidenceSyncRun.status.in_((SyncStatus.pending, SyncStatus.running))
            )
        )
        return len(rows.scalars().all())


async def test_parallel_starts_admit_one_run(monkeypatch: pytest.MonkeyPatch) -> None:
    install_evidence_source(monkeypatch, ScriptedEvidenceSource())
    await seed_enabled_scope()

    results = await asyncio.gather(_start(), _start(), return_exceptions=True)

    successes = [r for r in results if not isinstance(r, BaseException)]
    duplicates = [r for r in results if isinstance(r, DuplicateSyncError)]
    assert len(successes) == 1
    assert len(duplicates) == 1
    assert await count_active() == 1


async def test_index_race_with_preflight_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Even with the advisory SELECT removed, the index alone holds the guard."""
    install_evidence_source(monkeypatch, ScriptedEvidenceSource())
    await seed_enabled_scope()

    async def _no_preflight(session: object, source_id: object) -> None:
        return None

    monkeypatch.setattr(evidence_sync, "_raise_if_duplicate_run", _no_preflight)
    results = await asyncio.gather(_start(), _start(), return_exceptions=True)
    monkeypatch.undo()

    successes = [r for r in results if not isinstance(r, BaseException)]
    duplicates = [r for r in results if isinstance(r, DuplicateSyncError)]
    assert len(successes) == 1
    assert len(duplicates) == 1
    assert duplicates[0].active_sync_id is not None
    assert await count_active() == 1


async def test_index_names_the_guard() -> None:
    async with session_factory() as session:
        count = (
            await session.execute(
                text(
                    "SELECT count(*) FROM pg_indexes "
                    "WHERE indexname = 'uq_evidence_sync_active_run'"
                )
            )
        ).scalar_one()
    assert count == 1
