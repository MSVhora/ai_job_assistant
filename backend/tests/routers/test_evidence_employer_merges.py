from typing import Any

import pytest
from fakes import seed_employers
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.db import session_factory
from app.main import app
from app.models import Candidate

pytestmark = pytest.mark.usefixtures("clean_tables")

MERGES = "/api/evidence/employers/merges"
EMPLOYERS = "/api/evidence/employers"


@pytest.fixture
async def client() -> AsyncClient:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as c:
        yield c


def names(options: list[dict[str, Any]]) -> list[str]:
    return [option["company"] for option in options if option["kind"] == "experience"]


async def test_merging_two_companies_makes_one_employer_with_both_names(
    client: AsyncClient,
) -> None:
    await seed_employers("Samsung", "Samsung Research Institute", "Acme Corp")

    response = await client.post(
        MERGES, json={"canonical": "Samsung", "members": ["Samsung Research Institute"]}
    )

    assert response.status_code == 200
    options = response.json()
    assert sorted(names(options)) == ["Acme Corp", "Samsung"]
    samsung = next(o for o in options if o["company"] == "Samsung")
    assert samsung["entries"] == 2
    assert samsung["merged_from"] == ["Samsung Research Institute"]
    assert set(samsung["aliases"]) == {"Samsung", "Samsung Research Institute"}
    assert names((await client.get(EMPLOYERS)).json()) == names(options)


async def test_the_canonical_name_may_be_either_company(client: AsyncClient) -> None:
    await seed_employers("Samsung", "Samsung Research Institute")

    options = (
        await client.post(
            MERGES,
            json={"canonical": "Samsung Research Institute", "members": ["Samsung"]},
        )
    ).json()

    assert names(options) == ["Samsung Research Institute"]


async def test_merging_into_an_existing_merge_extends_it(client: AsyncClient) -> None:
    await seed_employers("Samsung", "Samsung Research Institute", "Samsung Electronics")
    await client.post(
        MERGES, json={"canonical": "Samsung", "members": ["Samsung Research Institute"]}
    )

    options = (
        await client.post(MERGES, json={"canonical": "Samsung", "members": ["Samsung Electronics"]})
    ).json()

    (samsung,) = [o for o in options if o["kind"] == "experience"]
    assert samsung["entries"] == 3
    assert set(samsung["merged_from"]) == {"Samsung Research Institute", "Samsung Electronics"}


@pytest.mark.parametrize(
    "payload",
    [
        {"canonical": "Samsung", "members": ["Nowhere Inc"]},
        {"canonical": "Nowhere Inc", "members": ["Samsung"]},
        {"canonical": "Samsung", "members": ["Samsung"]},
        {"canonical": "Samsung", "members": ["SAMSUNG Ltd."]},
    ],
)
async def test_a_merge_needs_two_different_companies_from_the_profile(
    client: AsyncClient, payload: dict[str, Any]
) -> None:
    await seed_employers("Samsung", "Acme Corp")

    response = await client.post(MERGES, json=payload)

    assert response.status_code == 400
    assert "two or more different companies" in response.json()["detail"]


async def test_a_malformed_merge_request_is_rejected(client: AsyncClient) -> None:
    assert (await client.post(MERGES, json={"canonical": "", "members": []})).status_code == 422
    assert (await client.post(MERGES, json={"canonical": "A"})).status_code == 422


async def test_unmerging_restores_the_separate_employers(client: AsyncClient) -> None:
    await seed_employers("Samsung", "Samsung Research Institute")
    await client.post(
        MERGES, json={"canonical": "Samsung", "members": ["Samsung Research Institute"]}
    )

    options = (await client.delete(f"{MERGES}/samsung")).json()

    assert sorted(names(options)) == ["Samsung", "Samsung Research Institute"]
    async with session_factory() as session:
        candidate = (await session.execute(select(Candidate))).scalars().one()
        assert candidate.employer_merges == {"groups": []}


async def test_unmerging_something_that_is_not_merged_is_a_404(client: AsyncClient) -> None:
    await seed_employers("Samsung")

    assert (await client.delete(f"{MERGES}/samsung")).status_code == 404
