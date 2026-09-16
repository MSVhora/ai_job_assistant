import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fakes import FakeJobSource, fake_posting, seed_profile_light
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.adapters.job_sources import registry
from app.core.db import session_factory
from app.main import app
from app.models import JobPosting, SearchPosting

pytestmark = pytest.mark.usefixtures("clean_tables")


@pytest.fixture
async def client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        yield async_client


async def test_search_start_and_status_flow(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    profile_id = await seed_profile_light("Owner")
    source = FakeJobSource("adzuna", postings=[fake_posting("1", title="Data Engineer")])
    monkeypatch.setattr(registry, "all_sources", lambda: (source,))

    response = await client.post(
        "/api/jobs/search",
        json={
            "query": "python developer",
            "profile_id": str(profile_id),
            "location": "Berlin",
            "country": "de",
            "source": "adzuna",
        },
    )
    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "pending"
    search_id = body["search_id"]

    status = (
        await client.get(f"/api/jobs/searches/{search_id}", params={"profile_id": profile_id})
    ).json()
    assert status["status"] == "succeeded"
    assert status["query"] == {
        "query": "python developer",
        "profile_id": str(profile_id),
        "source_queries": None,
        "location": "Berlin",
        "country": "de",
        "results_wanted": 50,
        "max_days_old": None,
        "salary_min": None,
        "salary_max": None,
        "salary_currency": None,
        "seniority": None,
        "source": "adzuna",
    }
    assert status["results"] == [{"source": "adzuna", "status": "ok", "count": 1, "warning": None}]


async def test_search_persists_postings_and_associations(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    profile_id = await seed_profile_light("Owner")
    source = FakeJobSource("adzuna", postings=[fake_posting("1"), fake_posting("2")])
    monkeypatch.setattr(registry, "all_sources", lambda: (source,))

    start = (
        await client.post(
            "/api/jobs/search",
            json={
                "query": "data",
                "profile_id": str(profile_id),
                "country": "de",
                "source": "adzuna",
            },
        )
    ).json()

    async with session_factory() as session:
        postings = (await session.execute(select(JobPosting))).scalars().all()
        associations = (await session.execute(select(SearchPosting))).scalars().all()
    assert len(postings) == 2
    assert {association.posting_id for association in associations} == {
        posting.id for posting in postings
    }
    assert all(
        association.search_id == uuid.UUID(start["search_id"]) for association in associations
    )
    assert not hasattr(postings[0], "job_search_id")


async def test_search_without_profile_id_returns_400(client: AsyncClient) -> None:
    response = await client.post(
        "/api/jobs/search", json={"query": "data", "country": "de", "source": "adzuna"}
    )
    assert response.status_code == 400
    assert "profile_id is required" in response.json()["detail"]


async def test_search_with_unknown_profile_returns_404(client: AsyncClient) -> None:
    response = await client.post(
        "/api/jobs/search",
        json={
            "query": "data",
            "country": "de",
            "profile_id": str(uuid.uuid4()),
            "source": "adzuna",
        },
    )
    assert response.status_code == 404
    assert "profile not found" in response.json()["detail"]


async def test_search_records_max_days_old_and_validates_bounds(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    profile_id = await seed_profile_light("Owner")
    monkeypatch.setattr(
        registry, "all_sources", lambda: (FakeJobSource("adzuna", configured=True),)
    )

    start = await client.post(
        "/api/jobs/search",
        json={
            "query": "python developer",
            "profile_id": str(profile_id),
            "country": "de",
            "source": "adzuna",
            "max_days_old": 7,
        },
    )
    assert start.status_code == 202
    search_id = start.json()["search_id"]

    status = (
        await client.get(f"/api/jobs/searches/{search_id}", params={"profile_id": profile_id})
    ).json()
    assert status["query"]["max_days_old"] == 7

    invalid = await client.post(
        "/api/jobs/search",
        json={
            "query": "python developer",
            "profile_id": str(profile_id),
            "country": "de",
            "source": "adzuna",
            "max_days_old": 91,
        },
    )
    assert invalid.status_code == 422
    zero = await client.post(
        "/api/jobs/search",
        json={
            "query": "python developer",
            "profile_id": str(profile_id),
            "country": "de",
            "source": "adzuna",
            "max_days_old": 0,
        },
    )
    assert zero.status_code == 422


async def test_search_with_unconfigured_source_returns_409(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    profile_id = await seed_profile_light("Owner")
    monkeypatch.setattr(
        registry, "all_sources", lambda: (FakeJobSource("adzuna", configured=False),)
    )

    response = await client.post(
        "/api/jobs/search",
        json={"query": "data", "profile_id": str(profile_id), "country": "de", "source": "adzuna"},
    )

    assert response.status_code == 409
    assert "not enabled" in response.json()["detail"]


async def test_search_with_unknown_source_returns_400(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    profile_id = await seed_profile_light("Owner")
    response = await client.post(
        "/api/jobs/search",
        json={
            "query": "data",
            "profile_id": str(profile_id),
            "country": "de",
            "source": "not_a_source",
        },
    )

    assert response.status_code == 400
    assert "unknown job source" in response.json()["detail"]


async def test_search_rejects_invalid_source_options(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    profile_id = await seed_profile_light("Owner")
    source = FakeJobSource("adzuna", configured=True, filters=[])
    monkeypatch.setattr(registry, "all_sources", lambda: (source,))

    response = await client.post(
        "/api/jobs/search",
        json={
            "query": "python developer",
            "profile_id": str(profile_id),
            "country": "de",
            "source": "adzuna",
            "source_queries": {
                "adzuna": {"options": {"bogus_filter": 1}},
            },
        },
    )

    assert response.status_code == 400
    assert "unknown filter 'bogus_filter' for source 'adzuna'" in response.json()["detail"]


async def test_search_accepts_declared_source_options(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.adapters.job_sources.base import SourceFilterDecl

    profile_id = await seed_profile_light("Owner")
    source = FakeJobSource(
        "adzuna",
        configured=True,
        filters=[SourceFilterDecl(key="title_only", label="Title-only", type="boolean")],
    )
    monkeypatch.setattr(registry, "all_sources", lambda: (source,))

    response = await client.post(
        "/api/jobs/search",
        json={
            "query": "python developer",
            "profile_id": str(profile_id),
            "country": "de",
            "source": "adzuna",
            "source_queries": {"adzuna": {"options": {"title_only": True}}},
        },
    )

    assert response.status_code == 202
    search_id = response.json()["search_id"]
    status = (
        await client.get(f"/api/jobs/searches/{search_id}", params={"profile_id": profile_id})
    ).json()
    assert status["query"]["source_queries"]["adzuna"]["options"] == {"title_only": True}


async def test_search_requires_effective_query_per_source(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    profile_id = await seed_profile_light("Owner")
    monkeypatch.setattr(registry, "all_sources", lambda: (FakeJobSource("adzuna"),))

    response = await client.post(
        "/api/jobs/search",
        json={"country": "de", "profile_id": str(profile_id), "source": "adzuna"},
    )

    assert response.status_code == 400
    assert "no search query" in response.json()["detail"]


async def test_search_accepts_per_source_specs_and_salary(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    profile_id = await seed_profile_light("Owner")
    source = FakeJobSource("adzuna", postings=[fake_posting("1")])
    monkeypatch.setattr(registry, "all_sources", lambda: (source,))

    response = await client.post(
        "/api/jobs/search",
        json={
            "country": "in",
            "profile_id": str(profile_id),
            "location": "Bangalore",
            "source": "adzuna",
            "source_queries": {
                "adzuna": {"title": "Senior Android Engineer", "skills": ["Kotlin"]}
            },
            "salary_min": 5000000,
        },
    )

    assert response.status_code == 202
    query = source.queries[0]
    assert query.term_plan is not None
    assert query.term_plan.what_phrase == "Senior Android Engineer"
    assert query.salary_min == 5000000
    assert query.location == "Bangalore"


async def test_search_rejects_inverted_salary_range(client: AsyncClient) -> None:
    response = await client.post(
        "/api/jobs/search",
        json={
            "query": "data",
            "country": "de",
            "salary_min": 100,
            "salary_max": 50,
            "source": "adzuna",
        },
    )

    assert response.status_code == 422


async def test_search_with_unacknowledged_scraper_returns_409(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    profile_id = await seed_profile_light("Owner")
    scraper = FakeJobSource("apify_linkedin", disclosure_required=True)
    monkeypatch.setattr(registry, "all_sources", lambda: (scraper,))

    response = await client.post(
        "/api/jobs/search",
        json={
            "query": "data",
            "profile_id": str(profile_id),
            "country": "de",
            "source": "apify_linkedin",
        },
    )

    assert response.status_code == 409
    assert "not enabled" in response.json()["detail"]


async def test_search_validates_country(client: AsyncClient) -> None:
    response = await client.post(
        "/api/jobs/search",
        json={"query": "data", "country": "germany", "source": "adzuna"},
    )

    assert response.status_code == 422


async def test_search_normalizes_country(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    profile_id = await seed_profile_light("Owner")
    source = FakeJobSource("adzuna", postings=[])
    monkeypatch.setattr(registry, "all_sources", lambda: (source,))

    response = await client.post(
        "/api/jobs/search",
        json={"query": "data", "profile_id": str(profile_id), "country": "DE", "source": "adzuna"},
    )

    assert response.status_code == 202
    assert source.queries[0].country == "de"


async def test_search_status_requires_profile_id(client: AsyncClient) -> None:
    profile_id = await seed_profile_light("Owner")
    start = (
        await client.post(
            "/api/jobs/search",
            json={
                "query": "data",
                "profile_id": str(profile_id),
                "country": "de",
                "source": "adzuna",
            },
        )
    ).json()

    missing = await client.get(f"/api/jobs/searches/{start['search_id']}")
    assert missing.status_code == 422

    wrong = await client.get(
        f"/api/jobs/searches/{start['search_id']}", params={"profile_id": str(uuid.uuid4())}
    )
    assert wrong.status_code == 404
    assert "job search not found" in wrong.json()["detail"]


async def test_search_postings_endpoint(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    profile_id = await seed_profile_light("Owner")
    source = FakeJobSource(
        "adzuna",
        postings=[
            fake_posting("1", title="Engineer A", salary_min=100.0, currency="EUR"),
            fake_posting("2", title="Engineer B"),
        ],
    )
    monkeypatch.setattr(registry, "all_sources", lambda: (source,))

    start = (
        await client.post(
            "/api/jobs/search",
            json={
                "query": "data",
                "profile_id": str(profile_id),
                "country": "de",
                "source": "adzuna",
            },
        )
    ).json()

    postings = (
        await client.get(
            f"/api/jobs/searches/{start['search_id']}/postings", params={"profile_id": profile_id}
        )
    ).json()
    assert [posting["title"] for posting in postings] == ["Engineer A", "Engineer B"]
    assert postings[0]["source"] == "adzuna"
    assert postings[0]["salary_min"] == 100.0
    assert postings[0]["currency"] == "EUR"

    missing = await client.get(
        f"/api/jobs/searches/{uuid.uuid4()}/postings", params={"profile_id": profile_id}
    )
    assert missing.status_code == 404

    cross_profile = await client.get(
        f"/api/jobs/searches/{start['search_id']}/postings",
        params={"profile_id": str(uuid.uuid4())},
    )
    assert cross_profile.status_code == 404


async def test_list_searches_returns_recent_runs_for_profile(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.models import JobSearch

    profile_id = await seed_profile_light("Owner")

    async with session_factory() as session:
        session.add_all(
            [
                JobSearch(
                    profile_id=profile_id,
                    status="succeeded",
                    query={},
                    created_at=datetime.now(UTC) - timedelta(minutes=5),
                ),
                JobSearch(profile_id=profile_id, status="pending", query={}),
            ]
        )
        await session.commit()

    response = await client.get("/api/jobs/searches", params={"profile_id": profile_id})
    assert response.status_code == 200
    runs = response.json()
    assert [run["status"] for run in runs] == ["pending", "succeeded"]
    assert "query" not in runs[0]

    unknown = await client.get("/api/jobs/searches", params={"profile_id": str(uuid.uuid4())})
    assert unknown.status_code == 404

    missing = await client.get("/api/jobs/searches")
    assert missing.status_code == 422


async def test_list_sources_includes_state(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    adzuna = FakeJobSource("adzuna")
    adzuna.is_official_api = True
    scraper = FakeJobSource("apify_linkedin", disclosure_required=True)
    monkeypatch.setattr(registry, "all_sources", lambda: (adzuna, scraper))

    response = await client.get("/api/sources")

    assert response.status_code == 200
    sources = {source["name"]: source for source in response.json()}
    assert sources["adzuna"]["is_official_api"] is True
    assert sources["adzuna"]["disclosure_required"] is False
    assert sources["adzuna"]["is_configured"] is True
    assert sources["adzuna"]["enabled"] is True
    assert sources["apify_linkedin"]["disclosure_required"] is True
    assert sources["apify_linkedin"]["enabled"] is False
    assert sources["apify_linkedin"]["filters"] == []


async def test_list_sources_includes_filter_declarations(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.adapters.job_sources.base import SourceFilterDecl

    source = FakeJobSource(
        "adzuna",
        configured=True,
        filters=[SourceFilterDecl(key="title_only", label="Title-only", type="boolean")],
    )
    monkeypatch.setattr(registry, "all_sources", lambda: (source,))

    response = await client.get("/api/sources")

    assert response.status_code == 200
    [payload] = response.json()
    assert payload["supports_exclusions"] is False
    assert payload["filters"] == [
        {
            "key": "title_only",
            "label": "Title-only",
            "type": "boolean",
            "options": None,
            "required": False,
            "placeholder": None,
            "help_text": None,
        }
    ]


async def test_enable_requires_acknowledgment(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    scraper = FakeJobSource("apify_linkedin", disclosure_required=True)
    monkeypatch.setattr(registry, "all_sources", lambda: (scraper,))

    denied = await client.post(
        "/api/sources/apify_linkedin/enable", json={"acknowledged_disclosure": False}
    )
    assert denied.status_code == 409

    allowed = await client.post(
        "/api/sources/apify_linkedin/enable", json={"acknowledged_disclosure": True}
    )
    assert allowed.status_code == 200
    assert allowed.json()["enabled"] is True

    again = await client.post(
        "/api/sources/apify_linkedin/enable", json={"acknowledged_disclosure": True}
    )
    assert again.status_code == 200

    listing = (await client.get("/api/sources")).json()
    assert next(s for s in listing if s["name"] == "apify_linkedin")["enabled"] is True


async def test_enable_official_api_source_is_noop(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    adzuna = FakeJobSource("adzuna")
    monkeypatch.setattr(registry, "all_sources", lambda: (adzuna,))

    response = await client.post(
        "/api/sources/adzuna/enable", json={"acknowledged_disclosure": False}
    )

    assert response.status_code == 200
    assert response.json()["enabled"] is True


async def test_enable_unknown_source_returns_404(client: AsyncClient) -> None:
    response = await client.post(
        "/api/sources/not_a_source/enable", json={"acknowledged_disclosure": True}
    )

    assert response.status_code == 404
