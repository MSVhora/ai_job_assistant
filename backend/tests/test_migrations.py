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
