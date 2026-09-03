import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from app.adapters.job_sources.apify import ApifyActorSource
from app.adapters.job_sources.base import ConnectorError, JobSearchQuery, RawJobPosting
from app.adapters.job_sources.config import ActorConfig
from app.core.config import get_settings

FIXTURES = Path(__file__).parent / "fixtures"


async def _no_delay(_: float) -> None:
    return None


CONFIG = ActorConfig(
    name="apify_linkedin",
    actor_id="hKByXkMQaC5Qt9UMN",
    external_id_field="id",
    input={
        "keywords": "{query}",
        "location": "{location}",
        "limitPerSource": "{results_wanted}",
        "datePosted": "anyTime",
        "scrapeCompany": False,
    },
)


def _fixture() -> list[dict[str, object]]:
    return json.loads((FIXTURES / "linkedin_dataset.json").read_text())


def _raw(item: dict[str, object]) -> RawJobPosting:
    external_id = str(item["id"])
    return RawJobPosting(external_id=external_id, payload=item)


def _mock_source(monkeypatch: pytest.MonkeyPatch, handler: httpx.MockTransport) -> ApifyActorSource:
    monkeypatch.setattr(get_settings(), "apify_token", "test-token")
    client = httpx.AsyncClient(transport=handler)
    return ApifyActorSource(CONFIG, client_factory=lambda: client)


def test_normalize_maps_full_posting() -> None:
    data = ApifyActorSource(CONFIG).normalize(_raw(_fixture()[0]))

    assert data.external_id == "4439105297"
    assert data.title == "Data Analyst"
    assert data.company == "Johnstone Supply"
    assert (
        data.url == "https://www.linkedin.com/jobs/view/data-analyst-at-johnstone-supply-4439105297"
    )
    assert data.location == "Orleans, IN"
    assert data.job_type is not None and data.job_type.value == "full_time"
    assert data.remote_type is None
    assert data.description is not None
    assert data.description.startswith("Johnstone Supply")
    assert data.posted_at == datetime(2026, 7, 12, tzinfo=UTC)
    assert data.salary_min is None and data.salary_max is None
    assert data.raw_payload["id"] == "4439105297"


def test_normalize_maps_contract_type() -> None:
    data = ApifyActorSource(CONFIG).normalize(_raw(_fixture()[2]))

    assert data.job_type is not None and data.job_type.value == "contract"


def test_normalize_parses_salary_range_string() -> None:
    item = {"id": "1", "title": "Analyst", "salary": "$80,000 - $100,000"}
    data = ApifyActorSource(CONFIG).normalize(_raw(item))

    assert data.salary_min == 80000.0
    assert data.salary_max == 100000.0


def test_normalize_parses_salary_info_list_and_swaps_inverted_range() -> None:
    item = {"id": "1", "title": "Analyst", "salaryInfo": ["$100,000", "$80,000"]}
    data = ApifyActorSource(CONFIG).normalize(_raw(item))

    assert data.salary_min == 80000.0
    assert data.salary_max == 100000.0


def test_normalize_maps_remote_and_hybrid_workplace_types() -> None:
    remote = ApifyActorSource(CONFIG).normalize(
        _raw({"id": "1", "title": "A", "workplaceTypes": "Remote"})
    )
    on_site = ApifyActorSource(CONFIG).normalize(
        _raw({"id": "2", "title": "A", "workRemoteAllowed": False, "workplaceTypes": "on-site"})
    )

    assert remote.remote_type is not None and remote.remote_type.value == "remote"
    assert on_site.remote_type is not None and on_site.remote_type.value == "on_site"


def test_normalize_parses_posted_at_timestamp_ms() -> None:
    item = {"id": "1", "title": "A", "postedAtTimestamp": 1692141600000}

    data = ApifyActorSource(CONFIG).normalize(_raw(item))

    assert data.posted_at == datetime.fromtimestamp(1692141600, tz=UTC)


def test_normalize_rejects_posting_without_title() -> None:
    with pytest.raises(ConnectorError):
        ApifyActorSource(CONFIG).normalize(_raw({"id": "1", "title": ""}))


async def test_search_builds_input_and_reads_dataset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if request.method == "POST" and path == "/v2/acts/hKByXkMQaC5Qt9UMN/runs":
            seen["input"] = json.loads(request.content)
            return httpx.Response(200, json={"data": {"id": "run-1", "status": "READY"}})
        if request.method == "GET" and path == "/v2/actor-runs/run-1":
            return httpx.Response(
                200,
                json={"data": {"id": "run-1", "status": "SUCCEEDED", "defaultDatasetId": "ds-1"}},
            )
        if request.method == "GET" and path == "/v2/datasets/ds-1/items":
            return httpx.Response(200, json=_fixture())
        return httpx.Response(404)

    source = _mock_source(monkeypatch, httpx.MockTransport(handler))

    postings = await source.search(
        JobSearchQuery(query="data analyst", country="us", results_wanted=10)
    )

    assert seen["input"] == {
        "keywords": "data analyst",
        "limitPerSource": 10,
        "datePosted": "anyTime",
        "scrapeCompany": False,
    }
    assert [posting.external_id for posting in postings][:2] == [
        "4439105297",
        "4441105250",
    ]


async def test_search_polls_until_succeeded(monkeypatch: pytest.MonkeyPatch) -> None:
    polls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if request.method == "POST":
            return httpx.Response(200, json={"data": {"id": "run-1"}})
        if path == "/v2/actor-runs/run-1":
            polls["count"] += 1
            status = "RUNNING" if polls["count"] < 3 else "SUCCEEDED"
            dataset = {"defaultDatasetId": "ds-1"} if status == "SUCCEEDED" else {}
            return httpx.Response(200, json={"data": {"status": status, **dataset}})
        if path == "/v2/datasets/ds-1/items":
            return httpx.Response(200, json=[])
        return httpx.Response(404)

    monkeypatch.setattr("app.adapters.job_sources.apify._POLL_INTERVAL_S", 0)
    source = _mock_source(monkeypatch, httpx.MockTransport(handler))

    postings = await source.search(JobSearchQuery(query="x", country="us"))

    assert polls["count"] == 3
    assert postings == []


async def test_search_fails_on_terminal_run_status(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(200, json={"data": {"id": "run-1"}})
        return httpx.Response(200, json={"data": {"status": "FAILED"}})

    monkeypatch.setattr("app.adapters.job_sources.apify._POLL_INTERVAL_S", 0)
    source = _mock_source(monkeypatch, httpx.MockTransport(handler))

    with pytest.raises(ConnectorError, match="FAILED"):
        await source.search(JobSearchQuery(query="x", country="us"))


async def test_search_times_out_when_run_never_finishes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(200, json={"data": {"id": "run-1"}})
        return httpx.Response(200, json={"data": {"status": "RUNNING"}})

    monkeypatch.setattr("app.adapters.job_sources.apify._POLL_INTERVAL_S", 0)
    monkeypatch.setattr("app.adapters.job_sources.apify._MAX_WAIT_S", 0.01)
    source = _mock_source(monkeypatch, httpx.MockTransport(handler))

    with pytest.raises(ConnectorError, match="did not finish"):
        await source.search(JobSearchQuery(query="x", country="us"))


async def test_search_builds_nl_keywords_from_spec(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if request.method == "POST" and path == "/v2/acts/hKByXkMQaC5Qt9UMN/runs":
            seen["input"] = json.loads(request.content)
            return httpx.Response(200, json={"data": {"id": "run-1", "status": "READY"}})
        if request.method == "GET" and path == "/v2/actor-runs/run-1":
            return httpx.Response(
                200,
                json={"data": {"id": "run-1", "status": "SUCCEEDED", "defaultDatasetId": "ds-1"}},
            )
        if request.method == "GET" and path == "/v2/datasets/ds-1/items":
            return httpx.Response(200, json=[])
        return httpx.Response(404)

    source = _mock_source(monkeypatch, httpx.MockTransport(handler))

    query = JobSearchQuery(
        query="",
        title_phrase="Senior Android Engineer",
        skills_any=["Kotlin", "Java"],
        exclude_any=["intern"],
        location="Bangalore",
        country="in",
        salary_min=5000000,
        salary_currency="INR",
    )
    postings = await source.search(query)

    assert seen["input"]["keywords"] == (
        "Senior Android Engineer with Kotlin and Java, offering INR 5000000 or more"
    )
    assert seen["input"]["location"] == "Bangalore"
    assert "exclude" not in json.dumps(seen["input"])
    assert postings == []


async def test_search_requires_terms_when_no_query_or_title(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": {"id": "run-1"}})

    source = _mock_source(monkeypatch, httpx.MockTransport(handler))

    with pytest.raises(ConnectorError, match="needs a query"):
        await source.search(JobSearchQuery(query="", country="us"))


async def test_search_retries_once_on_rate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            calls["count"] += 1
            if calls["count"] == 1:
                return httpx.Response(429)
            return httpx.Response(200, json={"data": {"id": "run-1"}})
        return httpx.Response(
            200, json={"data": {"status": "SUCCEEDED", "defaultDatasetId": "ds-1"}}
        )

    monkeypatch.setattr("app.adapters.job_sources.apify._POLL_INTERVAL_S", 0)
    monkeypatch.setattr("app.adapters.retry.asyncio.sleep", _no_delay)
    source = _mock_source(monkeypatch, httpx.MockTransport(handler))

    postings = await source.search(JobSearchQuery(query="x", country="us"))

    assert calls["count"] == 2
    assert postings == []


async def test_search_does_not_retry_client_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"count": 0}

    def handler(_: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return httpx.Response(401)

    source = _mock_source(monkeypatch, httpx.MockTransport(handler))

    with pytest.raises(ConnectorError, match="status 401"):
        await source.search(JobSearchQuery(query="x", country="us"))
    assert calls["count"] == 1


async def test_search_skips_items_without_external_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(200, json={"data": {"id": "run-1"}})
        if request.url.path == "/v2/actor-runs/run-1":
            return httpx.Response(
                200, json={"data": {"status": "SUCCEEDED", "defaultDatasetId": "ds-1"}}
            )
        return httpx.Response(200, json=[{"id": "1", "title": "A"}, {"title": "No id"}])

    source = _mock_source(monkeypatch, httpx.MockTransport(handler))

    postings = await source.search(JobSearchQuery(query="x", country="us"))

    assert [posting.external_id for posting in postings] == ["1"]


async def test_search_raises_when_not_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "apify_token", None)
    source = ApifyActorSource(CONFIG)

    with pytest.raises(ConnectorError, match="not configured"):
        await source.search(JobSearchQuery(query="x", country="us"))


def test_is_configured_reflects_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "apify_token", "t")
    assert ApifyActorSource(CONFIG).is_configured() is True
    monkeypatch.setattr(get_settings(), "apify_token", None)
    assert ApifyActorSource(CONFIG).is_configured() is False


def test_missing_mapper_module_fails_config(tmp_path: Path) -> None:
    config = ActorConfig(name="apify_no_mapper", actor_id="x", external_id_field="id")

    with pytest.raises(ConnectorError, match="no mapper module"):
        ApifyActorSource(config)
