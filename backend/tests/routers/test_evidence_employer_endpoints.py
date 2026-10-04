import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from fakes import (
    ScriptedEvidenceSource,
    install_evidence_source,
    seed_achievement,
    seed_profile_light,
)
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text

from app.core.config import get_settings
from app.core.db import session_factory
from app.main import app
from app.models import Achievement, EvidenceItem, EvidenceKind, EvidenceScope
from app.schemas.evidence import ScopeCandidate

pytestmark = pytest.mark.usefixtures("clean_tables")

ACME = {"company": "Acme Corp", "start_date": "Mar 2021"}


@pytest.fixture
async def client(monkeypatch: pytest.MonkeyPatch) -> AsyncClient:
    monkeypatch.setattr(get_settings(), "github_token", "ghp_" + "e" * 36)
    install_evidence_source(
        monkeypatch,
        ScriptedEvidenceSource(
            scopes=[ScopeCandidate(ref="ada/engine"), ScopeCandidate(ref="ada/side")]
        ),
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as c:
        yield c


async def add_items(ref: str, first: datetime, last: datetime) -> uuid.UUID:
    async with session_factory() as session:
        scope = (
            await session.execute(select(EvidenceScope).where(EvidenceScope.ref == ref))
        ).scalar_one()
        candidate_id = (
            await session.execute(text("SELECT id FROM candidate LIMIT 1"))
        ).scalar_one()
        for index, stamp in enumerate((first, last)):
            session.add(
                EvidenceItem(
                    candidate_id=candidate_id,
                    scope_id=scope.id,
                    kind=EvidenceKind.commit,
                    external_id=f"{ref}-{index}",
                    project_key=ref,
                    body="work",
                    occurred_at=stamp,
                    content_hash=f"{ref}-{index}",
                )
            )
        await session.commit()
        return scope.id


async def patch_scope(client: AsyncClient, ref: str, employer: Any) -> Any:
    return await client.patch(
        "/api/evidence/github/scopes",
        json={"scopes": [{"ref": ref, "employer_ref": employer}]},
    )


async def test_the_employer_options_come_from_every_profile_plus_personal(
    client: AsyncClient,
) -> None:
    await seed_profile_light()

    options = (await client.get("/api/evidence/employers")).json()

    assert options == [
        {
            "kind": "experience",
            "label": "Acme Corp (Mar 2021)",
            "company": "Acme Corp",
            "start_date": "Mar 2021",
        },
        {
            "kind": "personal",
            "label": "Personal / open source",
            "company": None,
            "start_date": None,
        },
    ]


async def test_without_profiles_only_the_personal_option_exists(client: AsyncClient) -> None:
    options = (await client.get("/api/evidence/employers")).json()

    assert [o["kind"] for o in options] == ["personal"]


async def test_a_valid_mapping_is_stored_and_applied_to_the_repos_achievements(
    client: AsyncClient,
) -> None:
    await seed_profile_light()
    await client.post("/api/evidence/github/scopes/refresh")
    async with session_factory() as session:
        candidate_id = (
            await session.execute(text("SELECT id FROM candidate LIMIT 1"))
        ).scalar_one()
    achievement_id = await seed_achievement(candidate_id, item_ids=[], project_key="ada/engine")

    response = await patch_scope(client, "ada/engine", ACME)

    assert response.status_code == 200
    assert response.json()[0]["employer_ref"] == {**ACME, "source": "user"}
    async with session_factory() as session:
        stored = await session.get_one(Achievement, achievement_id)
    assert stored.employer_ref == {**ACME, "source": "scope"}
    cleared = await patch_scope(client, "ada/engine", None)
    assert cleared.json()[0]["employer_ref"] is None
    async with session_factory() as session:
        assert (await session.get_one(Achievement, achievement_id)).employer_ref is None


@pytest.mark.parametrize(
    "employer",
    [
        {"company": "Nowhere Inc", "start_date": "2020"},
        {"company": "Acme Corp", "start_date": "2001"},
    ],
)
async def test_a_mapping_outside_the_profiles_experience_is_rejected(
    client: AsyncClient, employer: dict[str, str]
) -> None:
    await seed_profile_light()
    await client.post("/api/evidence/github/scopes/refresh")

    response = await patch_scope(client, "ada/engine", employer)

    assert response.status_code == 400
    assert "experience entries" in response.json()["detail"]
    scopes = (await client.get("/api/evidence/github/scopes")).json()
    assert {s["ref"]: s["employer_ref"] for s in scopes}["ada/engine"] is None


async def test_personal_mapping_needs_no_profile(client: AsyncClient) -> None:
    await client.post("/api/evidence/github/scopes/refresh")

    response = await patch_scope(client, "ada/side", {"kind": "personal"})

    assert response.json()[0]["employer_ref"] == {"kind": "personal", "source": "user"}


async def test_a_repo_active_during_exactly_one_job_gets_a_suggestion(client: AsyncClient) -> None:
    await seed_profile_light()
    await client.post("/api/evidence/github/scopes/refresh")
    await add_items(
        "ada/engine", datetime(2022, 1, 1, tzinfo=UTC), datetime(2022, 6, 1, tzinfo=UTC)
    )
    await add_items("ada/side", datetime(2020, 1, 1, tzinfo=UTC), datetime(2024, 12, 1, tzinfo=UTC))

    scopes = {s["ref"]: s for s in (await client.get("/api/evidence/github/scopes")).json()}

    assert scopes["ada/engine"]["suggested_employer"] == {**ACME, "source": "suggested"}
    assert scopes["ada/side"]["suggested_employer"] is None
    assert scopes["ada/engine"]["employer_ref"] is None


async def test_a_confirmed_repo_no_longer_gets_a_suggestion(client: AsyncClient) -> None:
    await seed_profile_light()
    await client.post("/api/evidence/github/scopes/refresh")
    await add_items(
        "ada/engine", datetime(2022, 1, 1, tzinfo=UTC), datetime(2022, 6, 1, tzinfo=UTC)
    )
    await patch_scope(client, "ada/engine", ACME)

    scopes = {s["ref"]: s for s in (await client.get("/api/evidence/github/scopes")).json()}

    assert scopes["ada/engine"]["suggested_employer"] is None


async def test_status_counts_synced_enabled_repos_without_a_mapping(client: AsyncClient) -> None:
    await seed_profile_light()
    await client.post("/api/evidence/github/scopes/refresh")
    await client.patch(
        "/api/evidence/github/scopes",
        json={
            "scopes": [{"ref": "ada/engine", "enabled": True}, {"ref": "ada/side", "enabled": True}]
        },
    )
    assert (await client.get("/api/evidence/github/status")).json()["scopes_unmapped"] == 0

    async with session_factory() as session:
        await session.execute(text("UPDATE evidence_scope SET last_synced_at = now()"))
        await session.commit()
    assert (await client.get("/api/evidence/github/status")).json()["scopes_unmapped"] == 2

    await patch_scope(client, "ada/engine", ACME)
    assert (await client.get("/api/evidence/github/status")).json()["scopes_unmapped"] == 1
