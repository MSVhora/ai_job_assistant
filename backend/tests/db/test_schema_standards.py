import asyncio
import re
import sys
from pathlib import Path

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
        assert await _updated_at_triggers() == 9
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
        assert await _updated_at_triggers() == 9
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
