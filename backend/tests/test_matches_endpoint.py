import json
import math
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fakes import (
    VALID_PROFILE,
    fake_vector,
    install_acompletion,
    llm_response,
)
from httpx import ASGITransport, AsyncClient

from app.core.db import session_factory
from app.main import app
from app.models import JobPosting, Profile
from app.schemas.profile import ProfileCreate, StructuredProfile
from app.services import matching
from app.services.profile_service import create_profile

pytestmark = pytest.mark.usefixtures("clean_tables")

DESCRIPTION = "Analyse data with SQL and Python. " * 20
RERANK_JSON = json.dumps({"items": []})


def structured_profile() -> StructuredProfile:
    return StructuredProfile.model_validate(VALID_PROFILE)


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    return dot / (norm_a * norm_b)


@pytest.fixture
async def client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        yield async_client


async def seed_matched_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[uuid.UUID, list[JobPosting]]:
    async with session_factory() as session:
        profile = await create_profile(
            session, ProfileCreate(name="Seeker", structured_profile=structured_profile())
        )
        await session.commit()
        profile_id = profile.profile_id

    async with session_factory() as session:
        stored = await session.get(Profile, profile_id)
        assert stored is not None
        await session.refresh(stored)
        assert stored.embedding is not None
        profile_embedding = stored.embedding

        now = datetime.now(UTC)
        specs = [
            {
                "title": "Berlin Analyst",
                "location": "Berlin",
                "remote_type": "remote",
                "job_type": "full_time",
                "posted_at": now - timedelta(days=2),
                "embedding": fake_vector("match-a"),
            },
            {
                "title": "Amsterdam Contract",
                "location": "Amsterdam",
                "remote_type": "hybrid",
                "job_type": "contract",
                "posted_at": now - timedelta(days=30),
                "embedding": fake_vector("match-b"),
            },
            {
                "title": "Undated Berlin",
                "location": "Berlin",
                "posted_at": None,
                "embedding": fake_vector("match-c"),
            },
        ]
        postings: list[JobPosting] = []
        for index, spec in enumerate(specs):
            posting = JobPosting(
                source="adzuna",
                external_id=f"ext-{index}",
                raw_payload={"id": f"ext-{index}"},
                description=DESCRIPTION,
                **spec,
            )
            session.add(posting)
            postings.append(posting)
        await session.commit()
        for posting in postings:
            await session.refresh(posting)

        await matching.refresh_matches_for_profile(session, profile_id)
        await session.commit()
        assert profile_embedding is not None
    return profile_id, postings


def vector_scores(
    profile_embedding: list[float], postings: list[JobPosting]
) -> dict[uuid.UUID, float]:
    return {posting.id: cosine(profile_embedding, posting.embedding) for posting in postings}


async def get_matches(client: AsyncClient, profile_id: uuid.UUID, **params: Any) -> Any:
    query = {"profile_id": str(profile_id), **{k: str(v) for k, v in params.items()}}
    return await client.get("/api/matches", params=query)


async def seed_subscored_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[uuid.UUID, list[JobPosting]]:
    """Profile + two postings with identical embeddings but opposite LLM sub-scores.

    Equal vector scores make the custom-priority ordering depend entirely on the
    re-rank sub-scores: "Role Heavy" (role 9 / company 1) vs "Company Heavy"
    (role 1 / company 9).
    """
    async with session_factory() as session:
        profile = await create_profile(
            session, ProfileCreate(name="Seeker", structured_profile=structured_profile())
        )
        await session.commit()
        profile_id = profile.profile_id

    async with session_factory() as session:
        now = datetime.now(UTC)
        postings = []
        for index, (title, posted_at) in enumerate(
            [("Role Heavy", now - timedelta(days=1)), ("Company Heavy", now - timedelta(days=2))]
        ):
            posting = JobPosting(
                source="adzuna",
                external_id=f"ext-{index}",
                title=title,
                location="Berlin",
                posted_at=posted_at,
                description=DESCRIPTION,
                embedding=fake_vector("twin"),
                raw_payload={"id": f"ext-{index}"},
            )
            session.add(posting)
            postings.append(posting)
        await session.commit()
        for posting in postings:
            await session.refresh(posting)

        items = [
            {
                "posting_id": str(postings[0].id),
                "role_fit": 9.0,
                "company_fit": 1.0,
                "rationale": "Role matches skills.",
            },
            {
                "posting_id": str(postings[1].id),
                "role_fit": 1.0,
                "company_fit": 9.0,
                "rationale": "Employer matches trajectory.",
            },
        ]
        install_acompletion(monkeypatch, lambda **kw: llm_response(json.dumps({"items": items})))
        await matching.refresh_matches_for_profile(session, profile_id)
        await session.commit()
    return profile_id, postings


async def test_list_matches_ranks_and_embeds_posting(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    profile_id, postings = await seed_matched_profile(monkeypatch)
    async with session_factory() as session:
        stored = await session.get(Profile, profile_id)
        assert stored is not None
        await session.refresh(stored)
        profile_embedding = stored.embedding
        assert profile_embedding is not None
    scores = vector_scores(profile_embedding, postings)

    response = await get_matches(client, profile_id)

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 3
    finals = [row["final_score"] for row in body]
    assert finals == sorted(finals, reverse=True)
    by_posting = {row["job_posting"]["id"]: row for row in body}
    for posting in postings:
        row = by_posting[str(posting.id)]
        assert row["vector_score"] == pytest.approx(scores[posting.id], abs=1e-6)
        assert row["final_score"] == pytest.approx(row["vector_score"], abs=1e-6)
        assert row["job_posting"]["title"] == posting.title
        assert row["job_posting"]["source"] == "adzuna"
        assert row["created_at"] is not None


async def test_unknown_profile_returns_404(client: AsyncClient) -> None:
    response = await get_matches(client, uuid.uuid4())
    assert response.status_code == 404


async def test_unembedded_profile_returns_409(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    profile_id, _ = await seed_matched_profile(monkeypatch)
    async with session_factory() as session:
        stored = await session.get(Profile, profile_id)
        assert stored is not None
        stored.embedding = None
        await session.commit()

    response = await get_matches(client, profile_id)

    assert response.status_code == 409
    assert "embedding" in response.json()["detail"]


async def test_location_filter_substring(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    profile_id, _ = await seed_matched_profile(monkeypatch)

    response = await get_matches(client, profile_id, location="Berlin")

    body = response.json()
    assert len(body) == 2
    assert all(row["job_posting"]["location"] == "Berlin" for row in body)


async def test_remote_and_job_type_filters(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    profile_id, _ = await seed_matched_profile(monkeypatch)

    remote = await get_matches(client, profile_id, remote_type="remote")
    assert [row["job_posting"]["title"] for row in remote.json()] == ["Berlin Analyst"]

    job_type = await get_matches(client, profile_id, job_type="contract")
    assert [row["job_posting"]["title"] for row in job_type.json()] == ["Amsterdam Contract"]


async def test_posted_within_excludes_null_posted_at(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    profile_id, _ = await seed_matched_profile(monkeypatch)

    response = await get_matches(client, profile_id, posted_within_days=7)

    assert [row["job_posting"]["title"] for row in response.json()] == ["Berlin Analyst"]


async def test_sort_posted_at_nulls_last(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    profile_id, _ = await seed_matched_profile(monkeypatch)

    response = await get_matches(client, profile_id, sort="posted_at")

    titles = [row["job_posting"]["title"] for row in response.json()]
    assert titles == ["Berlin Analyst", "Amsterdam Contract", "Undated Berlin"]


async def test_sort_vector_score_orders_by_vector(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    profile_id, postings = await seed_matched_profile(monkeypatch)
    async with session_factory() as session:
        stored = await session.get(Profile, profile_id)
        assert stored is not None
        await session.refresh(stored)
        profile_embedding = stored.embedding
        assert profile_embedding is not None
    scores = vector_scores(profile_embedding, postings)
    expected_ids = [str(p.id) for p in sorted(postings, key=lambda p: -scores[p.id])]

    response = await get_matches(client, profile_id, sort="vector_score")

    assert [row["job_posting"]["id"] for row in response.json()] == expected_ids


async def test_limit_and_offset_page(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    profile_id, postings = await seed_matched_profile(monkeypatch)
    async with session_factory() as session:
        stored = await session.get(Profile, profile_id)
        assert stored is not None
        await session.refresh(stored)
        profile_embedding = stored.embedding
        assert profile_embedding is not None
    scores = vector_scores(profile_embedding, postings)
    ranked = sorted(postings, key=lambda p: -scores[p.id])

    page = await get_matches(client, profile_id, limit=1, offset=1)

    assert page.status_code == 200
    assert [row["job_posting"]["id"] for row in page.json()] == [str(ranked[1].id)]


async def test_invalid_params_return_422(client: AsyncClient) -> None:
    too_low = await get_matches(client, uuid.uuid4(), limit=0)
    assert too_low.status_code == 422

    bad_sort = await get_matches(client, uuid.uuid4(), sort="bogus")
    assert bad_sort.status_code == 422

    missing_profile = await client.get("/api/matches")
    assert missing_profile.status_code == 422


async def test_custom_priority_reorders_by_subscores(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    profile_id, _ = await seed_subscored_profile(monkeypatch)

    role_first = await get_matches(client, profile_id, priority=1.0)
    company_first = await get_matches(client, profile_id, priority=0.0)

    assert [row["job_posting"]["title"] for row in role_first.json()] == [
        "Role Heavy",
        "Company Heavy",
    ]
    assert [row["job_posting"]["title"] for row in company_first.json()] == [
        "Company Heavy",
        "Role Heavy",
    ]


async def test_custom_priority_response_scores_match_order_and_math(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    profile_id, _ = await seed_subscored_profile(monkeypatch)

    body = (await get_matches(client, profile_id, priority=0.0)).json()

    finals = [row["final_score"] for row in body]
    assert finals == sorted(finals, reverse=True)
    vector_score = body[0]["vector_score"]
    assert body[0]["job_posting"]["title"] == "Company Heavy"
    assert body[0]["final_score"] == pytest.approx(0.4 * vector_score + 0.6 * 0.9, abs=1e-6)
    assert body[1]["final_score"] == pytest.approx(0.4 * vector_score + 0.6 * 0.1, abs=1e-6)
    for row in body:
        assert row["role_fit"] is not None
        assert row["rationale"] is not None


async def test_default_priority_matches_no_param_response(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    profile_id, _ = await seed_subscored_profile(monkeypatch)

    without = (await get_matches(client, profile_id)).json()
    explicit_default = (await get_matches(client, profile_id, priority=0.6666666667)).json()

    assert [row["job_posting"]["id"] for row in without] == [
        row["job_posting"]["id"] for row in explicit_default
    ]
    assert [row["final_score"] for row in without] == [
        row["final_score"] for row in explicit_default
    ]


async def test_stored_preference_used_when_param_absent(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    profile_id, _ = await seed_subscored_profile(monkeypatch)
    stored = await client.patch(f"/api/profiles/{profile_id}/preferences", json={"priority": 0.0})
    assert stored.status_code == 200

    ordered = await get_matches(client, profile_id)
    overridden = await get_matches(client, profile_id, priority=1.0)

    assert [row["job_posting"]["title"] for row in ordered.json()] == [
        "Company Heavy",
        "Role Heavy",
    ]
    assert [row["job_posting"]["title"] for row in overridden.json()] == [
        "Role Heavy",
        "Company Heavy",
    ]


async def test_sort_posted_at_ignores_priority(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    profile_id, _ = await seed_subscored_profile(monkeypatch)

    response = await get_matches(client, profile_id, sort="posted_at", priority=0.0)

    assert [row["job_posting"]["title"] for row in response.json()] == [
        "Role Heavy",
        "Company Heavy",
    ]


async def test_out_of_range_priority_returns_422(client: AsyncClient) -> None:
    too_high = await get_matches(client, uuid.uuid4(), priority=1.5)
    too_low = await get_matches(client, uuid.uuid4(), priority=-0.1)

    assert too_high.status_code == 422
    assert too_low.status_code == 422
