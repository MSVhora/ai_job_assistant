import json
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from app.adapters.job_sources.adzuna import AdzunaJobSource
from app.adapters.job_sources.base import (
    ConnectorError,
    JobSearchQuery,
    RawJobPosting,
    TermPlan,
)
from app.core.config import get_settings

FIXTURES = Path(__file__).parent / "fixtures"


async def _no_delay(_: float) -> None:
    return None


def _fixture() -> dict[str, object]:
    return json.loads((FIXTURES / "adzuna_search_response.json").read_text())


def _raws() -> list[RawJobPosting]:
    payload = _fixture()
    results = payload["results"]
    assert isinstance(results, list)
    return [
        RawJobPosting(external_id=str(item["id"]), payload=item)
        for item in results
        if isinstance(item, dict) and "id" in item
    ]


def _request_params(url: str) -> dict[str, str]:
    return {key: values[0] for key, values in parse_qs(urlparse(url).query).items()}


def _configure(monkeypatch: pytest.MonkeyPatch, app_id: str | None = "test-id") -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "adzuna_app_id", app_id)
    monkeypatch.setattr(settings, "adzuna_app_key", "test-key" if app_id else None)


def _mock_source(
    monkeypatch: pytest.MonkeyPatch,
    handler: httpx.MockTransport,
) -> AdzunaJobSource:
    _configure(monkeypatch)
    # A fresh client per call: the connector's budget-gated multi-pass loop
    # makes more than one HTTP call per run, and a shared client cannot be
    # reopened after close.
    return AdzunaJobSource(client_factory=lambda: httpx.AsyncClient(transport=handler))


def test_normalize_maps_full_posting() -> None:
    source = AdzunaJobSource()
    data = source.normalize(_raws()[0])

    assert data.external_id == "5862011801"
    assert data.title == "Software & Data Engineer (m/f/d)"
    assert data.company == "Markant Gruppe"
    assert data.location == "Offenburg, Ortenaukreis"
    assert data.url == "https://www.adzuna.de/land/ad/5862011801"
    assert data.job_type is not None and data.job_type.value == "full_time"
    assert data.remote_type is None
    assert data.description == "Lead the data platform team. SQL Python"
    assert data.posted_at == datetime(2026, 8, 30, 10, 22, 10, tzinfo=UTC)
    assert data.salary_min == 60000.0
    assert data.salary_max == 80000.0
    assert data.currency is None
    assert data.raw_payload["id"] == "5862011801"


def test_normalize_maps_minimal_posting_from_contract_type() -> None:
    source = AdzunaJobSource()
    data = source.normalize(_raws()[1])

    assert data.title == "Backend Engineer"
    assert data.company == "STRATEC SE"
    assert data.job_type is not None and data.job_type.value == "contract"
    assert data.salary_min is None
    assert data.salary_max is None
    assert data.posted_at is not None


def test_normalize_rejects_posting_without_title() -> None:
    source = AdzunaJobSource()
    with pytest.raises(ConnectorError):
        source.normalize(_raws()[2])


async def test_search_requests_country_path_and_params(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, json=_fixture())

    monkeypatch.setattr("app.adapters.retry.asyncio.sleep", _no_delay)
    source = _mock_source(monkeypatch, httpx.MockTransport(handler))

    postings = await source.search(
        JobSearchQuery(query="python developer", country="DE", results_wanted=50)
    )

    params = _request_params(str(seen["url"]))
    assert "https://api.adzuna.com/v1/api/jobs/de/search/1" in str(seen["url"])
    assert params["app_id"] == "test-id"
    assert params["app_key"] == "test-key"
    assert params["what"] == "python developer"
    assert params["results_per_page"] == "50"
    assert [posting.external_id for posting in postings] == [
        "5862011801",
        "5861903807",
        "5860000001",
    ]


async def test_search_sends_max_days_old_param(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, json=_fixture())

    monkeypatch.setattr("app.adapters.retry.asyncio.sleep", _no_delay)
    source = _mock_source(monkeypatch, httpx.MockTransport(handler))

    await source.search(JobSearchQuery(query="python developer", country="DE", max_days_old=7))

    params = _request_params(str(seen["url"]))
    assert params["max_days_old"] == "7"


async def test_search_sends_params_for_declared_options(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, json=_fixture())

    monkeypatch.setattr("app.adapters.retry.asyncio.sleep", _no_delay)
    source = _mock_source(monkeypatch, httpx.MockTransport(handler))

    await source.search(
        JobSearchQuery(
            query="python",
            country="de",
            location="Berlin",
            options={"title_only": True, "distance_km": 25, "sort_by": "date"},
        )
    )

    params = _request_params(str(seen["url"]))
    assert params["title_only"] == "true"
    assert params["distance"] == "25"
    assert params["sort_by"] == "date"


async def test_search_skips_distance_without_location(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, json=_fixture())

    monkeypatch.setattr("app.adapters.retry.asyncio.sleep", _no_delay)
    source = _mock_source(monkeypatch, httpx.MockTransport(handler))

    await source.search(
        JobSearchQuery(
            query="python", country="de", options={"distance_km": 25, "title_only": True}
        )
    )

    params = _request_params(str(seen["url"]))
    assert "distance" not in params
    assert params["title_only"] == "true"


def test_filters_declared_capabilities() -> None:
    source = AdzunaJobSource()

    keys = [decl.key for decl in source.filters()]
    assert keys == [
        "title_only",
        "job_type",
        "distance_km",
        "sort_by",
    ]
    job_type = source.filters()[1]
    assert job_type.type == "select"
    assert job_type.required is False
    assert job_type.options is not None
    assert [option.value for option in job_type.options] == [
        "full_time",
        "part_time",
        "contract",
        "permanent",
    ]
    sort_by = source.filters()[3]
    assert sort_by.options is not None
    assert [option.value for option in sort_by.options] == ["relevance", "date", "salary"]


async def test_search_retries_once_on_rate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"count": 0}

    def handler(_: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] == 1:
            return httpx.Response(429)
        return httpx.Response(200, json=_fixture())

    monkeypatch.setattr("app.adapters.retry.asyncio.sleep", _no_delay)
    source = _mock_source(monkeypatch, httpx.MockTransport(handler))

    postings = await source.search(JobSearchQuery(query="python", country="de"))

    assert calls["count"] == 2
    assert len(postings) == 3


async def test_search_does_not_retry_client_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"count": 0}

    def handler(_: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return httpx.Response(401)

    monkeypatch.setattr("app.adapters.retry.asyncio.sleep", _no_delay)
    source = _mock_source(monkeypatch, httpx.MockTransport(handler))

    with pytest.raises(ConnectorError, match="status 401"):
        await source.search(JobSearchQuery(query="python", country="de"))
    assert calls["count"] == 1


async def test_search_raises_when_not_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure(monkeypatch, app_id=None)
    source = AdzunaJobSource()

    with pytest.raises(ConnectorError, match="not configured"):
        await source.search(JobSearchQuery(query="python", country="de"))


async def test_search_sends_structured_params_for_spec(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    broad: dict[str, str] = {}
    titles: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        params = _request_params(str(request.url))
        if "title_only" in params:
            titles.update(params)
        else:
            broad.update(params)
        return httpx.Response(200, json=_fixture())

    monkeypatch.setattr("app.adapters.retry.asyncio.sleep", _no_delay)
    source = _mock_source(monkeypatch, httpx.MockTransport(handler))

    query = JobSearchQuery(
        term_plan=TermPlan(
            what_phrase="Senior Android Engineer",
            what_and=["kotlin", "compose"],
            what_or=["Kotlin", "Java"],
            what_exclude=["intern"],
        ),
        country="in",
        salary_min=5000000,
    )
    postings = await source.search(query)

    assert broad["what_phrase"] == "Senior Android Engineer"
    assert broad["what_and"] == "kotlin compose"
    assert broad["what_or"] == "Kotlin Java"
    assert broad["what_exclude"] == "intern"
    assert broad["salary_min"] == "5000000"
    assert "what" not in broad
    assert "title_only" not in broad
    assert titles["title_only"] == "true"
    assert titles["what_phrase"] == "Senior Android Engineer"
    # Page-1 fixture is not full, so no pagination and exactly 2 calls.
    assert len(postings) == len({p.external_id for p in postings})


async def test_search_maps_free_text_what_from_plan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, json=_fixture())

    monkeypatch.setattr("app.adapters.retry.asyncio.sleep", _no_delay)
    source = _mock_source(monkeypatch, httpx.MockTransport(handler))

    query = JobSearchQuery(
        term_plan=TermPlan(what="android developer", what_and=["kotlin", "compose"]),
        country="in",
    )
    await source.search(query)

    params = _request_params(str(seen["url"]))
    assert params["what"] == "android developer"
    assert params["what_and"] == "kotlin compose"
    assert "what_phrase" not in params


async def test_search_requires_terms_when_no_query_or_title(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_fixture())

    monkeypatch.setattr("app.adapters.retry.asyncio.sleep", _no_delay)
    source = _mock_source(monkeypatch, httpx.MockTransport(handler))

    with pytest.raises(ConnectorError, match="needs a query"):
        await source.search(JobSearchQuery(query="", country="de"))


def test_is_configured_reflects_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure(monkeypatch)
    assert AdzunaJobSource().is_configured() is True
    _configure(monkeypatch, app_id=None)
    assert AdzunaJobSource().is_configured() is False


def _page_fixture(count: int, first_id: int = 90_000_000) -> dict[str, object]:
    results = [
        {
            "id": first_id + index,
            "title": f"Engineer {index}",
            "redirect_url": f"https://adzuna.test/land/{first_id + index}",
            "created": "2026-08-30T10:22:10+00:00",
            "description": "Build things",
        }
        for index in range(count)
    ]
    return {"count": count, "page": 1, "results": results}


def _recording_handler(calls: list[dict[str, str]], fixture: dict[str, object]):
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(_request_params(str(request.url)))
        return httpx.Response(200, json=fixture)

    return handler


async def test_search_salary_include_unknown_when_no_salary_floor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, str]] = []
    handler = _recording_handler(calls, _fixture())
    monkeypatch.setattr("app.adapters.retry.asyncio.sleep", _no_delay)
    source = _mock_source(monkeypatch, httpx.MockTransport(handler))

    await source.search(JobSearchQuery(query="python", country="de"))

    assert calls[0]["salary_include_unknown"] == "1"
    assert "salary_min" not in calls[0]


async def test_search_omits_salary_include_unknown_when_floor_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, str]] = []
    handler = _recording_handler(calls, _fixture())
    monkeypatch.setattr("app.adapters.retry.asyncio.sleep", _no_delay)
    source = _mock_source(monkeypatch, httpx.MockTransport(handler))

    await source.search(JobSearchQuery(query="python", country="de", salary_min=60000))

    assert "salary_include_unknown" not in calls[0]
    assert calls[0]["salary_min"] == "60000"


async def test_search_single_call_with_explicit_title_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, str]] = []
    handler = _recording_handler(calls, _fixture())
    monkeypatch.setattr("app.adapters.retry.asyncio.sleep", _no_delay)
    source = _mock_source(monkeypatch, httpx.MockTransport(handler))

    await source.search(
        JobSearchQuery(
            country="de",
            term_plan=TermPlan(what_phrase="Backend Engineer", what_or=["Python"]),
            options={"title_only": True},
        )
    )

    assert len(calls) == 1
    assert calls[0]["title_only"] == "true"


async def test_search_single_call_without_title_phrase(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, str]] = []
    handler = _recording_handler(calls, _fixture())
    monkeypatch.setattr("app.adapters.retry.asyncio.sleep", _no_delay)
    source = _mock_source(monkeypatch, httpx.MockTransport(handler))

    await source.search(JobSearchQuery(query="python", country="de"))

    assert len(calls) == 1


async def test_search_dedupes_title_pass_by_external_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, str]] = []
    handler = _recording_handler(calls, _fixture())
    monkeypatch.setattr("app.adapters.retry.asyncio.sleep", _no_delay)
    source = _mock_source(monkeypatch, httpx.MockTransport(handler))

    postings = await source.search(
        JobSearchQuery(
            country="de",
            term_plan=TermPlan(what_phrase="Data Engineer", what_or=["SQL"]),
        )
    )

    # Same fixture on both passes: 6 raw results collapse to 3 unique ids.
    assert len(calls) == 2
    assert len(postings) == 3
    assert [posting.external_id for posting in postings] == [
        "5862011801",
        "5861903807",
        "5860000001",
    ]


async def test_search_maps_job_type_select_to_one_contract_param(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, str]] = []
    handler = _recording_handler(calls, _fixture())
    monkeypatch.setattr("app.adapters.retry.asyncio.sleep", _no_delay)
    source = _mock_source(monkeypatch, httpx.MockTransport(handler))

    await source.search(
        JobSearchQuery(query="python", country="de", options={"job_type": "full_time"})
    )

    params = calls[0]
    assert params["full_time"] == "true"
    assert "part_time" not in params
    assert "contract" not in params
    assert "permanent" not in params


async def test_search_omits_contract_params_when_job_type_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, str]] = []
    handler = _recording_handler(calls, _fixture())
    monkeypatch.setattr("app.adapters.retry.asyncio.sleep", _no_delay)
    source = _mock_source(monkeypatch, httpx.MockTransport(handler))

    await source.search(JobSearchQuery(query="python", country="de"))

    params = calls[0]
    assert "full_time" not in params
    assert "part_time" not in params
    assert "contract" not in params
    assert "permanent" not in params


async def test_search_fetches_page_two_when_page_one_full(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    urls: list[str] = []
    page2 = _page_fixture(50, first_id=91_000_000)

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "/search/2" in url:
            return httpx.Response(200, json=page2)
        urls.append(url)
        return httpx.Response(200, json=_page_fixture(50))

    monkeypatch.setattr("app.adapters.retry.asyncio.sleep", _no_delay)
    source = _mock_source(monkeypatch, httpx.MockTransport(handler))

    postings = await source.search(JobSearchQuery(query="python", country="de", results_wanted=100))

    assert urls and all("/search/1" in url for url in urls)
    assert len(postings) == 100
    ids = [posting.external_id for posting in postings]
    assert len(ids) == len(set(ids))
    assert ids[0] == "90000000"
    assert ids[50] == "91000000"


async def test_search_no_page_two_when_page_not_full(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, str]] = []
    handler = _recording_handler(calls, _page_fixture(30))
    monkeypatch.setattr("app.adapters.retry.asyncio.sleep", _no_delay)
    source = _mock_source(monkeypatch, httpx.MockTransport(handler))

    postings = await source.search(JobSearchQuery(query="python", country="de"))

    assert len(calls) == 1
    assert len(postings) == 30


async def test_search_no_page_two_when_results_wanted_met(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, str]] = []
    handler = _recording_handler(calls, _page_fixture(50))
    monkeypatch.setattr("app.adapters.retry.asyncio.sleep", _no_delay)
    source = _mock_source(monkeypatch, httpx.MockTransport(handler))

    postings = await source.search(JobSearchQuery(query="python", country="de"))

    assert len(calls) == 1
    assert len(postings) == 50


async def test_search_stops_when_budget_exhausted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "max_adzuna_calls_per_run", 2)
    calls: list[dict[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(_request_params(str(request.url)))
        first_id = 91_000_000 if "/search/2" in str(request.url) else 90_000_000
        return httpx.Response(200, json=_page_fixture(50, first_id=first_id))

    monkeypatch.setattr("app.adapters.retry.asyncio.sleep", _no_delay)
    source = _mock_source(monkeypatch, httpx.MockTransport(handler))

    postings = await source.search(JobSearchQuery(query="python", country="de", results_wanted=100))

    assert len(calls) == 2
    assert len(postings) == 100
    ids = [posting.external_id for posting in postings]
    assert len(ids) == len(set(ids))
