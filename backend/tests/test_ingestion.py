import uuid

import pytest
from fakes import FakeJobSource, fake_posting
from sqlalchemy import select

from app.adapters.job_sources import registry
from app.adapters.job_sources.base import ConnectorError
from app.core.db import session_factory
from app.core.errors import NoJobSourcesConfiguredError, UnknownJobSourceError
from app.models import JobPosting, JobSearch
from app.schemas.job_search import JobSearchRequest
from app.services.ingestion import _selected_sources, run_search

pytestmark = pytest.mark.usefixtures("clean_tables")


def payload(**overrides: object) -> JobSearchRequest:
    defaults: dict[str, object] = {"query": "python developer", "country": "de"}
    return JobSearchRequest(**{**defaults, **overrides})


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


def only_enabled(monkeypatch: pytest.MonkeyPatch, *sources: FakeJobSource) -> None:
    monkeypatch.setattr(registry, "enabled_sources", lambda: list(sources))


async def test_run_search_persists_and_dedupes(monkeypatch: pytest.MonkeyPatch) -> None:
    source = FakeJobSource(
        "adzuna", postings=[fake_posting("1", title="Original Title", salary_min=50000.0)]
    )
    only_enabled(monkeypatch, source)

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
    only_enabled(monkeypatch, refreshed)
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
    only_enabled(monkeypatch, source)

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
    only_enabled(monkeypatch, failing, healthy)

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
    only_enabled(monkeypatch, failing)

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
    only_enabled(monkeypatch, source)

    run = await create_run(payload())
    await run_search(run, payload())

    run_row = await get_run(run)
    assert run_row.status.value == "succeeded"
    results = run_row.results
    assert results is not None
    assert results[0]["count"] == 0
    assert "2 posting(s) skipped" in results[0]["warning"]
    assert await get_postings() == []


async def test_selected_sources_rejects_unknown_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(UnknownJobSourceError):
        _selected_sources(payload(sources=["does_not_exist"]))


async def test_selected_sources_rejects_when_none_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(registry, "enabled_sources", lambda: [])
    with pytest.raises(NoJobSourcesConfiguredError):
        _selected_sources(payload())


async def test_selected_sources_filters_by_requested_names(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    enabled = FakeJobSource("adzuna"), FakeJobSource("other")
    monkeypatch.setattr(registry, "enabled_sources", lambda: list(enabled))
    monkeypatch.setattr(registry, "all_sources", lambda: tuple(enabled))

    selected = _selected_sources(payload(sources=["other"]))

    assert [source.name for source in selected] == ["other"]
