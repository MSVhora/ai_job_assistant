import uuid
from typing import Any

import pytest
from fakes import seed_profile_light
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.db import session_factory
from app.main import app
from app.models import ProfileRevision

pytestmark = pytest.mark.usefixtures("clean_tables")


@pytest.fixture
async def client() -> AsyncClient:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as c:
        yield c


def path(profile_id: Any) -> str:
    return f"/api/profiles/{profile_id}/experience"


def companies(response: Any) -> list[str]:
    return [job["company"] for job in response.json()["structured_profile"]["experience"]]


async def test_an_employer_missing_from_the_resume_is_added_as_a_role_with_a_revision(
    client: AsyncClient,
) -> None:
    profile_id = await seed_profile_light()

    response = await client.post(
        path(profile_id),
        json={"company": "  Zeta Labs  ", "title": "Contractor", "start_date": "Jan 2024"},
    )

    assert response.status_code == 201
    added = next(
        job
        for job in response.json()["structured_profile"]["experience"]
        if job["company"] == "Zeta Labs"
    )
    assert (added["title"], added["start_date"], added["bullets"]) == (
        "Contractor",
        "Jan 2024",
        [],
    )
    options = (await client.get("/api/evidence/employers")).json()
    assert "Zeta Labs" in [o["company"] for o in options]
    async with session_factory() as session:
        revisions = (await session.execute(select(ProfileRevision))).scalars().all()
    assert [r.source.value for r in revisions] == ["manual_edit"]
    assert "experience" in revisions[0].diff


async def test_roles_are_kept_newest_first(client: AsyncClient) -> None:
    profile_id = await seed_profile_light()

    await client.post(path(profile_id), json={"company": "Old Co", "start_date": "Jan 2015"})
    await client.post(path(profile_id), json={"company": "Newer Co", "start_date": "Jan 2024"})
    response = await client.post(path(profile_id), json={"company": "Undated Co"})

    assert companies(response) == ["Newer Co", "Acme Corp", "Old Co", "Undated Co"]


async def test_a_second_stint_at_an_existing_company_joins_its_employer(
    client: AsyncClient,
) -> None:
    profile_id = await seed_profile_light()

    response = await client.post(
        path(profile_id),
        json={"company": "ACME Corp.", "start_date": "Jan 2016", "end_date": "Dec 2017"},
    )

    assert response.status_code == 201
    options = (await client.get("/api/evidence/employers")).json()
    acme = [o for o in options if o["kind"] == "experience"]
    assert len(acme) == 1
    assert acme[0]["entries"] == 2
    assert acme[0]["label"].endswith("2 roles")


async def test_the_same_role_twice_is_a_409(client: AsyncClient) -> None:
    profile_id = await seed_profile_light()
    body = {"company": "Zeta Labs", "start_date": "Jan 2024", "end_date": "Jun 2024"}
    await client.post(path(profile_id), json=body)

    again = await client.post(path(profile_id), json={**body, "company": "ZETA LABS Ltd."})

    assert again.status_code == 409
    assert "already in the profile" in again.json()["detail"]
    current = await client.get(f"/api/profiles/{profile_id}")
    assert companies(current).count("Zeta Labs") == 1


async def test_blank_optional_fields_are_stored_as_missing(client: AsyncClient) -> None:
    profile_id = await seed_profile_light()

    response = await client.post(
        path(profile_id), json={"company": "Zeta Labs", "title": "  ", "location": ""}
    )

    added = next(
        job
        for job in response.json()["structured_profile"]["experience"]
        if job["company"] == "Zeta Labs"
    )
    assert (added["title"], added["location"], added["start_date"]) == (None, None, None)


@pytest.mark.parametrize("body", [{}, {"company": ""}, {"company": "   "}, {"company": "x" * 201}])
async def test_a_role_needs_a_company(client: AsyncClient, body: dict[str, Any]) -> None:
    profile_id = await seed_profile_light()

    assert (await client.post(path(profile_id), json=body)).status_code == 422


async def test_an_unknown_profile_is_a_404(client: AsyncClient) -> None:
    response = await client.post(path(uuid.uuid4()), json={"company": "Zeta Labs"})

    assert response.status_code == 404
