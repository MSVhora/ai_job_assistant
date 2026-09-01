import json
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from app.adapters.job_sources.adzuna import AdzunaJobSource
from app.adapters.job_sources.base import ConnectorError, JobSearchQuery, RawJobPosting
from app.core.config import get_settings

FIXTURES = Path(__file__).parent / "fixtures"


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
    client = httpx.AsyncClient(transport=handler)
    return AdzunaJobSource(client_factory=lambda: client)


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

    monkeypatch.setattr("app.adapters.job_sources.adzuna._RETRY_DELAY_S", 0)
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


async def test_search_retries_once_on_rate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"count": 0}

    def handler(_: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] == 1:
            return httpx.Response(429)
        return httpx.Response(200, json=_fixture())

    monkeypatch.setattr("app.adapters.job_sources.adzuna._RETRY_DELAY_S", 0)
    source = _mock_source(monkeypatch, httpx.MockTransport(handler))

    postings = await source.search(JobSearchQuery(query="python", country="de"))

    assert calls["count"] == 2
    assert len(postings) == 3


async def test_search_does_not_retry_client_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"count": 0}

    def handler(_: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return httpx.Response(401)

    monkeypatch.setattr("app.adapters.job_sources.adzuna._RETRY_DELAY_S", 0)
    source = _mock_source(monkeypatch, httpx.MockTransport(handler))

    with pytest.raises(ConnectorError, match="status 401"):
        await source.search(JobSearchQuery(query="python", country="de"))
    assert calls["count"] == 1


async def test_search_raises_when_not_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure(monkeypatch, app_id=None)
    source = AdzunaJobSource()

    with pytest.raises(ConnectorError, match="not configured"):
        await source.search(JobSearchQuery(query="python", country="de"))


def test_is_configured_reflects_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure(monkeypatch)
    assert AdzunaJobSource().is_configured() is True
    _configure(monkeypatch, app_id=None)
    assert AdzunaJobSource().is_configured() is False
