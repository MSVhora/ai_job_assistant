import json

import pytest
from fakes import VALID_PROFILE, install_acompletion, llm_response

from app.core.config import get_settings
from app.schemas.job_search import SourceQuerySpec
from app.schemas.profile import StructuredProfile
from app.services.query_builder import (
    generate_queries,
    parse_stored,
    regenerate_for_profile,
)

pytestmark = pytest.mark.usefixtures("clean_tables")

SPEC_PAYLOAD = {
    "queries": {
        "adzuna": {
            "title": "Senior Android Engineer",
            "skills": ["Kotlin", "Java"],
            "exclude": ["intern"],
        },
        "apify_linkedin": {"title": "Senior Android Engineer", "skills": ["Kotlin", "Java"]},
    }
}


@pytest.fixture(autouse=True)
def llm_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def queries_response() -> object:
    return llm_response(json.dumps(SPEC_PAYLOAD))


def profile() -> StructuredProfile:
    return StructuredProfile.model_validate(VALID_PROFILE)


async def test_generate_queries_produces_stamped_specs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = install_acompletion(monkeypatch, lambda **kw: queries_response())

    stored = await generate_queries(profile(), ["adzuna", "apify_linkedin"])

    assert set(stored.queries) == {"adzuna", "apify_linkedin"}
    assert stored.queries["adzuna"].title == "Senior Android Engineer"
    assert stored.queries["adzuna"].exclude == ["intern"]
    assert stored.queries["apify_linkedin"].exclude is None
    assert stored.generated_by == "gemini/gemini-2.5-flash"
    assert stored.prompt_version == "search_query_v1"
    assert calls[0]["temperature"] == 0.8
    prompt = calls[0]["messages"][1]["content"]
    assert "Senior Data Analyst" in prompt
    assert "SQL" in prompt
    assert "resume text" not in prompt.lower()


async def test_generate_queries_asks_for_fresh_variant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = install_acompletion(monkeypatch, lambda **kw: queries_response())
    previous = {"adzuna": SourceQuerySpec(title="Old Title")}

    await generate_queries(profile(), ["adzuna"], previous=previous)

    prompt = calls[0]["messages"][1]["content"]
    assert "Old Title" in prompt
    assert "Do not repeat the previous text" in prompt


async def test_generate_queries_missing_source_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    install_acompletion(
        monkeypatch,
        lambda **kw: llm_response(
            json.dumps({"queries": {"adzuna": {"title": "Senior Android Engineer"}}})
        ),
    )

    with pytest.raises(Exception, match="missing sources"):
        await generate_queries(profile(), ["adzuna", "apify_linkedin"])


async def test_generate_queries_overlong_title_fails_after_repair(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_acompletion(
        monkeypatch,
        lambda **kw: llm_response(json.dumps({"queries": {"adzuna": {"title": "T" * 100}}})),
    )

    with pytest.raises(Exception, match="failed validation"):
        await generate_queries(profile(), ["adzuna"])


async def test_generate_queries_requires_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    def not_configured() -> bool:
        return False

    monkeypatch.setattr("app.services.query_builder.is_llm_configured", not_configured)

    with pytest.raises(Exception, match="not configured"):
        await generate_queries(profile(), ["adzuna"])


def test_parse_stored_rejects_garbage() -> None:
    assert parse_stored({"queries": "nope"}) is None
    assert parse_stored(None) is None
    assert parse_stored({"not_queries": {}}) is None


async def test_regenerate_for_profile_persists_and_returns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.db import session_factory
    from app.models import Candidate, Profile

    monkeypatch.setenv("ADZUNA_APP_ID", "id")
    monkeypatch.setenv("ADZUNA_APP_KEY", "key")
    get_settings.cache_clear()
    calls = install_acompletion(monkeypatch, lambda **kw: queries_response())

    async with session_factory() as session:
        candidate = Candidate()
        session.add(candidate)
        await session.flush()
        profile_row = Profile(
            candidate_id=candidate.id, name="Android", structured_profile=VALID_PROFILE
        )
        session.add(profile_row)
        await session.commit()
        profile_id = profile_row.id

    async with session_factory() as session:
        response = await regenerate_for_profile(session, profile_id, None)
        await session.commit()

    assert set(response.queries) == {"adzuna"}
    assert response.queries["adzuna"].title == "Senior Android Engineer"
    assert "Sources needing a query spec: adzuna" in calls[0]["messages"][1]["content"]
    async with session_factory() as session:
        stored = (await session.get(Profile, profile_id)).search_queries
    assert stored["queries"]["adzuna"]["title"] == "Senior Android Engineer"
    assert stored["generated_by"] == "gemini/gemini-2.5-flash"


async def test_regenerate_for_profile_rejects_unknown_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.db import session_factory
    from app.models import Candidate, Profile

    monkeypatch.setenv("ADZUNA_APP_ID", "id")
    monkeypatch.setenv("ADZUNA_APP_KEY", "key")
    get_settings.cache_clear()

    async with session_factory() as session:
        candidate = Candidate()
        session.add(candidate)
        await session.flush()
        profile_row = Profile(
            candidate_id=candidate.id, name="Android", structured_profile=VALID_PROFILE
        )
        session.add(profile_row)
        await session.commit()
        profile_id = profile_row.id
        with pytest.raises(Exception, match="not enabled"):
            await regenerate_for_profile(session, profile_id, ["apify_linkedin"])
