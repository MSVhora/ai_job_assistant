import io
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from docx import Document
from fakes import seed_profile_light
from httpx import ASGITransport, AsyncClient

from app.core.db import session_factory
from app.main import app
from app.models import JobPosting, JobSearch, JobSearchStatus, SearchPosting

pytestmark = pytest.mark.usefixtures("clean_tables")

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
TOTAL = "x-total-count"


@pytest.fixture
async def client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        yield async_client


async def upload_docx(client: AsyncClient, name: str) -> None:
    buffer = io.BytesIO()
    document = Document()
    document.add_paragraph(name)
    document.save(buffer)
    response = await client.post(
        "/api/resumes", files={"file": (f"{name}.docx", io.BytesIO(buffer.getvalue()), DOCX_MIME)}
    )
    assert response.status_code == 201


async def seed_searches(profile_id: uuid.UUID, count: int) -> None:
    now = datetime.now(UTC)
    async with session_factory() as session:
        for index in range(count):
            session.add(
                JobSearch(
                    profile_id=profile_id,
                    source=f"source{index}",
                    status=JobSearchStatus.succeeded,
                    query={"query": "data"},
                    created_at=now - timedelta(minutes=index),
                )
            )
        await session.commit()


async def seed_postings(profile_id: uuid.UUID, count: int) -> uuid.UUID:
    async with session_factory() as session:
        search = JobSearch(
            profile_id=profile_id,
            source="adzuna",
            status=JobSearchStatus.succeeded,
            query={"query": "data"},
        )
        session.add(search)
        await session.flush()
        for index in range(count):
            posting = JobPosting(
                source="adzuna",
                external_id=f"ext-{index}",
                title=f"Posting {index:03d}",
                raw_payload={},
                posted_at=datetime.now(UTC) - timedelta(days=index),
            )
            session.add(posting)
            await session.flush()
            session.add(SearchPosting(search_id=search.id, posting_id=posting.id))
        await session.commit()
        return search.id


async def test_profiles_are_paged_with_total_header(client: AsyncClient) -> None:
    for name in ("A", "B", "C"):
        await seed_profile_light(name)

    everything = await client.get("/api/profiles")
    page = await client.get("/api/profiles", params={"limit": 2, "offset": 1})

    assert everything.headers[TOTAL] == "3"
    assert [item["name"] for item in page.json()] == [
        item["name"] for item in everything.json()[1:3]
    ]
    assert page.headers[TOTAL] == "3"


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 201}, {"offset": -1}])
async def test_profiles_reject_out_of_range_paging(client: AsyncClient, params: dict) -> None:
    response = await client.get("/api/profiles", params=params)

    assert response.status_code == 422
    assert isinstance(response.json()["detail"], str)


async def test_resumes_are_paged_with_total_header(client: AsyncClient) -> None:
    for name in ("one", "two", "three"):
        await upload_docx(client, name)

    page = await client.get("/api/resumes", params={"limit": 2})
    rest = await client.get("/api/resumes", params={"limit": 2, "offset": 2})
    too_many = await client.get("/api/resumes", params={"limit": 201})

    assert len(page.json()) == 2
    assert len(rest.json()) == 1
    assert page.headers[TOTAL] == rest.headers[TOTAL] == "3"
    assert too_many.status_code == 422


async def test_searches_keep_their_default_of_twenty_and_page(client: AsyncClient) -> None:
    profile_id = await seed_profile_light("Owner")
    await seed_searches(profile_id, 25)

    default = await client.get("/api/jobs/searches", params={"profile_id": str(profile_id)})
    page = await client.get(
        "/api/jobs/searches", params={"profile_id": str(profile_id), "limit": 10, "offset": 20}
    )
    over = await client.get(
        "/api/jobs/searches", params={"profile_id": str(profile_id), "limit": 201}
    )

    assert len(default.json()) == 20
    assert default.headers[TOTAL] == "25"
    assert len(page.json()) == 5
    assert over.status_code == 422


async def test_search_postings_are_paged_and_default_covers_a_full_run(
    client: AsyncClient,
) -> None:
    profile_id = await seed_profile_light("Owner")
    search_id = await seed_postings(profile_id, 12)
    url = f"/api/jobs/searches/{search_id}/postings"
    params = {"profile_id": str(profile_id)}

    everything = await client.get(url, params=params)
    page = await client.get(url, params={**params, "limit": 5, "offset": 10})
    over = await client.get(url, params={**params, "limit": 1001})

    assert len(everything.json()) == 12
    assert everything.headers[TOTAL] == "12"
    assert [item["title"] for item in page.json()] == [
        item["title"] for item in everything.json()[10:12]
    ]
    assert over.status_code == 422
