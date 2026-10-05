import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fakes import ScriptedEvidenceSource, install_evidence_source
from fastapi import BackgroundTasks
from sqlalchemy import select, text

from app.adapters.evidence_sources.base import EvidenceSourceError, EvidenceSourcePausedError
from app.core.config import get_settings
from app.core.db import session_factory
from app.core.errors import (
    DuplicateSyncError,
    EvidenceSourceNotConfiguredError,
    NoEnabledScopesError,
)
from app.models import (
    Candidate,
    EvidenceItem,
    EvidenceItemStatus,
    EvidenceKind,
    EvidenceScope,
    EvidenceSourceAccount,
    EvidenceSyncRun,
    SyncStatus,
)
from app.schemas.evidence import EvidenceItemData, RateLimitInfo, SyncPage
from app.services.evidence_sync import run_sync, start_sync

pytestmark = pytest.mark.usefixtures("clean_tables")


def item(kind: str, external_id: str, **meta: object) -> EvidenceItemData:
    return EvidenceItemData(
        kind=EvidenceKind(kind),
        external_id=external_id,
        project_key="ada/engine",
        title=f"{kind} {external_id}",
        body=f"Implement feature {external_id} with a careful design",
        meta=dict(meta),
    )


def page(
    items: list[EvidenceItemData], cursor: str, *, requests: int = 2, remaining: int = 4000
) -> SyncPage:
    return SyncPage(
        items=items,
        next_cursor={"stage": cursor},
        requests_used=requests,
        rate_limits=[RateLimitInfo(api="rest", remaining=remaining, limit=5000)],
    )


async def seed_scopes(
    *refs: str, private: bool = False, cursor: dict[str, object] | None = None
) -> None:
    async with session_factory() as session:
        candidate = Candidate()
        session.add(candidate)
        await session.flush()
        account = EvidenceSourceAccount(candidate_id=candidate.id, kind="github")
        session.add(account)
        await session.flush()
        for ref in refs:
            session.add(
                EvidenceScope(
                    source_id=account.id,
                    ref=ref,
                    enabled=True,
                    is_private=private,
                    cursor=cursor or {},
                )
            )
        await session.commit()


async def sync(mode: str = "incremental") -> uuid.UUID:
    async with session_factory() as session:
        response = await start_sync(session, BackgroundTasks(), mode)  # type: ignore[arg-type]
        await session.commit()
    await run_sync(response.sync_id, mode)  # type: ignore[arg-type]
    return response.sync_id


async def load_run(run_id: uuid.UUID) -> EvidenceSyncRun:
    async with session_factory() as session:
        return await session.get_one(EvidenceSyncRun, run_id)


async def load_scope(ref: str) -> EvidenceScope:
    async with session_factory() as session:
        return (
            await session.execute(select(EvidenceScope).where(EvidenceScope.ref == ref))
        ).scalar_one()


async def load_items() -> dict[str, EvidenceItem]:
    async with session_factory() as session:
        rows = (await session.execute(select(EvidenceItem))).scalars().all()
    return {row.external_id: row for row in rows}


async def test_sync_stores_items_advances_cursors_and_records_progress(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await seed_scopes("ada/engine", "ada/notes")
    source = ScriptedEvidenceSource(
        {
            "ada/engine": [
                page([item("commit", "c1")], "commits"),
                page([item("pull_request", "pr1")], "done", requests=3),
            ],
            "ada/notes": [page([item("issue", "i1")], "done", requests=1)],
        }
    )
    install_evidence_source(monkeypatch, source)

    run_id = await sync()

    run = await load_run(run_id)
    assert run.status is SyncStatus.succeeded
    assert set(await load_items()) == {"c1", "pr1", "i1"}
    engine = await load_scope("ada/engine")
    assert engine.cursor == {"stage": "done"}
    assert engine.sync_state is SyncStatus.succeeded
    assert engine.last_synced_at is not None
    assert run.usage == {"requests": 6}
    assert run.progress["items"] == 3
    assert run.rate_limit["rest"]["remaining"] == 4000
    async with session_factory() as session:
        account = (await session.execute(select(EvidenceSourceAccount))).scalar_one()
    assert account.last_synced_at is not None


async def test_noise_filtered_items_are_stored_with_a_reason_and_scope_privacy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await seed_scopes("ada/secret", private=True)
    install_evidence_source(
        monkeypatch,
        ScriptedEvidenceSource(
            {
                "ada/secret": [
                    page(
                        [
                            item("commit", "keep", additions=40, deletions=3, parents=1),
                            item("commit", "merge", parents=2),
                            item("commit", "bot", author_login="dependabot[bot]"),
                        ],
                        "done",
                    )
                ]
            }
        ),
    )

    await sync()

    items = await load_items()
    assert items["keep"].status is EvidenceItemStatus.kept
    assert (items["merge"].status, items["merge"].filter_reason) == (
        EvidenceItemStatus.filtered,
        "merge_commit",
    )
    assert items["bot"].filter_reason == "bot_author"
    assert all(row.is_private for row in items.values())


async def test_resyncing_the_same_items_does_not_duplicate_and_updates_changed_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await seed_scopes("ada/engine")
    first = item("commit", "c1")
    install_evidence_source(
        monkeypatch, ScriptedEvidenceSource({"ada/engine": [page([first], "done")]})
    )
    await sync()
    before = (await load_items())["c1"]

    changed = first.model_copy(update={"body": "Rewritten message with more context"})
    install_evidence_source(
        monkeypatch, ScriptedEvidenceSource({"ada/engine": [page([changed], "done")]})
    )
    await sync("full")

    after = (await load_items())["c1"]
    assert len(await load_items()) == 1
    assert after.id == before.id
    assert after.body == "Rewritten message with more context"


async def test_unchanged_items_are_left_untouched_so_a_user_restore_sticks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await seed_scopes("ada/engine")
    merge = item("commit", "m1", parents=2)
    install_evidence_source(
        monkeypatch, ScriptedEvidenceSource({"ada/engine": [page([merge], "done")]})
    )
    await sync()
    async with session_factory() as session:
        await session.execute(
            text("UPDATE evidence_item SET status = 'kept', filter_reason = NULL")
        )
        await session.commit()

    install_evidence_source(
        monkeypatch, ScriptedEvidenceSource({"ada/engine": [page([merge], "done")]})
    )
    await sync()

    assert (await load_items())["m1"].status is EvidenceItemStatus.kept


async def test_budget_pause_marks_run_and_scope_paused_and_keeps_committed_pages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(get_settings(), "evidence_sync_concurrency", 1)
    await seed_scopes("ada/a", "ada/b")
    resume = datetime.now(UTC) + timedelta(hours=1)
    source = ScriptedEvidenceSource(
        {
            "ada/a": [
                page([item("commit", "c1")], "commits"),
                EvidenceSourcePausedError("the request budget for this run is used up", resume),
            ],
            "ada/b": [page([item("commit", "never")], "done")],
        }
    )
    install_evidence_source(monkeypatch, source)

    run_id = await sync()

    run = await load_run(run_id)
    assert run.status is SyncStatus.paused
    assert run.resume_at is not None
    assert abs((run.resume_at - resume).total_seconds()) < 1
    assert run.error == "the request budget for this run is used up"
    scope = await load_scope("ada/a")
    assert scope.sync_state is SyncStatus.paused
    assert scope.cursor == {"stage": "commits"}
    assert set(await load_items()) == {"c1"}
    assert [state.ref for state in source.seen] == ["ada/a"]


class SlowSource(ScriptedEvidenceSource):
    in_flight = 0
    peak = 0

    async def sync_scope(self, scope: Any) -> Any:
        type(self).in_flight += 1
        type(self).peak = max(type(self).peak, type(self).in_flight)
        try:
            async for step in super().sync_scope(scope):
                await asyncio.sleep(0.02)
                yield step
        finally:
            type(self).in_flight -= 1


async def test_scopes_sync_concurrently_and_each_keeps_its_own_progress(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(get_settings(), "evidence_sync_concurrency", 3)
    refs = [f"ada/r{index}" for index in range(6)]
    await seed_scopes(*refs)
    SlowSource.in_flight = SlowSource.peak = 0
    source = SlowSource(
        {
            ref: [
                page([item("commit", f"{ref}-1")], "commits"),
                page([item("commit", f"{ref}-2")], "done"),
            ]
            for ref in refs
        }
    )
    install_evidence_source(monkeypatch, source)

    run_id = await sync()

    run = await load_run(run_id)
    assert run.status is SyncStatus.succeeded
    assert SlowSource.peak == 3
    assert set(run.progress["scopes"]) == set(refs)
    assert {entry["status"] for entry in run.progress["scopes"].values()} == {"ok"}
    assert run.progress["items"] == 12
    assert len(await load_items()) == 12


async def test_a_paused_run_does_not_block_the_next_start_which_resumes_from_the_cursor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await seed_scopes("ada/a")
    install_evidence_source(
        monkeypatch,
        ScriptedEvidenceSource(
            {
                "ada/a": [
                    page([item("commit", "c1")], "commits"),
                    EvidenceSourcePausedError("rate limit floor", None),
                ]
            }
        ),
    )
    await sync()

    resumed = ScriptedEvidenceSource({"ada/a": [page([item("commit", "c2")], "done")]})
    install_evidence_source(monkeypatch, resumed)
    run_id = await sync()

    assert (await load_run(run_id)).status is SyncStatus.succeeded
    assert resumed.seen[0].cursor == {"stage": "commits"}
    assert set(await load_items()) == {"c1", "c2"}


async def test_full_mode_resets_cursors_before_reading(monkeypatch: pytest.MonkeyPatch) -> None:
    await seed_scopes("ada/a", cursor={"stage": "done", "watermark": "2026-01-01T00:00:00+00:00"})
    source = ScriptedEvidenceSource({"ada/a": [page([], "done")]})
    install_evidence_source(monkeypatch, source)

    await sync("full")

    assert source.seen[0].cursor == {}


async def test_incremental_mode_passes_the_stored_cursor(monkeypatch: pytest.MonkeyPatch) -> None:
    stored = {"stage": "done", "watermark": "2026-01-01T00:00:00+00:00"}
    await seed_scopes("ada/a", cursor=stored)
    source = ScriptedEvidenceSource({"ada/a": [page([], "done")]})
    install_evidence_source(monkeypatch, source)

    await sync("incremental")

    assert source.seen[0].cursor == stored


async def test_a_failing_scope_is_a_warning_and_does_not_fail_the_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await seed_scopes("ada/a", "ada/b")
    install_evidence_source(
        monkeypatch,
        ScriptedEvidenceSource(
            {
                "ada/a": [EvidenceSourceError("GitHub returned 404 (repository missing)")],
                "ada/b": [page([item("commit", "c1")], "done")],
            }
        ),
    )

    run_id = await sync()

    run = await load_run(run_id)
    assert run.status is SyncStatus.succeeded
    assert run.progress["warnings"] == ["ada/a: GitHub returned 404 (repository missing)"]
    assert (await load_scope("ada/a")).sync_state is SyncStatus.failed
    assert (await load_scope("ada/b")).sync_state is SyncStatus.succeeded
    assert set(await load_items()) == {"c1"}


async def test_the_run_fails_when_every_scope_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    await seed_scopes("ada/a")
    install_evidence_source(
        monkeypatch, ScriptedEvidenceSource({"ada/a": [EvidenceSourceError("no access")]})
    )

    run_id = await sync()

    run = await load_run(run_id)
    assert run.status is SyncStatus.failed
    assert run.error is not None


async def test_squash_commits_attach_to_their_pull_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await seed_scopes("ada/engine")
    install_evidence_source(
        monkeypatch,
        ScriptedEvidenceSource(
            {
                "ada/engine": [
                    page(
                        [
                            item("commit", "sha-squash", additions=80, deletions=5, parents=1),
                            item("commit", "sha-direct", additions=60, deletions=4, parents=1),
                            item(
                                "pull_request",
                                "ada/engine#7",
                                number=7,
                                merge_commit_oid="sha-squash",
                                additions=80,
                                deletions=5,
                            ),
                        ],
                        "done",
                    )
                ]
            }
        ),
    )

    await sync()

    items = await load_items()
    assert items["sha-squash"].status is EvidenceItemStatus.filtered
    assert items["sha-squash"].filter_reason == "squash_of_pull_request"
    assert items["sha-squash"].meta["pr_number"] == 7
    assert items["sha-direct"].status is EvidenceItemStatus.kept


async def test_sweeper_fails_a_stale_run_and_releases_the_lock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await seed_scopes("ada/a")
    install_evidence_source(monkeypatch, ScriptedEvidenceSource({"ada/a": [page([], "done")]}))
    async with session_factory() as session:
        account = (await session.execute(select(EvidenceSourceAccount))).scalar_one()
        stale = EvidenceSyncRun(source_id=account.id, status=SyncStatus.running)
        session.add(stale)
        await session.commit()
        stale_id = stale.id
        await session.execute(
            text("UPDATE evidence_sync_run SET updated_at = now() - interval '2 hours'")
        )
        await session.commit()

    run_id = await sync()

    swept = await load_run(stale_id)
    assert swept.status is SyncStatus.failed
    assert swept.error is not None
    assert "abandoned" in swept.error
    assert (await load_run(run_id)).status is SyncStatus.succeeded


async def test_start_rejects_a_fresh_active_run_with_its_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await seed_scopes("ada/a")
    install_evidence_source(monkeypatch, ScriptedEvidenceSource())
    async with session_factory() as session:
        account = (await session.execute(select(EvidenceSourceAccount))).scalar_one()
        active = EvidenceSyncRun(source_id=account.id, status=SyncStatus.running)
        session.add(active)
        await session.commit()
        active_id = active.id

    async with session_factory() as session:
        with pytest.raises(DuplicateSyncError) as caught:
            await start_sync(session, BackgroundTasks(), "incremental")

    assert caught.value.active_sync_id == active_id


async def test_start_requires_a_configured_source_and_an_enabled_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_evidence_source(monkeypatch, ScriptedEvidenceSource(configured=False))
    async with session_factory() as session:
        with pytest.raises(EvidenceSourceNotConfiguredError):
            await start_sync(session, BackgroundTasks(), "incremental")

    install_evidence_source(monkeypatch, ScriptedEvidenceSource())
    async with session_factory() as session:
        with pytest.raises(NoEnabledScopesError):
            await start_sync(session, BackgroundTasks(), "incremental")


async def test_a_killed_run_keeps_its_committed_pages_and_a_later_sync_resumes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await seed_scopes("ada/a")
    block = asyncio.Event()
    source = ScriptedEvidenceSource(
        {
            "ada/a": [
                page([item("commit", "c1")], "p1"),
                page([item("commit", "c2")], "p2"),
                block,
                page([item("commit", "c3")], "done"),
            ]
        }
    )
    install_evidence_source(monkeypatch, source)
    async with session_factory() as session:
        response = await start_sync(session, BackgroundTasks(), "incremental")
        await session.commit()
    task = asyncio.create_task(run_sync(response.sync_id, "incremental"))
    for _ in range(200):
        await asyncio.sleep(0.01)
        if len(await load_items()) == 2:
            break
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert set(await load_items()) == {"c1", "c2"}
    assert (await load_scope("ada/a")).cursor == {"stage": "p2"}
    killed = await load_run(response.sync_id)
    assert killed.status is SyncStatus.running

    async with session_factory() as session:
        await session.execute(
            text("UPDATE evidence_sync_run SET updated_at = now() - interval '2 hours'")
        )
        await session.commit()
    resumed = ScriptedEvidenceSource({"ada/a": [page([item("commit", "c3")], "done")]})
    install_evidence_source(monkeypatch, resumed)
    await sync()

    assert resumed.seen[0].cursor == {"stage": "p2"}
    assert set(await load_items()) == {"c1", "c2", "c3"}


async def test_a_run_chunks_what_it_stored_and_records_the_counts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(get_settings(), "gemini_api_key", None)
    await seed_scopes("ada/engine")
    install_evidence_source(
        monkeypatch,
        ScriptedEvidenceSource(
            {
                "ada/engine": [
                    page([item("issue", "ada/engine#1"), item("issue", "ada/engine#2")], "done")
                ]
            }
        ),
    )

    run_id = await sync()

    chunks = (await load_run(run_id)).progress["chunks"]
    assert chunks["created"] == 2
    assert chunks["embed_failed"] == 0
    assert chunks["pending_embedding"] == 2


async def test_a_run_where_every_scope_fails_builds_no_chunks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await seed_scopes("ada/a")
    install_evidence_source(
        monkeypatch, ScriptedEvidenceSource({"ada/a": [EvidenceSourceError("no access")]})
    )

    run_id = await sync()

    assert "chunks" not in (await load_run(run_id)).progress


async def test_a_sync_that_changes_linked_evidence_flags_approved_achievements_for_re_review(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fakes import seed_achievement

    from app.models import Achievement

    await seed_scopes("ada/engine")
    original = item("issue", "ada/engine#1")
    install_evidence_source(
        monkeypatch, ScriptedEvidenceSource({"ada/engine": [page([original], "done")]})
    )
    await sync()
    stored = (await load_items())["ada/engine#1"]
    approved = await seed_achievement(
        stored.candidate_id, item_ids=[stored.id], status="approved", project_key="ada/engine"
    )

    install_evidence_source(
        monkeypatch, ScriptedEvidenceSource({"ada/engine": [page([original], "done")]})
    )
    unchanged_run = await sync()
    changed = original.model_copy(update={"body": "Reworded after the maintainers asked"})
    install_evidence_source(
        monkeypatch, ScriptedEvidenceSource({"ada/engine": [page([changed], "done")]})
    )
    changed_run = await sync()

    assert (await load_run(unchanged_run)).progress["stale_flagged"] == 0
    assert (await load_run(changed_run)).progress["stale_flagged"] == 1
    async with session_factory() as session:
        assert (await session.get_one(Achievement, approved)).evidence_stale_at is not None
