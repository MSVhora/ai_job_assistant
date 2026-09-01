import uuid
from datetime import UTC, datetime

import pytest
from fakes import FakeJobSource, fake_posting
from sqlalchemy import select

from app.adapters.job_sources import registry
from app.adapters.job_sources.base import ConnectorError
from app.core.db import session_factory
from app.core.errors import (
    JobSourceNotEnabledError,
    NoJobSourcesConfiguredError,
    UnknownJobSourceError,
)
from app.models import JobPosting, JobSearch, SourceState
from app.schemas.job_search import JobSearchRequest
from app.services.ingestion import _selected_sources, run_search

pytestmark = pytest.mark.usefixtures("clean_tables")


def payload(**overrides: object) -> JobSearchRequest:
    defaults: dict[str, object] = {"query": "python developer", "country": "de"}
    return JobSearchRequest(**{**defaults, **overrides})


def only_sources(monkeypatch: pytest.MonkeyPatch, *sources: FakeJobSource) -> None:
    monkeypatch.setattr(registry, "all_sources", lambda: tuple(sources))


async def acknowledge(name: str) -> None:
    async with session_factory() as session:
        session.add(SourceState(source_name=name, acknowledged_at=datetime.now(UTC)))
        await session.commit()


async def selected(payload: JobSearchRequest) -> list[str]:
    async with session_factory() as session:
        return [source.name for source in await _selected_sources(session, payload)]


async def create_run(payload: JobSearchRequest) -> uuid.UUID:
    async with session_factory() as session:
        run = JobSearch(query=payload.model_dump(mode="json"))
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


async def test_run_search_persists_and_dedupes(monkeypatch: pytest.MonkeyPatch) -> None:
    source = FakeJobSource(
        "adzuna", postings=[fake_posting("1", title="Original Title", salary_min=50000.0)]
    )
    only_sources(monkeypatch, source)

    run_1 = await create_run(payload())
    await run_search(run_1, payload())

    postings = await get_postings()
    assert len(postings) == 1
    assert postings[0].title == "Original Title"
    assert postings[0].source == "adzuna"
    assert postings[0].job_search_id == run_1

    refreshed = FakeJobSource(
        "adzuna", postings=[fake_posting("1", title="Refreshed Title", salary_min=65000.0)]
    )
    only_sources(monkeypatch, refreshed)
    run_2 = await create_run(payload())
    await run_search(run_2, payload())

    postings = await get_postings()
    assert len(postings) == 1
    assert postings[0].title == "Refreshed Title"
    assert postings[0].salary_min == 65000.0
    assert postings[0].job_search_id == run_2

    run_row = await get_run(run_2)
    assert run_row.status.value == "succeeded"


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


async def test_failing_source_degrades_to_partial(monkeypatch: pytest.MonkeyPatch) -> None:
    failing = FakeJobSource("adzuna", error=ConnectorError("rate limited"))
    healthy = FakeJobSource("other", postings=[fake_posting("2")])
    only_sources(monkeypatch, failing, healthy)

    run = await create_run(payload())
    await run_search(run, payload())

    run_row = await get_run(run)
    assert run_row.status.value == "partial"
    results = run_row.results
    assert results is not None and len(results) == 2
    failed = next(item for item in results if item["source"] == "adzuna")
    ok = next(item for item in results if item["source"] == "other")
    assert failed["status"] == "failed"
    assert "rate limited" in failed["warning"]
    assert ok["status"] == "ok" and ok["count"] == 1
    assert len(await get_postings()) == 1


async def test_all_sources_failing_marks_run_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    failing = FakeJobSource("adzuna", error=ConnectorError("down"))
    only_sources(monkeypatch, failing)

    run = await create_run(payload())
    await run_search(run, payload())

    run_row = await get_run(run)
    assert run_row.status.value == "failed"
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

    run = await create_run(payload(sources=["apify_linkedin"]))
    await run_search(run, payload(sources=["apify_linkedin"]))

    run_row = await get_run(run)
    assert run_row.status.value == "failed"
    results = run_row.results
    assert results is not None
    assert results[0]["source"] == "run"
    assert "not enabled" in results[0]["warning"]


async def test_selected_sources_rejects_unknown_source() -> None:
    with pytest.raises(UnknownJobSourceError):
        await selected(payload(sources=["does_not_exist"]))


async def test_selected_sources_rejects_when_none_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    only_sources(monkeypatch, FakeJobSource("adzuna", configured=False))
    with pytest.raises(NoJobSourcesConfiguredError):
        await selected(payload())


async def test_selected_sources_requires_acknowledgment_for_scraper(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scraper = FakeJobSource("apify_linkedin", disclosure_required=True)
    only_sources(monkeypatch, FakeJobSource("adzuna"), scraper)

    assert await selected(payload()) == ["adzuna"]
    with pytest.raises(JobSourceNotEnabledError):
        await selected(payload(sources=["apify_linkedin"]))

    await acknowledge("apify_linkedin")
    assert await selected(payload()) == ["adzuna", "apify_linkedin"]
    assert await selected(payload(sources=["apify_linkedin"])) == ["apify_linkedin"]


async def test_selected_sources_filters_by_requested_names(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    only_sources(monkeypatch, FakeJobSource("adzuna"), FakeJobSource("other"))

    assert await selected(payload(sources=["other"])) == ["other"]


async def test_run_search_sends_per_source_specs(monkeypatch: pytest.MonkeyPatch) -> None:
    adzuna = FakeJobSource("adzuna", postings=[fake_posting("1")])
    scraper = FakeJobSource("apify_linkedin", postings=[fake_posting("2")])
    only_sources(monkeypatch, adzuna, scraper)

    run = await create_run(
        payload(
            sources=["adzuna", "apify_linkedin"],
            source_queries={
                "adzuna": {
                    "title": "Senior Android Engineer",
                    "skills": ["Kotlin"],
                    "exclude": ["intern"],
                },
                "apify_linkedin": {
                    "title": "Senior Android Engineer",
                    "skills": ["Kotlin", "Java"],
                },
            },
            salary_min=5000000,
            location="Bangalore",
        )
    )
    await run_search(
        run,
        payload(
            sources=["adzuna", "apify_linkedin"],
            source_queries={
                "adzuna": {
                    "title": "Senior Android Engineer",
                    "skills": ["Kotlin"],
                    "exclude": ["intern"],
                },
                "apify_linkedin": {
                    "title": "Senior Android Engineer",
                    "skills": ["Kotlin", "Java"],
                },
            },
            salary_min=5000000,
            location="Bangalore",
        ),
    )

    adzuna_query = adzuna.queries[0]
    assert adzuna_query.title_phrase == "Senior Android Engineer"
    assert adzuna_query.skills_any == ["Kotlin"]
    assert adzuna_query.exclude_any == ["intern"]
    assert adzuna_query.salary_min == 5000000
    linkedin_query = scraper.queries[0]
    assert linkedin_query.title_phrase == "Senior Android Engineer"
    assert linkedin_query.exclude_any == []

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


async def test_validate_queries_rejects_unknown_override_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services.ingestion import _validate_queries

    only_sources(monkeypatch, FakeJobSource("adzuna"))
    request = payload(query="python", source_queries={"mystery": {"title": "T"}})
    async with session_factory() as session:
        selected = await _selected_sources(session, request)
        with pytest.raises(UnknownJobSourceError):
            _validate_queries(request, selected)
