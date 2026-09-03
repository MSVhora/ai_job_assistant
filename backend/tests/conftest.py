import os
import shutil
from pathlib import Path
from typing import Any

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
        await conn.execute(
            text(
                "truncate table job_posting, job_search, source_state, profile_revision, "
                "profile, resume, candidate cascade"
            )
        )
    await engine.dispose()


@pytest.fixture(autouse=True)
def fake_embedding(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    import litellm
    from fakes import embedding_response, fake_vector

    calls: list[dict[str, Any]] = []

    async def _spy(**kwargs: Any) -> object:
        calls.append(kwargs)
        texts = kwargs.get("input") or []
        return embedding_response([fake_vector(str(text)) for text in texts])

    monkeypatch.setattr(litellm, "aembedding", _spy)
    return calls
