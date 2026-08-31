import os
import shutil
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent


def pytest_configure(config: pytest.Config) -> None:
    os.environ.setdefault("UPLOADS_DIR", str(BACKEND_DIR / ".pytest-uploads"))
    test_url = os.environ.get("TEST_DATABASE_URL")
    if test_url:
        os.environ["DATABASE_URL"] = test_url


@pytest.fixture(scope="session")
def migrated_database() -> None:
    if not os.environ.get("TEST_DATABASE_URL"):
        pytest.skip("TEST_DATABASE_URL is not configured")
    from alembic.config import Config

    from alembic import command

    alembic_cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    command.upgrade(alembic_cfg, "head")
    yield
    shutil.rmtree(BACKEND_DIR / ".pytest-uploads", ignore_errors=True)
    command.downgrade(alembic_cfg, "base")


@pytest.fixture
async def clean_tables(migrated_database: None) -> None:
    from sqlalchemy import text

    from app.core.db import engine

    await engine.dispose()
    yield
    async with engine.begin() as conn:
        await conn.execute(text("truncate table resume, candidate"))
    await engine.dispose()
