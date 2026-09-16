import json
import uuid

import pytest
from fakes import VALID_PROFILE, install_acompletion, llm_response
from fastapi import BackgroundTasks

from app.adapters.job_sources.base import SourceFilterDecl, SourceFilterOption
from app.core.config import get_settings
from app.schemas.job_search import SourceQuerySpec
from app.schemas.profile import StructuredProfile
from app.services.query_builder import (
    compute_queries_input_hash,
    ensure_queries_fresh,
    generate_queries,
    parse_stored,
    regenerate_for_profile,
)

pytestmark = pytest.mark.usefixtures("clean_tables")


def adzuna_filters() -> list[SourceFilterDecl]:
    return [
        SourceFilterDecl(
            key="sort_by",
            label="Sort by",
            type="select",
            options=[
                SourceFilterOption(value="relevance", label="Relevance"),
                SourceFilterOption(value="date", label="Date"),
                SourceFilterOption(value="salary", label="Salary"),
            ],
        )
    ]


def linkedin_filters() -> list[SourceFilterDecl]:
    return [
        SourceFilterDecl(
            key="workplace_type",
            label="Workplace type",
            type="select",
            options=[SourceFilterOption(value="remote", label="Remote")],
        ),
        SourceFilterDecl(key="under_10_applicants", label="Few applicants", type="boolean"),
    ]


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


async def test_candidate_context_includes_yoe(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = install_acompletion(monkeypatch, lambda **kw: queries_response())
    structured = StructuredProfile.model_validate(
        {
            **VALID_PROFILE,
            "years_of_experience": 7,
            "preferences": {"seniority": "senior"},
        }
    )

    await generate_queries(structured, ["adzuna"])

    prompt = calls[0]["messages"][1]["content"]
    assert "Years of experience: 7" in prompt
    assert "Seniority: senior" in prompt


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
    assert stored.prompt_version == "search_query_v3"
    assert calls[0]["temperature"] == 0.0
    prompt = calls[0]["messages"][1]["content"]
    assert "Senior Data Analyst" in prompt
    assert "SQL" in prompt
    assert "resume text" not in prompt.lower()


async def test_generate_queries_lists_declared_options_in_prompt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = install_acompletion(monkeypatch, lambda **kw: queries_response())
    declarations = {
        "adzuna": adzuna_filters(),
        "apify_linkedin": linkedin_filters(),
    }

    await generate_queries(profile(), ["adzuna", "apify_linkedin"], declarations=declarations)

    prompt = calls[0]["messages"][1]["content"]
    assert "adzuna.options.sort_by" in prompt
    assert "one of: relevance, date, salary" in prompt
    assert "apify_linkedin.options.under_10_applicants" in prompt
    assert "true or false" in prompt


async def test_generate_queries_drops_invented_options(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {
        "queries": {
            "adzuna": {
                "title": "Senior Android Engineer",
                "options": {"sort_by": "date", "bogus_filter": "x"},
            },
        }
    }
    install_acompletion(monkeypatch, lambda **kw: llm_response(json.dumps(payload)))

    stored = await generate_queries(
        profile(), ["adzuna"], declarations={"adzuna": adzuna_filters()}
    )

    assert stored.queries["adzuna"].options == {"sort_by": "date"}


async def test_generate_queries_asks_for_fresh_variant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = install_acompletion(monkeypatch, lambda **kw: queries_response())
    previous = {"adzuna": SourceQuerySpec(title="Old Title")}

    await generate_queries(profile(), ["adzuna"], previous=previous)

    prompt = calls[0]["messages"][1]["content"]
    assert "Old Title" in prompt
    assert "Do not repeat the previous text" in prompt
    assert calls[0]["temperature"] == 0.8


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


class _NoopBackgroundTasks(BackgroundTasks):
    """BackgroundTasks subclass whose scheduled tasks are never executed."""


async def _seed_db_profile() -> uuid.UUID:
    from app.core.db import session_factory
    from app.models import Candidate, Profile

    async with session_factory() as session:
        candidate = Candidate()
        session.add(candidate)
        await session.flush()
        profile_row = Profile(
            candidate_id=candidate.id, name="Android", structured_profile=VALID_PROFILE
        )
        session.add(profile_row)
        await session.commit()
        return profile_row.id


def test_compute_queries_input_hash_deterministic_and_sensitive() -> None:
    declarations = {"adzuna": adzuna_filters()}
    baseline = compute_queries_input_hash(profile(), ["adzuna", "apify_linkedin"], declarations)

    assert baseline == compute_queries_input_hash(
        profile(), ["apify_linkedin", "adzuna"], declarations
    )
    assert baseline != compute_queries_input_hash(profile(), ["adzuna"], declarations)
    assert baseline != compute_queries_input_hash(profile(), ["adzuna", "apify_linkedin"], None)

    modified = profile().model_copy(deep=True)
    modified.preferences = None
    modified.skills = [*modified.skills, "GraphQL"]
    assert baseline != compute_queries_input_hash(
        modified, ["adzuna", "apify_linkedin"], declarations
    )


async def test_ensure_queries_fresh_generates_and_stores_hash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.db import session_factory
    from app.models import Profile

    monkeypatch.setenv("ADZUNA_APP_ID", "id")
    monkeypatch.setenv("ADZUNA_APP_KEY", "key")
    get_settings.cache_clear()
    calls = install_acompletion(monkeypatch, lambda **kw: queries_response())
    profile_id = await _seed_db_profile()

    async with session_factory() as session:
        generated = await ensure_queries_fresh(session, profile_id)
        await session.commit()
    assert generated is True
    assert len(calls) == 1
    assert calls[0]["temperature"] == 0.0

    async with session_factory() as session:
        row = await session.get(Profile, profile_id)
        assert row.queries_input_hash
        assert row.search_queries["queries"]["adzuna"]["title"] == "Senior Android Engineer"

    async with session_factory() as session:
        cached = await ensure_queries_fresh(session, profile_id)
        await session.commit()
    assert cached is False
    assert len(calls) == 1


async def test_ensure_queries_fresh_generates_again_on_changed_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.db import session_factory
    from app.schemas.profile import ProfileUpdate, StructuredProfile
    from app.services.profile_service import save_profile

    monkeypatch.setenv("ADZUNA_APP_ID", "id")
    monkeypatch.setenv("ADZUNA_APP_KEY", "key")
    get_settings.cache_clear()
    calls = install_acompletion(monkeypatch, lambda **kw: queries_response())
    profile_id = await _seed_db_profile()

    async with session_factory() as session:
        assert await ensure_queries_fresh(session, profile_id) is True
        await session.commit()

    modified = StructuredProfile.model_validate(VALID_PROFILE).model_copy(deep=True)
    modified.headline = "Lead Data Analyst"
    async with session_factory() as session:
        await save_profile(
            session,
            _NoopBackgroundTasks(),
            profile_id,
            ProfileUpdate(structured_profile=modified),
        )
        await session.commit()

    async with session_factory() as session:
        assert await ensure_queries_fresh(session, profile_id) is True
        await session.commit()
    assert len(calls) == 2


async def test_ensure_queries_fresh_keeps_specs_when_llm_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.db import session_factory
    from app.models import Profile

    monkeypatch.setenv("ADZUNA_APP_ID", "id")
    monkeypatch.setenv("ADZUNA_APP_KEY", "key")
    get_settings.cache_clear()
    install_acompletion(monkeypatch, lambda **kw: llm_response("complete garbage not json"))
    profile_id = await _seed_db_profile()

    async with session_factory() as session:
        generated = await ensure_queries_fresh(session, profile_id)
        await session.commit()
    assert generated is False

    async with session_factory() as session:
        row = await session.get(Profile, profile_id)
        assert row.queries_input_hash is None


async def test_regenerate_for_profile_overwrites_hash_and_runs_hot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.db import session_factory
    from app.models import Profile

    monkeypatch.setenv("ADZUNA_APP_ID", "id")
    monkeypatch.setenv("ADZUNA_APP_KEY", "key")
    get_settings.cache_clear()
    calls = install_acompletion(monkeypatch, lambda **kw: queries_response())
    profile_id = await _seed_db_profile()

    async with session_factory() as session:
        await ensure_queries_fresh(session, profile_id)
        await session.commit()
    assert len(calls) == 1

    async with session_factory() as session:
        await regenerate_for_profile(session, profile_id, None)
        await session.commit()
    assert len(calls) == 2
    assert calls[1]["temperature"] == 0.8

    async with session_factory() as session:
        row = await session.get(Profile, profile_id)
        assert row.queries_input_hash is not None
