import json
import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from fakes import VALID_PROFILE, install_acompletion, llm_response

from app.adapters.llm import LLMError
from app.core.config import get_settings
from app.core.db import session_factory
from app.core.errors import (
    LLMQueryGenerationError,
    NoJobSourcesConfiguredError,
    NoTunableSignalsError,
)
from app.models import Candidate, JobPosting, Match, Profile, SourceState
from app.services.query_builder import (
    ensure_queries_fresh,
    parse_stored,
)
from app.services.query_tuner import aggregate_signal_buckets, tune_for_profile

pytestmark = pytest.mark.usefixtures("clean_tables")

DESCRIPTION = "Work with python and SQL pipelines. " * 5

SPEC_PAYLOAD = {
    "queries": {
        "adzuna": {
            "title": "Data Engineer",
            "skills_all": ["python"],
            "skills": ["tableau"],
            "exclude": ["intern"],
        }
    }
}


@pytest.fixture(autouse=True)
def llm_key(monkeypatch: pytest.MonkeyPatch) -> Any:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


async def _seed_profile(acknowledged: bool = True) -> uuid.UUID:
    async with session_factory() as session:
        candidate = Candidate()
        session.add(candidate)
        await session.flush()
        profile_row = Profile(
            candidate_id=candidate.id, name="Seeker", structured_profile=VALID_PROFILE
        )
        session.add(profile_row)
        if acknowledged:
            session.add(SourceState(source_name="adzuna", acknowledged_at=datetime.now(UTC)))
        await session.commit()
        return profile_row.id


async def _seed_match(
    profile_id: uuid.UUID,
    title: str,
    company: str,
    *,
    saved_at: datetime | None = None,
    clicked_apply_at: datetime | None = None,
    dismissed_at: datetime | None = None,
    description: str = DESCRIPTION,
) -> None:
    async with session_factory() as session:
        posting = JobPosting(
            source="adzuna",
            external_id=f"ext-{title}",
            title=title,
            company=company,
            description=description,
            raw_payload={"id": f"ext-{title}"},
        )
        session.add(posting)
        await session.flush()
        session.add(
            Match(
                profile_id=profile_id,
                job_posting_id=posting.id,
                vector_score=0.5,
                final_score=0.5,
                saved_at=saved_at,
                clicked_apply_at=clicked_apply_at,
                dismissed_at=dismissed_at,
            )
        )
        await session.commit()


async def test_buckets_split_saved_clicked_dismissed_weak() -> None:
    profile_id = await _seed_profile()
    now = datetime.now(UTC)
    await _seed_match(profile_id, "Data Saved", "Acme", saved_at=now)
    await _seed_match(profile_id, "Role Clicked", "Globex", clicked_apply_at=now)
    await _seed_match(profile_id, "Kept Dismissed", "Initech", saved_at=now, dismissed_at=now)
    await _seed_match(profile_id, "Golang Never Opened", "Umbrella")

    async with session_factory() as session:
        buckets = await aggregate_signal_buckets(session, profile_id, ["SQL", "go"])

    positive = buckets["positive"]
    negative = buckets["negative"]
    weak = buckets["weak"]
    assert "data saved" in positive["titles"]
    assert "role clicked" in positive["titles"]
    assert "kept dismissed" in negative["titles"]
    assert "golang never opened" in weak["titles"]
    # dismissal outranks save for bucketing
    assert "kept dismissed" not in positive["titles"]
    assert "kept dismissed" not in weak["titles"]
    # word boundaries + case-insensitivity: "sql" hits the seeded text; "go"
    # must not hit "golang"
    assert positive["skills"]["SQL"] == 2
    assert weak["skills"]["SQL"] == 1
    assert "go" not in weak["skills"]
    assert positive["companies"] == {"acme": 1, "globex": 1}


async def test_tune_rewrites_queries_and_hashes(monkeypatch: pytest.MonkeyPatch) -> None:
    profile_id = await _seed_profile()
    await _seed_match(profile_id, "Data Saved", "Acme", saved_at=datetime.now(UTC))

    async with session_factory() as session:
        profile_row = await session.get(Profile, profile_id)
        assert profile_row is not None
        profile_row.search_queries = {"queries": {"adzuna": {"title": "Old"}}, "generated_at": None}
        await session.commit()
        stale_hash = profile_row.queries_input_hash
        assert stale_hash is None

    calls = install_acompletion(monkeypatch, lambda **kw: llm_response(json.dumps(SPEC_PAYLOAD)))

    async with session_factory() as session:
        response = await tune_for_profile(session, profile_id)
        await session.commit()

    assert response.queries["adzuna"].title == "Data Engineer"
    assert response.generated_by.startswith("tuned:")
    prompt = calls[0]["messages"][1]["content"]
    assert "data saved" in prompt
    assert "acme (1)" in prompt
    # aggregates only — no raw description text in the prompt
    assert "Work with python and SQL pipelines" not in prompt

    async with session_factory() as session:
        stored = await session.get(Profile, profile_id)
        assert stored is not None and stored.queries_input_hash is not None
        # hash now matches current inputs → ensure_queries_fresh must not
        # silently revert the tuned specs
        monkeypatch.setattr(
            "app.services.query_builder.generate_queries",
            _explode,
        )
        assert await ensure_queries_fresh(session, profile_id) is False


async def _explode(*args: Any, **kwargs: Any) -> Any:
    raise LLMQueryGenerationError("background regen must not run after tuning")


async def test_tune_requires_signals() -> None:
    profile_id = await _seed_profile()

    async with session_factory() as session:
        with pytest.raises(NoTunableSignalsError):
            await tune_for_profile(session, profile_id)


async def test_tune_without_sources_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    profile_id = await _seed_profile()
    monkeypatch.setattr("app.services.query_tuner.sources_service.enabled_sources", _no_sources)

    async with session_factory() as session:
        with pytest.raises(NoJobSourcesConfiguredError):
            await tune_for_profile(session, profile_id)


async def _no_sources(_session: Any) -> list[Any]:
    return []


async def test_tune_llm_failure_keeps_stored_specs(monkeypatch: pytest.MonkeyPatch) -> None:
    profile_id = await _seed_profile()
    await _seed_match(profile_id, "Data Saved", "Acme", saved_at=datetime.now(UTC))
    original = json.dumps(
        {
            "queries": {"adzuna": {"title": "Kept Title"}},
            "generated_at": "2026-01-01T00:00:00Z",
            "generated_by": "seed",
            "prompt_version": "search_query_v4",
        }
    )
    async with session_factory() as session:
        profile_row = await session.get(Profile, profile_id)
        assert profile_row is not None
        profile_row.search_queries = json.loads(original)
        profile_row.queries_input_hash = "seed-hash"
        await session.commit()

    def _raise(**kw: Any) -> Any:
        raise LLMError(" tunes are down")

    install_acompletion(monkeypatch, _raise)

    async with session_factory() as session:
        with pytest.raises(LLMQueryGenerationError):
            await tune_for_profile(session, profile_id)
        stored = await session.get(Profile, profile_id)
        assert stored is not None
        assert stored.queries_input_hash == "seed-hash"
        assert parse_stored(stored.search_queries) is not None
        stored_specs = parse_stored(stored.search_queries)
        assert stored_specs is not None
        assert stored_specs.queries["adzuna"].title == "Kept Title"
