import uuid
from datetime import UTC, datetime

import pytest
from fakes import FakeJobSource, fake_posting, install_aembedding, seed_profile_light
from fastapi import BackgroundTasks
from pydantic import ValidationError
from sqlalchemy import select

from app.adapters.job_sources import registry
from app.adapters.job_sources.base import ConnectorError
from app.adapters.llm import LLMError
from app.core.db import session_factory
from app.core.errors import (
    JobSourceNotEnabledError,
    MissingProfileIdError,
    ProfileNotFoundError,
    UnknownJobSourceError,
)
from app.models import JobPosting, JobSearch, Match, SearchPosting, SourceState
from app.schemas.job_search import JobSearchRequest
from app.services.ingestion import _selected_source, run_search, start_search

pytestmark = pytest.mark.usefixtures("clean_tables")


def payload(**overrides: object) -> JobSearchRequest:
    defaults: dict[str, object] = {
        "query": "python developer",
        "country": "de",
        "source": "adzuna",
    }
    return JobSearchRequest(**{**defaults, **overrides})


def only_sources(monkeypatch: pytest.MonkeyPatch, *sources: FakeJobSource) -> None:
    monkeypatch.setattr(registry, "all_sources", lambda: tuple(sources))


async def acknowledge(name: str) -> None:
    async with session_factory() as session:
        session.add(SourceState(source_name=name, acknowledged_at=datetime.now(UTC)))
        await session.commit()


async def selected(payload: JobSearchRequest) -> str:
    async with session_factory() as session:
        source = await _selected_source(session, payload)
        return source.name


async def create_run(payload: JobSearchRequest) -> uuid.UUID:
    async with session_factory() as session:
        profile_id = payload.profile_id or await seed_profile_light()
        stored = payload.model_copy(update={"profile_id": profile_id})
        run = JobSearch(profile_id=profile_id, query=stored.model_dump(mode="json"))
        session.add(run)
        await session.commit()
        return run.id


async def get_run(run_id: uuid.UUID) -> JobSearch:
    async with session_factory() as session:
        run = await session.get(JobSearch, run_id)
        assert run is not None
        return run


async def get_postings() -> list[JobPosting]:
    async with session_factory() as session:
        result = await session.execute(select(JobPosting).order_by(JobPosting.external_id))
        return list(result.scalars().all())


async def get_associations() -> set[tuple[uuid.UUID, uuid.UUID]]:
    async with session_factory() as session:
        result = await session.execute(select(SearchPosting.search_id, SearchPosting.posting_id))
        return set(result.all())


async def test_run_search_persists_and_dedupes(monkeypatch: pytest.MonkeyPatch) -> None:
    source = FakeJobSource(
        "adzuna", postings=[fake_posting("1", title="Original Title", salary_min=50000.0)]
    )
    only_sources(monkeypatch, source)

    run_1 = await create_run(payload())
    await run_search(run_1, payload())

    postings = await get_postings()
    assert len(postings) == 1
    posting_id = postings[0].id
    assert postings[0].title == "Original Title"
    assert postings[0].source == "adzuna"
    assert await get_associations() == {(run_1, posting_id)}

    refreshed = FakeJobSource(
        "adzuna", postings=[fake_posting("1", title="Refreshed Title", salary_min=65000.0)]
    )
    only_sources(monkeypatch, refreshed)
    run_2 = await create_run(payload())
    await run_search(run_2, payload())

    postings = await get_postings()
    assert len(postings) == 1
    assert postings[0].id == posting_id
    assert postings[0].title == "Refreshed Title"
    assert postings[0].salary_min == 65000.0
    assert await get_associations() == {(run_1, posting_id), (run_2, posting_id)}

    run_row = await get_run(run_2)
    assert run_row.status.value == "succeeded"


async def test_upsert_is_idempotent_for_same_search(monkeypatch: pytest.MonkeyPatch) -> None:
    source = FakeJobSource("adzuna", postings=[fake_posting("1")])
    only_sources(monkeypatch, source)

    run = await create_run(payload())
    await run_search(run, payload())
    await run_search(run, payload())

    postings = await get_postings()
    assert len(postings) == 1
    assert await get_associations() == {(run, postings[0].id)}


async def test_upsert_refreshes_expiry_on_refetch(monkeypatch: pytest.MonkeyPatch) -> None:
    from datetime import timedelta

    source = FakeJobSource(
        "adzuna",
        postings=[fake_posting("1", expires_at=datetime.now(UTC) + timedelta(days=5))],
    )
    only_sources(monkeypatch, source)
    run = await create_run(payload())
    await run_search(run, payload())

    postings = await get_postings()
    assert postings[0].expires_at is not None

    refreshed = FakeJobSource("adzuna", postings=[fake_posting("1")])
    only_sources(monkeypatch, refreshed)
    run_2 = await create_run(payload())
    await run_search(run_2, payload())

    postings = await get_postings()
    assert len(postings) == 1
    assert postings[0].expires_at is None


async def test_start_search_requires_existing_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    only_sources(monkeypatch, FakeJobSource("adzuna"))

    with pytest.raises(MissingProfileIdError):
        await start_search(None, BackgroundTasks(), payload())


async def test_start_search_unknown_profile_returns_404() -> None:
    async with session_factory() as session:
        with pytest.raises(ProfileNotFoundError):
            await start_search(session, BackgroundTasks(), payload(profile_id=uuid.uuid4()))


async def test_start_search_stamps_run_with_profile() -> None:
    profile_id = await seed_profile_light("Owner")
    async with session_factory() as session:
        response = await start_search(session, BackgroundTasks(), payload(profile_id=profile_id))
        await session.commit()
    run_row = await get_run(response.search_id)
    assert run_row.profile_id == profile_id
    assert run_row.query["profile_id"] == str(profile_id)


async def test_run_search_passes_query_to_connector(monkeypatch: pytest.MonkeyPatch) -> None:
    source = FakeJobSource("adzuna", postings=[fake_posting("1")])
    only_sources(monkeypatch, source)

    run = await create_run(payload(location="Berlin", results_wanted=10))
    await run_search(run, payload(location="Berlin", results_wanted=10))

    assert len(source.queries) == 1
    assert source.queries[0].query == "python developer"
    assert source.queries[0].location == "Berlin"
    assert source.queries[0].country == "de"
    assert source.queries[0].results_wanted == 10


async def test_failing_source_marks_run_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    failing = FakeJobSource("adzuna", error=ConnectorError("rate limited"))
    only_sources(monkeypatch, failing)

    run = await create_run(payload())
    await run_search(run, payload())

    run_row = await get_run(run)
    assert run_row.status.value == "failed"
    results = run_row.results
    assert results is not None and len(results) == 1
    failed = results[0]
    assert failed["source"] == "adzuna"
    assert failed["status"] == "failed"
    assert "rate limited" in failed["warning"]
    assert await get_postings() == []


async def test_unmappable_postings_are_skipped_with_warning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class BadNormalizer(FakeJobSource):
        def normalize(self, raw: object) -> object:
            raise ConnectorError("no title")

    source = BadNormalizer("adzuna", postings=[fake_posting("1"), fake_posting("2")])
    only_sources(monkeypatch, source)

    run = await create_run(payload())
    await run_search(run, payload())

    run_row = await get_run(run)
    assert run_row.status.value == "succeeded"
    results = run_row.results
    assert results is not None
    assert results[0]["count"] == 0
    assert "2 posting(s) skipped" in results[0]["warning"]
    assert await get_postings() == []


async def test_run_marks_failed_when_background_selection_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scraper = FakeJobSource("apify_linkedin", disclosure_required=True)
    only_sources(monkeypatch, scraper)

    run = await create_run(payload(source="apify_linkedin"))
    await run_search(run, payload(source="apify_linkedin"))

    run_row = await get_run(run)
    assert run_row.status.value == "failed"
    results = run_row.results
    assert results is not None
    assert results[0]["source"] == "run"
    assert "not enabled" in results[0]["warning"]


async def test_selected_source_rejects_unknown_source() -> None:
    with pytest.raises(UnknownJobSourceError):
        await selected(payload(source="does_not_exist"))


async def test_selected_source_rejects_unconfigured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    only_sources(monkeypatch, FakeJobSource("adzuna", configured=False))
    with pytest.raises(JobSourceNotEnabledError):
        await selected(payload())


async def test_selected_source_requires_acknowledgment_for_scraper(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scraper = FakeJobSource("apify_linkedin", disclosure_required=True)
    only_sources(monkeypatch, FakeJobSource("adzuna"), scraper)

    assert await selected(payload()) == "adzuna"
    with pytest.raises(JobSourceNotEnabledError):
        await selected(payload(source="apify_linkedin"))

    await acknowledge("apify_linkedin")
    assert await selected(payload()) == "adzuna"
    assert await selected(payload(source="apify_linkedin")) == "apify_linkedin"


async def test_selected_source_resolves_requested_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    only_sources(monkeypatch, FakeJobSource("adzuna"), FakeJobSource("other"))

    assert await selected(payload(source="other")) == "other"


async def test_run_search_sends_per_source_specs(monkeypatch: pytest.MonkeyPatch) -> None:
    adzuna = FakeJobSource("adzuna", postings=[fake_posting("1")])
    only_sources(monkeypatch, adzuna)

    request = payload(
        source_queries={
            "adzuna": {
                "title": "Senior Android Engineer",
                "skills": ["Kotlin"],
                "exclude": ["intern"],
            },
        },
        salary_min=5000000,
        location="Bangalore",
    )
    run = await create_run(request)
    await run_search(run, request)

    adzuna_query = adzuna.queries[0]
    assert adzuna_query.title_phrase == "Senior Android Engineer"
    assert adzuna_query.skills_any == ["Kotlin"]
    assert adzuna_query.exclude_any == ["intern"]
    assert adzuna_query.salary_min == 5000000

    run_row = await get_run(run)
    assert run_row.status.value == "succeeded"


async def test_run_search_fails_when_no_effective_query(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    only_sources(monkeypatch, FakeJobSource("adzuna"))
    run = await create_run(payload(query=None))
    await run_search(run, payload(query=None))

    run_row = await get_run(run)
    assert run_row.status.value == "failed"
    results = run_row.results
    assert results is not None
    assert "no search query" in results[0]["warning"]


def test_request_rejects_source_queries_key_mismatch() -> None:
    with pytest.raises(ValidationError, match="source_queries keys must match source"):
        payload(source_queries={"mystery": {"title": "T"}})


async def test_run_search_persists_embeddings(
    monkeypatch: pytest.MonkeyPatch, fake_embedding: list[dict[str, object]]
) -> None:
    source = FakeJobSource(
        "adzuna",
        postings=[
            fake_posting("1", description="First description"),
            fake_posting("2"),
        ],
    )
    only_sources(monkeypatch, source)

    run = await create_run(payload())
    await run_search(run, payload())

    assert len(fake_embedding) == 1
    assert fake_embedding[0]["input"] == ["Job 1\nFirst description"]
    postings = {posting.external_id: posting for posting in await get_postings()}
    assert postings["1"].embedding is not None
    assert len(postings["1"].embedding) == 768
    assert postings["2"].embedding is None
    run_row = await get_run(run)
    assert run_row.status.value == "succeeded"


async def test_embed_failure_keeps_postings_and_warns(monkeypatch: pytest.MonkeyPatch) -> None:
    install_aembedding(monkeypatch, lambda **kw: LLMError("provider down"))
    source = FakeJobSource("adzuna", postings=[fake_posting("1", description="First description")])
    only_sources(monkeypatch, source)

    run = await create_run(payload())
    await run_search(run, payload())

    run_row = await get_run(run)
    assert run_row.status.value == "succeeded"
    results = run_row.results
    assert results is not None
    assert results[0]["status"] == "ok"
    assert "embeddings unavailable" in results[0]["warning"]
    postings = await get_postings()
    assert len(postings) == 1
    assert postings[0].embedding is None


async def test_reingest_refreshes_embedding(monkeypatch: pytest.MonkeyPatch) -> None:
    only_sources(
        monkeypatch,
        FakeJobSource("adzuna", postings=[fake_posting("1", description="First description")]),
    )
    first_run = await create_run(payload())
    await run_search(first_run, payload())
    first_embedding = (await get_postings())[0].embedding

    refreshed = FakeJobSource(
        "adzuna", postings=[fake_posting("1", description="Completely different description")]
    )
    only_sources(monkeypatch, refreshed)
    second_run = await create_run(payload())
    await run_search(second_run, payload())

    postings = await get_postings()
    assert len(postings) == 1
    assert postings[0].embedding is not None
    assert postings[0].embedding != first_embedding
    run_row = await get_run(second_run)
    assert run_row.status.value == "succeeded"


async def seed_profile(name: str = "Seeker") -> uuid.UUID:
    from fakes import VALID_PROFILE

    from app.models import Candidate, Profile
    from app.schemas.profile import StructuredProfile

    async with session_factory() as session:
        result = await session.execute(select(Candidate).limit(1))
        candidate = result.scalars().first()
        if candidate is None:
            candidate = Candidate()
            session.add(candidate)
            await session.flush()
        profile = Profile(
            candidate_id=candidate.id,
            name=name,
            structured_profile=StructuredProfile.model_validate(VALID_PROFILE).model_dump(
                mode="json"
            ),
        )
        session.add(profile)
        await session.flush()
        from app.services.embedding import refresh_profile_embedding

        await refresh_profile_embedding(profile)
        await session.commit()
        return profile.id


async def get_matches(profile_id: uuid.UUID) -> list[Match]:
    async with session_factory() as session:
        result = await session.execute(select(Match).where(Match.profile_id == profile_id))
        return list(result.scalars().all())


async def test_run_search_refreshes_matches_for_run_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fakes import install_acompletion, llm_response

    profile_id = await seed_profile()
    source = FakeJobSource("adzuna", postings=[fake_posting("1", description="Great role")])
    only_sources(monkeypatch, source)
    install_acompletion(
        monkeypatch,
        lambda **kw: llm_response('{"items": []}', prompt_tokens=9, completion_tokens=4),
    )

    run = await create_run(payload(profile_id=profile_id))
    await run_search(run, payload(profile_id=profile_id))

    run_row = await get_run(run)
    assert run_row.status.value == "succeeded"
    assert run_row.profile_id == profile_id
    assert run_row.matching is not None
    assert run_row.matching["status"] == "ok"
    assert run_row.matching["scored_count"] == 1
    assert run_row.matching["rationale_count"] == 0
    assert run_row.matching["rerank_prompt_tokens"] == 9
    assert run_row.matching["rerank_completion_tokens"] == 4
    matches = await get_matches(profile_id)
    assert len(matches) == 1


async def test_run_search_skips_matching_when_profile_has_no_embedding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = FakeJobSource("adzuna", postings=[fake_posting("1")])
    only_sources(monkeypatch, source)

    profile_id = await seed_profile_light("NoEmbedding")
    run = await create_run(payload(profile_id=profile_id))
    await run_search(run, payload(profile_id=profile_id))

    run_row = await get_run(run)
    assert run_row.status.value == "succeeded"
    assert run_row.matching is not None
    assert run_row.matching["status"] == "skipped"
    assert "no embedding" in run_row.matching["warning"]
    assert await get_postings() != []


async def test_run_search_matching_failure_degrades(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fakes import ProviderError, install_acompletion

    profile_id = await seed_profile()
    source = FakeJobSource("adzuna", postings=[fake_posting("1", description="Great role")])
    only_sources(monkeypatch, source)
    install_acompletion(monkeypatch, lambda **kw: ProviderError(400))

    run = await create_run(payload(profile_id=profile_id))
    await run_search(run, payload(profile_id=profile_id))

    run_row = await get_run(run)
    assert run_row.status.value == "succeeded"
    assert run_row.matching is not None
    assert run_row.matching["status"] == "failed"
    assert "re-rank unavailable" in run_row.matching["warning"]


async def test_run_search_honors_explicit_profile_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fakes import install_acompletion, llm_response

    explicit = await seed_profile("Explicit")
    latest = await seed_profile("Latest")
    source = FakeJobSource("adzuna", postings=[fake_posting("1", description="Great role")])
    only_sources(monkeypatch, source)
    install_acompletion(monkeypatch, lambda **kw: llm_response('{"items": []}', prompt_tokens=1))

    run = await create_run(payload(profile_id=explicit))
    await run_search(run, payload(profile_id=explicit))

    run_row = await get_run(run)
    assert run_row.status.value == "succeeded"
    assert run_row.matching is not None
    assert run_row.matching["status"] == "ok"
    matches = await get_matches(explicit)
    assert len(matches) == 1
    assert await get_matches(latest) == []


async def test_get_search_postings_filters_stale_or_expired() -> None:
    from datetime import timedelta

    from app.services.ingestion import get_search_postings

    run = await create_run(payload())

    async with session_factory() as session:
        session.add_all(
            [
                JobPosting(
                    source="adzuna",
                    external_id="fresh",
                    title="Fresh",
                    posted_at=datetime.now(UTC),
                    expires_at=datetime.now(UTC) + timedelta(days=5),
                    raw_payload={"id": "fresh"},
                ),
                JobPosting(
                    source="adzuna",
                    external_id="expired",
                    title="Expired",
                    posted_at=datetime.now(UTC) - timedelta(days=10),
                    expires_at=datetime.now(UTC) - timedelta(days=1),
                    raw_payload={"id": "expired"},
                ),
                JobPosting(
                    source="adzuna",
                    external_id="ancient",
                    title="Ancient",
                    posted_at=datetime.now(UTC) - timedelta(days=60),
                    raw_payload={"id": "ancient"},
                ),
                JobPosting(
                    source="adzuna",
                    external_id="closed",
                    title="Closed",
                    posted_at=datetime.now(UTC),
                    is_closed=True,
                    raw_payload={"id": "closed"},
                ),
            ]
        )
        await session.commit()
        ids = {
            row[0]: row[1]
            for row in (await session.execute(select(JobPosting.external_id, JobPosting.id))).all()
        }
        session.add_all(
            [
                SearchPosting(search_id=run, posting_id=ids[name])
                for name in ["fresh", "expired", "ancient", "closed"]
            ]
        )
        await session.commit()

    run_row = await get_run(run)
    async with session_factory() as session:
        seen = await get_search_postings(session, run, run_row.profile_id)

    assert {summary.title for summary in seen} == {"Fresh"}
