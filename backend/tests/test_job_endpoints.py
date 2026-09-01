import uuid

import pytest
from fakes import FakeJobSource, fake_posting
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.adapters.job_sources import registry
from app.core.db import session_factory
from app.main import app
from app.models import JobPosting

pytestmark = pytest.mark.usefixtures("clean_tables")


@pytest.fixture
async def client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        yield async_client


async def test_search_start_and_status_flow(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = FakeJobSource("adzuna", postings=[fake_posting("1", title="Data Engineer")])
    monkeypatch.setattr(registry, "enabled_sources", lambda: [source])

    response = await client.post(
        "/api/jobs/search",
        json={"query": "python developer", "location": "Berlin", "country": "de"},
    )
    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "pending"
    search_id = body["search_id"]

    status = (await client.get(f"/api/jobs/searches/{search_id}")).json()
    assert status["status"] == "succeeded"
    assert status["query"] == {
        "query": "python developer",
        "location": "Berlin",
        "country": "de",
        "results_wanted": 50,
        "sources": None,
    }
    assert status["results"] == [{"source": "adzuna", "status": "ok", "count": 1, "warning": None}]


async def test_search_persists_postings(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = FakeJobSource("adzuna", postings=[fake_posting("1"), fake_posting("2")])
    monkeypatch.setattr(registry, "enabled_sources", lambda: [source])

    start = (await client.post("/api/jobs/search", json={"query": "data", "country": "de"})).json()

    async with session_factory() as session:
        postings = (await session.execute(select(JobPosting))).scalars().all()
    assert len(postings) == 2
    assert all(posting.job_search_id == uuid.UUID(start["search_id"]) for posting in postings)


async def test_search_without_configured_sources_returns_400(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(registry, "enabled_sources", lambda: [])

    response = await client.post("/api/jobs/search", json={"query": "data", "country": "de"})

    assert response.status_code == 400
    assert "no job sources" in response.json()["detail"]


async def test_search_with_unknown_source_returns_400(client: AsyncClient) -> None:
    response = await client.post(
        "/api/jobs/search",
        json={"query": "data", "country": "de", "sources": ["not_a_source"]},
    )

    assert response.status_code == 400
    assert "unknown job source" in response.json()["detail"]


async def test_search_validates_country(client: AsyncClient) -> None:
    response = await client.post(
        "/api/jobs/search",
        json={"query": "data", "country": "germany"},
    )

    assert response.status_code == 422


async def test_search_normalizes_country(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = FakeJobSource("adzuna", postings=[])
    monkeypatch.setattr(registry, "enabled_sources", lambda: [source])

    response = await client.post("/api/jobs/search", json={"query": "data", "country": "DE"})

    assert response.status_code == 202
    assert source.queries[0].country == "de"


async def test_get_unknown_search_returns_404(client: AsyncClient) -> None:
    response = await client.get(f"/api/jobs/searches/{uuid.uuid4()}")

    assert response.status_code == 404


async def test_list_sources_returns_adzuna_metadata(client: AsyncClient) -> None:
    response = await client.get("/api/sources")

    assert response.status_code == 200
    sources = response.json()
    adzuna = next(source for source in sources if source["name"] == "adzuna")
    assert adzuna["is_official_api"] is True
    assert adzuna["disclosure_required"] is False
    assert isinstance(adzuna["is_configured"], bool)
