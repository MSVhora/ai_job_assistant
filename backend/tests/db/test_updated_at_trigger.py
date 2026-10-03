import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fakes import seed_profile_light
from sqlalchemy import text

from app.core.db import session_factory

pytestmark = pytest.mark.usefixtures("clean_tables")

TABLES_WITH_UPDATED_AT = [
    "achievement",
    "achievement_extraction_run",
    "candidate",
    "evidence_chunk",
    "evidence_item",
    "evidence_scope",
    "evidence_sync_run",
    "job_search",
    "match",
    "match_rebuild",
    "profile",
    "resume_document",
]


async def _updated_at(profile_id: uuid.UUID) -> datetime:
    async with session_factory() as session:
        return (
            await session.execute(
                text("SELECT updated_at FROM profile WHERE id = :id"), {"id": profile_id}
            )
        ).scalar_one()


async def _bulk(sql: str, **params: object) -> None:
    async with session_factory() as session:
        await session.execute(text(sql), params)
        await session.commit()


async def test_updated_at_trigger_exists_on_every_table_with_the_column() -> None:
    async with session_factory() as session:
        columns = (
            await session.execute(
                text(
                    "SELECT table_name FROM information_schema.columns "
                    "WHERE table_schema = 'public' AND column_name = 'updated_at'"
                )
            )
        ).scalars()
        with_column = sorted(columns)
        triggers = (
            await session.execute(
                text(
                    "SELECT event_object_table FROM information_schema.triggers "
                    "WHERE trigger_name LIKE 'trg\\_%\\_set\\_updated\\_at'"
                )
            )
        ).scalars()
        with_trigger = sorted(set(triggers))

    assert with_column == TABLES_WITH_UPDATED_AT
    assert with_trigger == TABLES_WITH_UPDATED_AT


async def test_bulk_update_bumps_updated_at() -> None:
    profile_id = await seed_profile_light("Before")
    before = await _updated_at(profile_id)
    await asyncio.sleep(0.01)

    await _bulk("UPDATE profile SET name = 'After' WHERE id = :id", id=profile_id)

    assert await _updated_at(profile_id) > before


async def test_update_that_changes_nothing_does_not_bump_updated_at() -> None:
    profile_id = await seed_profile_light("Same")
    before = await _updated_at(profile_id)
    await asyncio.sleep(0.01)

    await _bulk("UPDATE profile SET name = 'Same' WHERE id = :id", id=profile_id)

    assert await _updated_at(profile_id) == before


async def test_explicit_updated_at_value_is_kept() -> None:
    profile_id = await seed_profile_light("Backdate")
    backdated = datetime.now(UTC) - timedelta(days=1)

    await _bulk(
        "UPDATE profile SET name = 'Backdated', updated_at = :ts WHERE id = :id",
        id=profile_id,
        ts=backdated,
    )

    assert await _updated_at(profile_id) == backdated
