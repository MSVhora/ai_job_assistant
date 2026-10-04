import asyncio
import uuid

import pytest
from fakes import seed_profile_light
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.core.db import session_factory
from app.models import (
    Candidate,
    EvidenceChunk,
    EvidenceChunkItem,
    EvidenceItem,
    EvidenceKind,
    EvidenceScope,
    EvidenceSourceAccount,
    EvidenceSyncRun,
    SyncStatus,
)

pytestmark = pytest.mark.usefixtures("clean_tables")


async def _candidate_id() -> uuid.UUID:
    await seed_profile_light()
    async with session_factory() as session:
        return (await session.execute(select(Candidate.id))).scalars().first()  # type: ignore[return-value]


async def _source(candidate_id: uuid.UUID) -> uuid.UUID:
    async with session_factory() as session:
        source = EvidenceSourceAccount(candidate_id=candidate_id, kind="github")
        session.add(source)
        await session.commit()
        return source.id


def _item(candidate_id: uuid.UUID, external_id: str = "sha1", **kw: object) -> EvidenceItem:
    return EvidenceItem(
        candidate_id=candidate_id,
        kind=EvidenceKind.commit,
        external_id=external_id,
        body="Fix race in token refresh",
        content_hash="h" * 64,
        **kw,
    )


async def test_evidence_item_identity_is_unique_per_candidate_kind_external_id() -> None:
    candidate_id = await _candidate_id()
    async with session_factory() as session:
        session.add(_item(candidate_id))
        await session.commit()

    async with session_factory() as session:
        session.add(_item(candidate_id))
        with pytest.raises(IntegrityError):
            await session.commit()

    async with session_factory() as session:
        session.add(_item(candidate_id, external_id="sha2"))
        session.add(
            EvidenceItem(
                candidate_id=candidate_id,
                kind=EvidenceKind.note,
                external_id="sha1",
                body="same id, different kind",
                content_hash="h" * 64,
            )
        )
        await session.commit()


async def test_evidence_item_defaults_are_kept_and_not_private() -> None:
    candidate_id = await _candidate_id()
    async with session_factory() as session:
        item = _item(candidate_id)
        session.add(item)
        await session.commit()
        await session.refresh(item)

    assert item.status.value == "kept"
    assert item.is_private is False
    assert item.authored_by_user is True
    assert item.meta == {}


async def test_second_active_sync_run_for_a_source_is_rejected_by_the_index() -> None:
    source_id = await _source(await _candidate_id())
    async with session_factory() as session:
        session.add(EvidenceSyncRun(source_id=source_id, status=SyncStatus.running))
        await session.commit()

    async with session_factory() as session:
        session.add(EvidenceSyncRun(source_id=source_id, status=SyncStatus.pending))
        with pytest.raises(IntegrityError, match="uq_evidence_sync_active_run"):
            await session.commit()


async def test_terminal_and_paused_sync_runs_do_not_block_a_new_active_run() -> None:
    source_id = await _source(await _candidate_id())
    async with session_factory() as session:
        for status in (SyncStatus.succeeded, SyncStatus.failed, SyncStatus.paused):
            session.add(EvidenceSyncRun(source_id=source_id, status=status))
        session.add(EvidenceSyncRun(source_id=source_id, status=SyncStatus.pending))
        await session.commit()


async def test_concurrent_active_runs_are_stopped_by_the_index_not_the_app() -> None:
    source_id = await _source(await _candidate_id())

    async def insert() -> bool:
        async with session_factory() as session:
            session.add(EvidenceSyncRun(source_id=source_id, status=SyncStatus.pending))
            try:
                await session.commit()
            except IntegrityError:
                return False
            return True

    results = await asyncio.gather(insert(), insert())

    assert sorted(results) == [False, True]


async def test_deleting_a_source_cascades_to_scopes_and_runs_but_keeps_items() -> None:
    candidate_id = await _candidate_id()
    source_id = await _source(candidate_id)
    async with session_factory() as session:
        scope = EvidenceScope(source_id=source_id, ref="ada/repo")
        session.add(scope)
        session.add(EvidenceSyncRun(source_id=source_id, status=SyncStatus.succeeded))
        await session.flush()
        session.add(_item(candidate_id, scope_id=scope.id))
        await session.commit()

    async with session_factory() as session:
        await session.execute(text("DELETE FROM evidence_source WHERE id = :id"), {"id": source_id})
        await session.commit()

    async with session_factory() as session:
        counts = (
            await session.execute(
                text(
                    "SELECT (SELECT count(*) FROM evidence_scope),"
                    " (SELECT count(*) FROM evidence_sync_run),"
                    " (SELECT count(*) FROM evidence_item WHERE scope_id IS NULL)"
                )
            )
        ).one()
    assert tuple(counts) == (0, 0, 1)


async def test_scope_ref_is_unique_per_source() -> None:
    source_id = await _source(await _candidate_id())
    async with session_factory() as session:
        session.add(EvidenceScope(source_id=source_id, ref="ada/repo"))
        await session.commit()

    async with session_factory() as session:
        session.add(EvidenceScope(source_id=source_id, ref="ada/repo"))
        with pytest.raises(IntegrityError):
            await session.commit()


async def test_scope_defaults_are_disabled_with_message_level_content() -> None:
    source_id = await _source(await _candidate_id())
    async with session_factory() as session:
        scope = EvidenceScope(source_id=source_id, ref="ada/private-repo", is_private=True)
        session.add(scope)
        await session.commit()
        await session.refresh(scope)

    assert scope.enabled is False
    assert scope.content_level.value == "messages_and_prs"
    assert scope.sync_state is SyncStatus.pending
    assert scope.cursor == {}


async def test_chunk_item_links_cascade_and_reject_dangling_references() -> None:
    candidate_id = await _candidate_id()
    async with session_factory() as session:
        item = _item(candidate_id)
        chunk = EvidenceChunk(
            candidate_id=candidate_id,
            kind="commit_group",
            text="Fix race in token refresh",
            content_hash="c" * 64,
            chunker_version="v1",
            contains_private=True,
        )
        session.add_all([item, chunk])
        await session.flush()
        session.add(EvidenceChunkItem(chunk_id=chunk.id, item_id=item.id))
        await session.commit()
        chunk_id, item_id = chunk.id, item.id

    async with session_factory() as session:
        session.add(EvidenceChunkItem(chunk_id=uuid.uuid4(), item_id=item_id))
        with pytest.raises(IntegrityError):
            await session.commit()

    async with session_factory() as session:
        await session.execute(text("DELETE FROM evidence_item WHERE id = :id"), {"id": item_id})
        await session.commit()
        links = (
            await session.execute(text("SELECT count(*) FROM evidence_chunk_item"))
        ).scalar_one()
        kept = (
            await session.execute(
                text("SELECT count(*) FROM evidence_chunk WHERE id = :id"), {"id": chunk_id}
            )
        ).scalar_one()
    assert (links, kept) == (0, 1)


async def test_chunk_token_count_cannot_be_negative() -> None:
    candidate_id = await _candidate_id()
    async with session_factory() as session:
        session.add(
            EvidenceChunk(
                candidate_id=candidate_id,
                kind="note",
                text="t",
                token_count=-1,
                content_hash="c" * 64,
                chunker_version="v1",
            )
        )
        with pytest.raises(IntegrityError, match="token_count_nonneg"):
            await session.commit()


async def test_evidence_chunk_embedding_is_nullable_vector_768() -> None:
    candidate_id = await _candidate_id()
    async with session_factory() as session:
        session.add(
            EvidenceChunk(
                candidate_id=candidate_id,
                kind="note",
                text="t",
                content_hash="c" * 64,
                chunker_version="v1",
                embedding=[0.1] * 768,
            )
        )
        await session.commit()
        stored = (
            await session.execute(text("SELECT vector_dims(embedding) FROM evidence_chunk"))
        ).scalar_one()
    assert stored == 768


async def test_updated_at_trigger_exists_on_every_evidence_table_with_the_column() -> None:
    async with session_factory() as session:
        names = (
            (
                await session.execute(
                    text("SELECT tgname FROM pg_trigger WHERE tgname LIKE 'trg\\_evidence%'")
                )
            )
            .scalars()
            .all()
        )
    assert sorted(names) == [
        f"trg_{table}_set_updated_at"
        for table in ("evidence_chunk", "evidence_item", "evidence_scope", "evidence_sync_run")
    ]


async def test_scope_listing_cache_columns_have_safe_defaults() -> None:
    candidate_id = await _candidate_id()
    source_id = await _source(candidate_id)
    async with session_factory() as session:
        session.add(EvidenceScope(source_id=source_id, ref="ada/engine"))
        await session.commit()

    async with session_factory() as session:
        scope = (await session.execute(select(EvidenceScope))).scalars().one()
        account = (await session.execute(select(EvidenceSourceAccount))).scalars().one()

    assert (scope.is_fork, scope.contributed, scope.new_since_refresh) == (False, False, False)
    assert scope.visible is True
    assert (scope.description, scope.pushed_at) == (None, None)
    assert (account.scopes_refreshed_at, account.token_scopes) == (None, None)
