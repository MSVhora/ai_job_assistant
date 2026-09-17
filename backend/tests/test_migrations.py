"""Migration 0013 verification: up/down round-trip + backfill correctness.

Runs its own alembic cycle on the scratch test database and leaves the schema
at `head` so the rest of the suite is unaffected. Asserts the issue #24
contract: ownership from `query->>'profile_id'`, orphan adoption
(most-recently-updated profile), `job_search_id` → `search_posting` seeding,
append-only unique pair, and the destructive downgrade reconstruction.
"""

import asyncio
import json
import uuid

import pytest
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.core.db import session_factory


def _alembic() -> Config:
    from pathlib import Path

    backend_dir = Path(__file__).resolve().parent.parent
    cfg = Config(backend_dir / "alembic.ini")
    cfg.set_main_option("script_location", str(backend_dir / "alembic"))
    return cfg


def _run_alembic(op: str, arg: str) -> None:
    from alembic import command

    command.__getattribute__(op)(_alembic(), arg)


async def migrate(op: str, arg: str) -> None:
    await asyncio.get_running_loop().run_in_executor(None, _run_alembic, op, arg)
    from app.core.db import engine

    await engine.dispose()


@pytest.fixture
async def migration_database(migrated_database: None):
    await migrate("downgrade", "0012")
    yield
    await migrate("upgrade", "head")


async def _seed_0012_rows() -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID]:
    """Seed at 0012: one profile, three searches, one posting.

    Returns (owned_search, orphan_echo_search, orphan_blank_search,
    owning_profile, posting) ids.
    """
    owning_profile = uuid.uuid4()
    owned_search = uuid.uuid4()
    orphan_echo_search = uuid.uuid4()
    orphan_blank_search = uuid.uuid4()
    posting = uuid.uuid4()

    async with session_factory() as session:
        conn = await session.connection()
        await conn.execute(text("INSERT INTO candidate (id) VALUES (:id)"), {"id": uuid.uuid4()})
        candidate = (await conn.execute(text("SELECT id FROM candidate LIMIT 1"))).scalar_one()
        await conn.execute(
            text(
                "INSERT INTO profile (id, candidate_id, name, structured_profile) "
                "VALUES (:id, :cid, 'Good', '{}')"
            ),
            {"id": owning_profile, "cid": candidate},
        )
        for search_id, query in [
            (owned_search, {"query": "data", "profile_id": str(owning_profile)}),
            # stale echo pointing at a profile that no longer exists → adopted
            (orphan_echo_search, {"query": "data", "profile_id": str(uuid.uuid4())}),
            # no echo at all → adopted
            (orphan_blank_search, {"query": "data"}),
        ]:
            await conn.execute(
                text(
                    "INSERT INTO job_search (id, status, query) "
                    "VALUES (:id, 'succeeded', CAST(:query AS jsonb))"
                ),
                {"id": search_id, "query": json.dumps(query)},
            )
        await conn.execute(
            text(
                "INSERT INTO job_posting (id, source, external_id, title, raw_payload, "
                "job_search_id) VALUES (:id, 'adzuna', 'x1', 'Posting A', '{}', :search_id)"
            ),
            {"id": posting, "search_id": owned_search},
        )
        await session.commit()
    return owned_search, orphan_echo_search, orphan_blank_search, owning_profile, posting


async def test_migration_0013_backfill_and_roundtrip(migration_database: None) -> None:
    (
        owned_search,
        orphan_echo_search,
        orphan_blank_search,
        owning_profile,
        posting,
    ) = await _seed_0012_rows()

    await migrate("upgrade", "0013")

    async with session_factory() as session:
        conn = await session.connection()

        owners = {
            str(row[0]): row[1]
            for row in (await conn.execute(text("SELECT id, profile_id FROM job_search"))).all()
        }
        # every search owned; echo-mapped search points at the echoed profile;
        # orphans adopt the single most-recently-updated profile (the only one).
        assert owners[str(owned_search)] == owning_profile
        assert owners[str(orphan_echo_search)] == owning_profile
        assert owners[str(orphan_blank_search)] == owning_profile

        nulls = (
            await conn.execute(text("SELECT count(*) FROM job_search WHERE profile_id IS NULL"))
        ).scalar_one()
        assert nulls == 0

        associations = (
            await conn.execute(text("SELECT search_id, posting_id FROM search_posting"))
        ).all()
        assert associations == [(owned_search, posting)]

        pointer = (
            await conn.execute(
                text(
                    "SELECT count(*) FROM information_schema.columns "
                    "WHERE table_name='job_posting' AND column_name='job_search_id'"
                )
            )
        ).scalar_one()
        assert pointer == 0

        with pytest.raises(DBAPIError):
            await conn.execute(
                text(
                    "INSERT INTO search_posting (search_id, posting_id) "
                    "SELECT search_id, posting_id FROM search_posting"
                )
            )
        await conn.rollback()

    await migrate("downgrade", "0012")

    async with session_factory() as session:
        conn = await session.connection()
        # destructive downgrade: pointer repopulated from the first association
        revived = (
            await conn.execute(
                text("SELECT job_search_id FROM job_posting WHERE id = :id"),
                {"id": posting},
            )
        ).scalar_one()
        assert revived == owned_search

        assert (
            await conn.execute(
                text(
                    "SELECT count(*) FROM information_schema.tables "
                    "WHERE table_name='search_posting'"
                )
            )
        ).scalar_one() == 0
        assert (
            await conn.execute(
                text(
                    "SELECT count(*) FROM information_schema.columns "
                    "WHERE table_name='job_search' AND column_name='profile_id'"
                )
            )
        ).scalar_one() == 0


async def _expiry_columns(conn) -> dict[str, tuple[bool, bool]]:
    rows = await conn.execute(
        text(
            "SELECT column_name, is_nullable, column_default FROM information_schema.columns "
            "WHERE table_name='job_posting' AND column_name IN ('expires_at', 'is_closed')"
        )
    )
    mapping = rows.all()
    return {name: (nullable == "YES", default is not None) for name, nullable, default in mapping}


@pytest.fixture
async def migration_0014(migrated_database: None):
    await migrate("downgrade", "0014")
    yield
    await migrate("upgrade", "head")


async def test_migration_0015_expiry_roundtrip(migration_0014: None) -> None:
    marker = f"expiry-{uuid.uuid4()}"
    async with session_factory() as session:
        conn = await session.connection()
        assert await _expiry_columns(conn) == {}

    await migrate("upgrade", "head")

    async with session_factory() as session:
        conn = await session.connection()
        expired = await _expiry_columns(conn)
        assert expired["expires_at"] == (True, False)
        assert expired["is_closed"] == (False, True)

        await conn.execute(
            text(
                "INSERT INTO job_posting (id, source, external_id, title, raw_payload) "
                "VALUES (:id, 'adzuna', :external_id, 'Posting A', '{}')"
            ),
            {"id": uuid.uuid4(), "external_id": marker},
        )
        defaults = (
            await conn.execute(
                text(
                    "SELECT expires_at, is_closed FROM job_posting WHERE external_id = :external_id"
                ),
                {"external_id": marker},
            )
        ).one()
        assert defaults[0] is None
        assert defaults[1] is False
        await conn.rollback()

    await migrate("downgrade", "0014")

    async with session_factory() as session:
        conn = await session.connection()
        assert await _expiry_columns(conn) == {}


@pytest.fixture
async def migration_0016(migrated_database: None):
    await migrate("downgrade", "0016")
    yield
    await migrate("upgrade", "head")


async def test_migration_0017_source_backfill_and_index(migration_0016: None) -> None:
    profile_id = uuid.uuid4()
    marker_new = uuid.uuid4()
    marker_legacy = uuid.uuid4()
    marker_unrecoverable = uuid.uuid4()
    async with session_factory() as session:
        conn = await session.connection()
        await conn.execute(text("INSERT INTO candidate (id) VALUES (:id)"), {"id": uuid.uuid4()})
        candidate = (await conn.execute(text("SELECT id FROM candidate LIMIT 1"))).scalar_one()
        await conn.execute(
            text(
                "INSERT INTO profile (id, candidate_id, name, structured_profile) "
                "VALUES (:id, :cid, 'Owner', '{}')"
            ),
            {"id": profile_id, "cid": candidate},
        )
        await conn.execute(
            text(
                "INSERT INTO job_search (id, profile_id, status, query) VALUES "
                "(:id, :profile_id, 'succeeded', :query)"
            ),
            {
                "id": marker_new,
                "profile_id": profile_id,
                "query": json.dumps({"query": "python dev", "source": "adzuna"}),
            },
        )
        await conn.execute(
            text(
                "INSERT INTO job_search (id, profile_id, status, query) VALUES "
                "(:id, :profile_id, 'succeeded', :query)"
            ),
            {
                "id": marker_legacy,
                "profile_id": profile_id,
                "query": json.dumps({"query": "python dev", "sources": ["apify_linkedin"]}),
            },
        )
        await conn.execute(
            text(
                "INSERT INTO job_search (id, profile_id, status, query) VALUES "
                "(:id, :profile_id, 'succeeded', :query)"
            ),
            {
                "id": marker_unrecoverable,
                "profile_id": profile_id,
                "query": json.dumps({"query": "python dev", "sources": None}),
            },
        )
        await conn.commit()

    await migrate("upgrade", "head")

    async with session_factory() as session:
        conn = await session.connection()
        nullable = (
            await conn.execute(
                text(
                    "SELECT is_nullable FROM information_schema.columns "
                    "WHERE table_name='job_search' AND column_name='source'"
                )
            )
        ).scalar_one()
        assert nullable == "NO"
        source_rows = (
            await conn.execute(
                text("SELECT id::text, source FROM job_search WHERE id = ANY(:ids)"),
                {"ids": [str(marker_new), str(marker_legacy), str(marker_unrecoverable)]},
            )
        ).all()
        sources = {row[0]: row[1] for row in source_rows}
        assert sources[str(marker_new)] == "adzuna"
        assert sources[str(marker_legacy)] == "apify_linkedin"
        assert marker_unrecoverable not in sources

        index_names = {
            row[0]
            for row in await conn.execute(
                text("SELECT indexname FROM pg_indexes WHERE tablename='job_search'")
            )
        }
        assert "uq_job_search_active_run" in index_names

        partial = (
            await conn.execute(
                text(
                    "SELECT indexdef FROM pg_indexes "
                    "WHERE tablename='job_search' AND indexname='uq_job_search_active_run'"
                )
            )
        ).scalar_one()
        assert "'pending'" in partial and "'running'" in partial

    await migrate("downgrade", "0016")

    async with session_factory() as session:
        conn = await session.connection()
        remaining = (
            await conn.execute(
                text(
                    "SELECT count(*) FROM information_schema.columns "
                    "WHERE table_name='job_search' AND column_name='source'"
                )
            )
        ).scalar_one()
        assert remaining == 0


@pytest.fixture
async def migration_0017(migrated_database: None):
    await migrate("downgrade", "0017")
    yield
    await migrate("upgrade", "head")


async def test_migration_0019_dedupe_columns_and_trgm(migration_0017: None) -> None:
    canonical_id = uuid.uuid4()
    duplicate_id = uuid.uuid4()

    await migrate("upgrade", "head")

    async with session_factory() as session:
        conn = await session.connection()
        columns = {
            row[0]
            for row in await conn.execute(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name='job_posting' AND column_name IN "
                    "('canonical_id', 'source_urls', 'country')"
                )
            )
        }
        assert columns == {"canonical_id", "source_urls", "country"}
        assert (
            await conn.execute(text("SELECT count(*) FROM pg_extension WHERE extname='pg_trgm'"))
        ).scalar_one() == 1
        index_names = {
            row[0]
            for row in await conn.execute(
                text("SELECT indexname FROM pg_indexes WHERE tablename='job_posting'")
            )
        }
        assert "ix_job_posting_title_trgm" in index_names
        assert "ix_job_posting_canonical_id" in index_names

        await conn.execute(
            text(
                "INSERT INTO job_posting (id, source, external_id, title, raw_payload, country) "
                "VALUES (:id, 'adzuna', 'canon', 'Backend Engineer', '{}', 'de')"
            ),
            {"id": canonical_id},
        )
        await conn.execute(
            text(
                "INSERT INTO job_posting (id, source, external_id, title, raw_payload, "
                "canonical_id, source_urls) VALUES (:id, 'apify_linkedin', 'dup', "
                "'Backend Engineer', '{}', :canonical, CAST(:urls AS jsonb))"
            ),
            {
                "id": duplicate_id,
                "canonical": canonical_id,
                "urls": '[{"source": "apify_linkedin", "url": null}]',
            },
        )
        await session.commit()

    async with session_factory() as session:
        conn = await session.connection()
        await conn.execute(
            text("DELETE FROM job_posting WHERE id = ANY(:ids)"),
            {"ids": [str(canonical_id), str(duplicate_id)]},
        )
        await session.commit()

    await migrate("downgrade", "0018")

    async with session_factory() as session:
        conn = await session.connection()
        remaining = {
            row[0]
            for row in await conn.execute(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name='job_posting'"
                )
            )
        }
        assert {"canonical_id", "source_urls", "country"}.isdisjoint(remaining)
        assert (
            await conn.execute(text("SELECT count(*) FROM pg_extension WHERE extname='pg_trgm'"))
        ).scalar_one() == 0


async def test_migration_0018_hybrid_columns_and_fallback_row_downgrade(
    migration_0017: None,
) -> None:
    profile_id = uuid.uuid4()
    posting_kept = uuid.uuid4()
    posting_fallback = uuid.uuid4()
    match_kept = uuid.uuid4()
    match_fallback = uuid.uuid4()

    await migrate("upgrade", "head")

    async with session_factory() as session:
        conn = await session.connection()
        await conn.execute(text("INSERT INTO candidate (id) VALUES (:id)"), {"id": uuid.uuid4()})
        candidate = (await conn.execute(text("SELECT id FROM candidate LIMIT 1"))).scalar_one()
        await conn.execute(
            text(
                "INSERT INTO profile (id, candidate_id, name, structured_profile) "
                "VALUES (:id, :cid, 'Owner', '{}')"
            ),
            {"id": profile_id, "cid": candidate},
        )
        for posting_id, ext in (
            (posting_kept, f"kept-{posting_kept}"),
            (posting_fallback, f"fallback-{posting_fallback}"),
        ):
            await conn.execute(
                text(
                    "INSERT INTO job_posting (id, source, external_id, title, raw_payload) "
                    "VALUES (:id, 'adzuna', :ext, 'Un-embedded', '{}')"
                ),
                {"id": posting_id, "ext": ext},
            )
        await conn.execute(
            text(
                "INSERT INTO match (id, profile_id, job_posting_id, vector_score, final_score) "
                "VALUES (:id, :pid, :jpid, 0.5, 0.5)"
            ),
            {"id": match_kept, "pid": profile_id, "jpid": posting_kept},
        )
        await conn.execute(
            text(
                "INSERT INTO match (id, profile_id, job_posting_id, vector_score, final_score, "
                "skill_score) VALUES (:id, :pid, :jpid, NULL, 0.9, 0.9)"
            ),
            {"id": match_fallback, "pid": profile_id, "jpid": posting_fallback},
        )
        await conn.commit()

    await migrate("downgrade", "0017")

    async with session_factory() as session:
        conn = await session.connection()
        columns = {
            row[0]
            for row in await conn.execute(
                text("SELECT column_name FROM information_schema.columns WHERE table_name='match'")
            )
        }
        assert {"skill_score", "recency_score", "salary_score"}.isdisjoint(columns)
        nullable = (
            await conn.execute(
                text(
                    "SELECT is_nullable FROM information_schema.columns "
                    "WHERE table_name='match' AND column_name='vector_score'"
                )
            )
        ).scalar_one()
        assert nullable == "NO"
        remaining = {
            str(row[0]) for row in await conn.execute(text("SELECT job_posting_id FROM match"))
        }
        assert str(posting_fallback) not in remaining
        assert str(posting_kept) in remaining


async def test_migration_0020_engagement_signal_columns(migration_0017: None) -> None:
    signal_columns = {"first_opened_at", "clicked_apply_at", "saved_at", "dismissed_at"}

    await migrate("upgrade", "head")

    async with session_factory() as session:
        conn = await session.connection()
        columns = {
            row[0]
            for row in await conn.execute(
                text("SELECT column_name FROM information_schema.columns WHERE table_name='match'")
            )
        }
        assert signal_columns <= columns
        nullable = {
            row[0]: row[1]
            for row in await conn.execute(
                text(
                    "SELECT column_name, is_nullable FROM information_schema.columns "
                    "WHERE table_name='match'"
                )
            )
        }
        assert all(nullable[name] == "YES" for name in signal_columns)

    await migrate("downgrade", "0019")

    async with session_factory() as session:
        conn = await session.connection()
        columns = {
            row[0]
            for row in await conn.execute(
                text("SELECT column_name FROM information_schema.columns WHERE table_name='match'")
            )
        }
        assert signal_columns.isdisjoint(columns)
