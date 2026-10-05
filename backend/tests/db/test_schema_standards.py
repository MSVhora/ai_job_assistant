import asyncio
import re
import sys
import uuid
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import text

from alembic import command
from app.core.db import engine, session_factory

BACKEND_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND_DIR / "scripts"))

FSTRING_SQL = re.compile(r"""(?:text|execute|exec_driver_sql)\(\s*f["']""", re.MULTILINE)


def _config() -> Config:
    cfg = Config(BACKEND_DIR / "alembic.ini")
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    return cfg


async def _alembic(fn: str, *args: str) -> None:
    await asyncio.get_running_loop().run_in_executor(
        None, lambda: getattr(command, fn)(_config(), *args)
    )
    await engine.dispose()


async def _updated_at_triggers() -> int:
    async with session_factory() as session:
        return (
            await session.execute(
                text(
                    "SELECT count(*) FROM pg_trigger "
                    "WHERE tgname LIKE 'trg\\_%\\_set\\_updated\\_at' AND NOT tgisinternal"
                )
            )
        ).scalar_one()


async def _evidence_objects() -> tuple[int, int, int]:
    async with session_factory() as session:
        row = (
            await session.execute(
                text(
                    "SELECT"
                    " (SELECT count(*) FROM pg_tables WHERE tablename LIKE 'evidence\\_%'),"
                    " (SELECT count(*) FROM pg_type WHERE typname IN ('sync_status',"
                    " 'evidence_kind', 'evidence_item_status', 'evidence_content_level')),"
                    " (SELECT count(*) FROM pg_indexes"
                    " WHERE indexname = 'uq_evidence_sync_active_run')"
                )
            )
        ).one()
    return (row[0], row[1], row[2])


async def _canonical_fk_delete_action() -> str:
    async with session_factory() as session:
        return (
            await session.execute(
                text(
                    "SELECT confdeltype::text FROM pg_constraint "
                    "WHERE conname = 'fk_job_posting_canonical_id'"
                )
            )
        ).scalar_one()


async def test_models_match_migrated_schema(migrated_database: None) -> None:
    await _alembic("check")


async def test_updated_at_trigger_and_set_null_migrations_round_trip(
    migrated_database: None,
) -> None:
    try:
        await _alembic("downgrade", "0021")
        assert await _canonical_fk_delete_action() == "a"

        await _alembic("downgrade", "0020")
        assert await _updated_at_triggers() == 0

        await _alembic("upgrade", "head")
        assert await _updated_at_triggers() == 13
        assert await _canonical_fk_delete_action() == "n"
    finally:
        await _alembic("upgrade", "head")


async def test_evidence_core_migration_round_trip(migrated_database: None) -> None:
    try:
        await _alembic("downgrade", "0022")
        assert await _evidence_objects() == (0, 0, 0)
        assert await _updated_at_triggers() == 5

        await _alembic("upgrade", "head")
        assert await _evidence_objects() == (6, 4, 1)
        assert await _updated_at_triggers() == 13
    finally:
        await _alembic("upgrade", "head")


async def test_llm_output_cache_migration_round_trip(migrated_database: None) -> None:
    async def cache_table_exists() -> bool:
        async with session_factory() as session:
            return (
                await session.execute(text("SELECT to_regclass('llm_output_cache') IS NOT NULL"))
            ).scalar_one()

    try:
        await _alembic("downgrade", "0023")
        assert not await cache_table_exists()

        await _alembic("upgrade", "head")
        assert await cache_table_exists()
    finally:
        await _alembic("upgrade", "head")


async def test_achievements_migration_round_trip(migrated_database: None) -> None:
    async def achievement_objects() -> tuple[int, int, int]:
        async with session_factory() as session:
            row = (
                await session.execute(
                    text(
                        "SELECT"
                        " (SELECT count(*) FROM pg_tables WHERE tablename LIKE 'achievement%'),"
                        " (SELECT count(*) FROM pg_type WHERE typname IN ('achievement_status',"
                        " 'achievement_origin', 'achievement_revision_source')),"
                        " (SELECT count(*) FROM pg_indexes"
                        " WHERE indexname = 'uq_achievement_extraction_active_run')"
                    )
                )
            ).one()
        return (row[0], row[1], row[2])

    try:
        await _alembic("downgrade", "0024")
        assert await achievement_objects() == (0, 0, 0)
        assert await _updated_at_triggers() == 9

        await _alembic("upgrade", "head")
        assert await achievement_objects() == (4, 3, 1)
        assert await _updated_at_triggers() == 13
    finally:
        await _alembic("upgrade", "head")


async def test_resume_document_migration_round_trip_and_checks(migrated_database: None) -> None:
    from fakes import seed_profile_light
    from sqlalchemy.exc import IntegrityError

    async def resume_objects() -> tuple[int, int]:
        async with session_factory() as session:
            row = (
                await session.execute(
                    text(
                        "SELECT"
                        " (SELECT count(*) FROM pg_tables WHERE tablename LIKE 'resume_document%'),"
                        " (SELECT count(*) FROM pg_type WHERE typname = 'resume_document_status')"
                    )
                )
            ).one()
        return (row[0], row[1])

    async def insert(profile_id: uuid.UUID, page_target: int, jd_weight: float) -> None:
        async with session_factory() as session:
            await session.execute(
                text(
                    "INSERT INTO resume_document (candidate_id, profile_id, title, page_target,"
                    " jd_weight) SELECT candidate_id, id, 't', :pages, :weight FROM profile"
                    " WHERE id = :profile_id"
                ),
                {"pages": page_target, "weight": jd_weight, "profile_id": profile_id},
            )
            await session.commit()

    try:
        await _alembic("downgrade", "0025")
        assert await resume_objects() == (0, 0)
        assert await _updated_at_triggers() == 11

        await _alembic("upgrade", "head")
        assert await resume_objects() == (2, 1)
        assert await _updated_at_triggers() == 13

        profile_id = await seed_profile_light()
        await insert(profile_id, 1, 0)
        await insert(profile_id, 4, 0.5)
        for pages, weight in ((0, 0), (5, 0), (1, 0.6), (1, -0.1)):
            with pytest.raises(IntegrityError):
                await insert(profile_id, pages, weight)
        async with session_factory() as session:
            defaults = (
                await session.execute(
                    text("SELECT comments, conflicts, status::text, version FROM resume_document")
                )
            ).first()
        assert defaults is not None
        assert (defaults[0], defaults[1], defaults[2], defaults[3]) == ([], [], "draft", 1)
    finally:
        async with session_factory() as session:
            await session.execute(text("TRUNCATE profile, candidate, resume_document CASCADE"))
            await session.commit()
        await _alembic("upgrade", "head")


async def test_resume_document_generation_migration_round_trip(migrated_database: None) -> None:
    from fakes import seed_profile_light

    async def has_column() -> bool:
        async with session_factory() as session:
            return bool(
                (
                    await session.execute(
                        text(
                            "SELECT count(*) FROM information_schema.columns"
                            " WHERE table_name = 'resume_document' AND column_name = 'generation'"
                        )
                    )
                ).scalar_one()
            )

    try:
        await _alembic("downgrade", "0026")
        assert await has_column() is False

        await _alembic("upgrade", "head")
        assert await has_column() is True

        profile_id = await seed_profile_light()
        async with session_factory() as session:
            await session.execute(
                text(
                    "INSERT INTO resume_document (candidate_id, profile_id, title)"
                    " SELECT candidate_id, id, 't' FROM profile WHERE id = :profile_id"
                ),
                {"profile_id": profile_id},
            )
            await session.commit()
            stored = (
                await session.execute(text("SELECT generation FROM resume_document"))
            ).scalar_one()
        assert stored == {}
    finally:
        async with session_factory() as session:
            await session.execute(text("TRUNCATE profile, candidate, resume_document CASCADE"))
            await session.commit()
        await _alembic("upgrade", "head")


async def test_agent_session_migration_round_trips(migrated_database: None) -> None:
    async def tables() -> set[str]:
        async with session_factory() as session:
            rows = await session.execute(
                text(
                    "SELECT table_name FROM information_schema.tables"
                    " WHERE table_name IN ('agent_session', 'agent_message')"
                )
            )
            return {row[0] for row in rows}

    try:
        await _alembic("downgrade", "0030")
        assert await tables() == set()

        await _alembic("upgrade", "head")
        assert await tables() == {"agent_session", "agent_message"}
    finally:
        await _alembic("upgrade", "head")


async def test_schema_audit_has_no_findings(migrated_database: None) -> None:
    from audit_schema import audit

    async with engine.connect() as conn:
        findings = await audit(conn)
    await engine.dispose()

    assert {title: items for title, items in findings.items() if items} == {}


def test_no_string_formatted_sql_in_app_alembic_or_scripts() -> None:
    offenders = [
        str(path.relative_to(BACKEND_DIR))
        for folder in ("app", "alembic", "scripts")
        for path in (BACKEND_DIR / folder).rglob("*.py")
        if FSTRING_SQL.search(path.read_text())
    ]

    assert offenders == [], "f-string SQL found; use bound parameters"
