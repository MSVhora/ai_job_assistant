import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fakes import embedding_response, fake_vector, install_aembedding
from sqlalchemy import func, select, text

from app.adapters.llm import LLMError
from app.core.config import get_settings
from app.core.db import session_factory
from app.models import (
    Candidate,
    EvidenceChunk,
    EvidenceChunkItem,
    EvidenceItem,
    EvidenceItemStatus,
    EvidenceKind,
)
from app.services.evidence_chunks import chunk_summary, rebuild_chunks, rebuild_chunks_background

pytestmark = pytest.mark.usefixtures("clean_tables")

T0 = datetime(2026, 3, 1, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _llm_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "gemini_api_key", "test-key")


def embedder(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, object]]:
    return install_aembedding(
        monkeypatch,
        lambda **kw: embedding_response([fake_vector(t) for t in kw["input"]], prompt_tokens=7),
    )


async def seed_items(*specs: tuple[str, str, str], private: bool = False) -> uuid.UUID:
    async with session_factory() as session:
        candidate = Candidate()
        session.add(candidate)
        await session.flush()
        for kind, external_id, body in specs:
            session.add(
                EvidenceItem(
                    candidate_id=candidate.id,
                    kind=EvidenceKind(kind),
                    external_id=external_id,
                    project_key="ada/engine",
                    title=body[:40],
                    body=body,
                    occurred_at=T0,
                    is_private=private,
                    meta={"number": 1} if kind == "pull_request" else {},
                    content_hash=external_id,
                )
            )
        await session.commit()
        return candidate.id


async def rebuild(candidate_id: uuid.UUID):
    async with session_factory() as session:
        result = await rebuild_chunks(session, candidate_id)
        await session.commit()
        return result


async def chunks() -> list[EvidenceChunk]:
    async with session_factory() as session:
        return list((await session.execute(select(EvidenceChunk))).scalars().all())


async def test_first_run_embeds_every_chunk_and_a_second_run_embeds_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = embedder(monkeypatch)
    candidate_id = await seed_items(
        ("issue", "ada/engine#1", "Loader drops the last card"),
        ("issue", "ada/engine#2", "Reader crashes on empty deck"),
        ("note", "n1", "Notes about the design of the loader"),
    )

    first = await rebuild(candidate_id)
    second = await rebuild(candidate_id)

    assert (first.created, first.embedded, first.embed_failed) == (3, 3, 0)
    assert first.prompt_tokens == 7
    assert (second.created, second.deleted, second.unchanged, second.embedded) == (0, 0, 3, 0)
    assert sum(len(call["input"]) for call in calls) == 3  # type: ignore[arg-type]
    stored = await chunks()
    assert all(chunk.embedding is not None for chunk in stored)
    assert all(len(chunk.embedding) == 768 for chunk in stored)  # type: ignore[arg-type]


async def test_editing_one_item_changes_one_chunk_and_embeds_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = embedder(monkeypatch)
    candidate_id = await seed_items(
        ("issue", "ada/engine#1", "Loader drops the last card"),
        ("issue", "ada/engine#2", "Reader crashes on empty deck"),
    )
    await rebuild(candidate_id)
    before = {c.content_hash for c in await chunks()}
    calls.clear()
    async with session_factory() as session:
        await session.execute(
            text(
                "UPDATE evidence_item SET body = 'Loader drops the final card' "
                "WHERE external_id = 'ada/engine#1'"
            )
        )
        await session.commit()

    result = await rebuild(candidate_id)

    after = {c.content_hash for c in await chunks()}
    assert (result.created, result.deleted, result.unchanged, result.embedded) == (1, 1, 1, 1)
    assert len(before & after) == 1
    assert sum(len(call["input"]) for call in calls) == 1  # type: ignore[arg-type]


async def test_removed_or_excluded_items_delete_their_chunks_and_links(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    embedder(monkeypatch)
    candidate_id = await seed_items(
        ("issue", "ada/engine#1", "Loader drops the last card"),
        ("issue", "ada/engine#2", "Reader crashes on empty deck"),
    )
    await rebuild(candidate_id)
    async with session_factory() as session:
        await session.execute(
            text("UPDATE evidence_item SET status = 'excluded' WHERE external_id = 'ada/engine#2'")
        )
        await session.commit()

    result = await rebuild(candidate_id)

    assert result.deleted == 1
    async with session_factory() as session:
        links = (
            await session.execute(select(func.count()).select_from(EvidenceChunkItem))
        ).scalar_one()
        items = (await session.execute(select(func.count()).select_from(EvidenceItem))).scalar_one()
    assert (len(await chunks()), links, items) == (1, 1, 2)


async def test_chunk_links_follow_the_member_items(monkeypatch: pytest.MonkeyPatch) -> None:
    embedder(monkeypatch)
    candidate_id = await seed_items(("issue", "ada/engine#1", "Loader drops the last card"))

    await rebuild(candidate_id)

    async with session_factory() as session:
        item_id = (await session.execute(select(EvidenceItem.id))).scalar_one()
        linked = (await session.execute(select(EvidenceChunkItem.item_id))).scalar_one()
    assert linked == item_id


async def test_embedding_failure_keeps_the_chunk_and_the_next_run_retries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_aembedding(monkeypatch, lambda **_: LLMError("provider down"))
    candidate_id = await seed_items(("issue", "ada/engine#1", "Loader drops the last card"))

    failed = await rebuild(candidate_id)

    assert (failed.created, failed.embedded, failed.embed_failed, failed.pending_embedding) == (
        1,
        0,
        1,
        1,
    )
    assert [c.embedding for c in await chunks()] == [None]

    embedder(monkeypatch)
    retried = await rebuild(candidate_id)

    assert (retried.created, retried.embedded, retried.pending_embedding) == (0, 1, 0)
    assert (await chunks())[0].embedding is not None


async def test_chunks_are_still_built_when_no_llm_key_is_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(get_settings(), "gemini_api_key", None)
    candidate_id = await seed_items(("issue", "ada/engine#1", "Loader drops the last card"))

    result = await rebuild(candidate_id)

    assert (result.created, result.embedded, result.pending_embedding) == (1, 0, 1)


async def test_filtered_items_are_never_chunked_but_squash_commits_join_their_pr(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    embedder(monkeypatch)
    candidate_id = await seed_items(
        ("pull_request", "ada/engine#1", "Add loader\n\nStreams cards."),
        ("commit", "sha-squash", "Add loader (#1)"),
        ("commit", "sha-merge", "Merge branch 'main'"),
    )
    async with session_factory() as session:
        await session.execute(
            text(
                "UPDATE evidence_item SET status = 'filtered', "
                "filter_reason = 'squash_of_pull_request', "
                "meta = '{\"pr_number\": 1}' WHERE external_id = 'sha-squash'"
            )
        )
        await session.execute(
            text(
                "UPDATE evidence_item SET status = 'filtered', filter_reason = 'merge_commit' "
                "WHERE external_id = 'sha-merge'"
            )
        )
        await session.commit()

    await rebuild(candidate_id)

    stored = await chunks()
    assert [c.kind for c in stored] == ["pr"]
    assert "Add loader (#1)" in stored[0].text
    assert "Merge branch" not in stored[0].text
    async with session_factory() as session:
        members = (
            await session.execute(select(func.count()).select_from(EvidenceChunkItem))
        ).scalar_one()
    assert members == 2


async def test_private_items_mark_their_chunks_and_the_summary_reports_the_share(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    embedder(monkeypatch)
    candidate_id = await seed_items(("issue", "ada/secret#1", "Private bug report"), private=True)
    async with session_factory() as session:
        session.add(
            EvidenceItem(
                candidate_id=candidate_id,
                kind=EvidenceKind.issue,
                external_id="ada/open#1",
                project_key="ada/open",
                title="Public bug",
                body="Public bug report",
                status=EvidenceItemStatus.kept,
                content_hash="p",
            )
        )
        await session.commit()

    await rebuild(candidate_id)

    async with session_factory() as session:
        summary = await chunk_summary(session)
    assert summary.chunks == 2
    assert (summary.private_chunks, summary.private_share) == (1, 0.5)
    assert (summary.embedded, summary.pending_embedding) == (2, 0)
    assert summary.by_kind == {"issue": 2}
    assert summary.tokens > 0


async def test_chunk_text_is_redacted_but_the_item_keeps_the_original(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    embedder(monkeypatch)
    candidate_id = await seed_items(
        ("issue", "ada/engine#1", "Mail ada@example.com about the loader")
    )

    result = await rebuild(candidate_id)

    chunk = (await chunks())[0]
    assert "ada@example.com" not in chunk.text
    assert result.redactions == {"EMAIL": 1}
    async with session_factory() as session:
        body = (await session.execute(select(EvidenceItem.body))).scalar_one()
    assert "ada@example.com" in body


async def test_redacted_text_is_what_reaches_the_embedding_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = embedder(monkeypatch)
    candidate_id = await seed_items(
        ("issue", "ada/engine#1", "Mail ada@example.com about the loader")
    )

    await rebuild(candidate_id)

    assert all("ada@example.com" not in text_ for call in calls for text_ in call["input"])  # type: ignore[attr-defined]


async def test_background_rebuild_commits_its_own_session(monkeypatch: pytest.MonkeyPatch) -> None:
    embedder(monkeypatch)
    candidate_id = await seed_items(("issue", "ada/engine#1", "Loader drops the last card"))

    result = await rebuild_chunks_background(candidate_id)

    assert result.created == 1
    assert len(await chunks()) == 1


async def test_time_range_comes_from_the_member_items(monkeypatch: pytest.MonkeyPatch) -> None:
    embedder(monkeypatch)
    candidate_id = await seed_items(("issue", "ada/engine#1", "Loader drops the last card"))
    async with session_factory() as session:
        await session.execute(
            text("UPDATE evidence_item SET occurred_at = :ts"), {"ts": T0 + timedelta(days=2)}
        )
        await session.commit()

    await rebuild(candidate_id)

    chunk = (await chunks())[0]
    assert chunk.time_start == chunk.time_end == T0 + timedelta(days=2)
