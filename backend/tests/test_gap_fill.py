import json
import uuid
from typing import Any

import pytest
from fakes import VALID_PROFILE, install_acompletion, llm_response
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import session_factory
from app.main import app
from app.models import Candidate, Profile, ProfileRevision, RevisionSource
from app.services.gap_fill import _NOTHING_MISSING_REPLY

pytestmark = pytest.mark.usefixtures("clean_tables")

FULL_PREFS: dict[str, Any] = {
    "target_title": "Data Analyst",
    "target_location": "Berlin",
    "remote_preference": "hybrid",
    "salary_min": 60000.0,
    "salary_max": 90000.0,
    "currency": "EUR",
    "seniority": "senior",
    "work_authorization": "EU citizen",
}

MISSING_KEYS = [
    "preferences.target_location",
    "preferences.remote_preference",
    "preferences.salary_band",
    "preferences.seniority",
    "preferences.work_authorization",
]


@pytest.fixture(autouse=True)
def gemini_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
async def client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        yield async_client


def turn(answers: dict[str, Any], reply: str = "Got it.") -> str:
    return json.dumps({"answers": answers, "reply": reply})


async def create_profile(name: str, structured_profile: dict[str, Any]) -> str:
    async with session_factory() as session:
        result = await session.execute(select(Candidate).limit(1))
        candidate = result.scalars().first()
        if candidate is None:
            candidate = Candidate()
            session.add(candidate)
            await session.flush()
        profile = Profile(
            candidate_id=candidate.id, name=name, structured_profile=structured_profile
        )
        session.add(profile)
        await session.flush()
        await session.commit()
        return str(profile.id)


async def fetch_revisions(profile_id: str) -> list[ProfileRevision]:
    async with session_factory() as session:
        result = await session.execute(
            select(ProfileRevision)
            .where(ProfileRevision.profile_id == uuid.UUID(profile_id))
            .order_by(ProfileRevision.created_at)
        )
        return list(result.scalars().all())


async def test_no_missing_fields_short_circuits_without_llm(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    profile_id = await create_profile("Full", {**VALID_PROFILE, "preferences": FULL_PREFS})
    calls = install_acompletion(
        monkeypatch, lambda **kw: llm_response(turn({}, "should not be called"))
    )

    response = await client.post(f"/api/profiles/{profile_id}/gap-fill", json={"messages": []})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "complete"
    assert body["reply"] == _NOTHING_MISSING_REPLY
    assert body["missing_fields"] == []
    assert body["applied_fields"] == []
    assert body["revision"] is None
    assert body["structured_profile"]["preferences"]["seniority"] == "senior"
    assert calls == []


async def test_opening_turn_asks_without_saving(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    profile_id = await create_profile("Bare", VALID_PROFILE)
    install_acompletion(
        monkeypatch, lambda **kw: llm_response(turn({}, "Where would you like to work next?"))
    )

    response = await client.post(f"/api/profiles/{profile_id}/gap-fill", json={"messages": []})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "in_progress"
    assert body["reply"] == "Where would you like to work next?"
    assert [field["key"] for field in body["missing_fields"]] == MISSING_KEYS
    assert body["applied_fields"] == []
    assert body["revision"] is None
    assert await fetch_revisions(profile_id) == []


async def test_answers_merge_and_write_gap_fill_revision(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    profile_id = await create_profile("Bare", VALID_PROFILE)
    install_acompletion(
        monkeypatch,
        lambda **kw: llm_response(
            turn(
                {
                    "target_location": "Amsterdam",
                    "remote_preference": "remote",
                    "salary_min": 70000,
                    "salary_max": 90000,
                    "currency": "eur",
                    "seniority": "senior",
                    "work_authorization": "EU citizen",
                },
                "That covers everything - you are all set!",
            )
        ),
    )
    messages = [
        {"role": "assistant", "content": "Tell me about your preferences?"},
        {"role": "user", "content": "Amsterdam, remote, senior, 70-90k EUR, EU citizen"},
    ]

    response = await client.post(
        f"/api/profiles/{profile_id}/gap-fill", json={"messages": messages}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "complete"
    assert body["missing_fields"] == []
    assert body["reply"] == "That covers everything - you are all set!"
    assert [field["field"] for field in body["applied_fields"]] == [
        "preferences.target_location",
        "preferences.remote_preference",
        "preferences.salary_min",
        "preferences.salary_max",
        "preferences.currency",
        "preferences.seniority",
        "preferences.work_authorization",
    ]
    assert body["structured_profile"]["preferences"]["currency"] == "EUR"
    assert body["revision"]["source"] == "gap_fill"

    revisions = await fetch_revisions(profile_id)
    assert len(revisions) == 1
    assert revisions[0].source == RevisionSource.gap_fill
    assert revisions[0].diff["preferences.target_location"] == {"old": None, "new": "Amsterdam"}
    assert revisions[0].diff["preferences.salary_min"] == {"old": None, "new": 70000.0}


async def test_inverted_salary_band_dropped(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    profile_id = await create_profile("Bare", VALID_PROFILE)
    install_acompletion(
        monkeypatch,
        lambda **kw: llm_response(
            turn(
                {
                    "target_location": "Berlin",
                    "salary_min": 100000,
                    "salary_max": 90000,
                },
                "Hmm, let me re-check that range.",
            )
        ),
    )

    response = await client.post(
        f"/api/profiles/{profile_id}/gap-fill",
        json={"messages": [{"role": "user", "content": "100k max 90k, Berlin"}]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "in_progress"
    assert [field["field"] for field in body["applied_fields"]] == ["preferences.target_location"]
    assert "preferences.salary_band" in [field["key"] for field in body["missing_fields"]]
    revisions = await fetch_revisions(profile_id)
    assert set(revisions[0].diff) == {"preferences.target_location"}


async def test_answers_for_present_fields_are_ignored(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    profile_id = await create_profile("Bare", VALID_PROFILE)
    install_acompletion(
        monkeypatch,
        lambda **kw: llm_response(
            turn({"contact_location": "Paris", "target_location": "Utrecht"})
        ),
    )
    response = await client.post(
        f"/api/profiles/{profile_id}/gap-fill",
        json={"messages": [{"role": "user", "content": "I moved to Paris, want Utrecht"}]},
    )

    assert response.status_code == 200
    body = response.json()
    assert [field["field"] for field in body["applied_fields"]] == ["preferences.target_location"]
    assert body["structured_profile"]["contact"]["location"] == "Berlin"
    assert body["structured_profile"]["preferences"]["target_location"] == "Utrecht"


async def test_unknown_profile_returns_404(client: AsyncClient) -> None:
    response = await client.post(f"/api/profiles/{uuid.uuid4()}/gap-fill", json={"messages": []})

    assert response.status_code == 404


async def test_llm_not_configured_returns_503(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    profile_id = await create_profile("Bare", VALID_PROFILE)
    monkeypatch.setattr("app.services.gap_fill.is_llm_configured", lambda: False)

    response = await client.post(f"/api/profiles/{profile_id}/gap-fill", json={"messages": []})

    assert response.status_code == 503


async def test_llm_failure_returns_502(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    profile_id = await create_profile("Bare", VALID_PROFILE)
    install_acompletion(monkeypatch, lambda **kw: RuntimeError("boom"))

    response = await client.post(f"/api/profiles/{profile_id}/gap-fill", json={"messages": []})

    assert response.status_code == 502
    assert response.json()["detail"] == "llm generation failed: provider rejected the request"


async def test_message_validation_returns_422(client: AsyncClient) -> None:
    profile_id = await create_profile("Bare", VALID_PROFILE)

    too_many = {"messages": [{"role": "user", "content": "hi"}] * 31}
    assert (
        await client.post(f"/api/profiles/{profile_id}/gap-fill", json=too_many)
    ).status_code == 422

    empty_content = {"messages": [{"role": "user", "content": ""}]}
    assert (
        await client.post(f"/api/profiles/{profile_id}/gap-fill", json=empty_content)
    ).status_code == 422

    bad_role = {"messages": [{"role": "system", "content": "hi"}]}
    assert (
        await client.post(f"/api/profiles/{profile_id}/gap-fill", json=bad_role)
    ).status_code == 422
