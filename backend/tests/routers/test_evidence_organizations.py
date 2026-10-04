import uuid
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
from app.models import Achievement
from app.schemas.evidence import ScopeCandidate

pytestmark = pytest.mark.usefixtures("clean_tables")

ACME = {"company": "Acme Corp"}
ACME_STORED = {"company": "Acme Corp", "start_date": None}


@pytest.fixture
async def client(monkeypatch: pytest.MonkeyPatch) -> AsyncClient:
    monkeypatch.setattr(get_settings(), "github_token", "ghp_" + "o" * 36)
    install_evidence_source(
        monkeypatch,
        ScriptedEvidenceSource(
            scopes=[
                ScopeCandidate(ref="Acme-Org/api"),
                ScopeCandidate(ref="acme-org/web"),
                ScopeCandidate(ref="ada/side"),
            ]
        ),
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as c:
        yield c


async def setup_scopes(client: AsyncClient) -> None:
    await seed_profile_light()
    await client.post("/api/evidence/github/scopes/refresh")


async def map_owner(client: AsyncClient, owner: str, employer: Any) -> Any:
    return await client.patch(
        f"/api/evidence/github/organizations/{owner}", json={"employer_ref": employer}
    )


async def owners_by_name(client: AsyncClient) -> dict[str, Any]:
    response = await client.get("/api/evidence/github/organizations")
    return {o["owner"]: o for o in response.json()}


async def scopes_by_ref(client: AsyncClient) -> dict[str, Any]:
    return {s["ref"]: s for s in (await client.get("/api/evidence/github/scopes")).json()}


async def test_owners_are_listed_case_insensitively_with_counts(client: AsyncClient) -> None:
    await setup_scopes(client)
    await client.patch(
        "/api/evidence/github/scopes", json={"scopes": [{"ref": "acme-org/web", "enabled": True}]}
    )

    owners = {
        o["owner"]: o for o in (await client.get("/api/evidence/github/organizations")).json()
    }

    assert owners["acme-org"]["repos"] == 2
    assert owners["acme-org"]["selected"] == 1
    assert owners["acme-org"]["employer"] is None
    assert owners["ada"]["repos"] == 1


async def test_mapping_an_owner_applies_to_selected_and_unselected_repositories(
    client: AsyncClient,
) -> None:
    await setup_scopes(client)
    await client.patch(
        "/api/evidence/github/scopes", json={"scopes": [{"ref": "acme-org/web", "enabled": True}]}
    )

    response = await map_owner(client, "ACME-ORG", ACME)

    assert response.status_code == 200
    scopes = await scopes_by_ref(client)
    assert scopes["Acme-Org/api"]["employer_ref"] == {**ACME_STORED, "source": "org"}
    assert scopes["acme-org/web"]["employer_ref"] == {**ACME_STORED, "source": "org"}
    assert scopes["ada/side"]["employer_ref"] is None
    owners = {o["owner"]: o for o in response.json()}
    assert owners["acme-org"]["employer"] == ACME_STORED
    assert owners["acme-org"]["explicit"] == 0


async def test_a_repository_mapped_on_its_own_keeps_it(client: AsyncClient) -> None:
    await setup_scopes(client)
    await client.patch(
        "/api/evidence/github/scopes",
        json={"scopes": [{"ref": "acme-org/web", "employer_ref": {"kind": "personal"}}]},
    )

    response = await map_owner(client, "acme-org", ACME)

    scopes = await scopes_by_ref(client)
    assert scopes["acme-org/web"]["employer_ref"] == {"kind": "personal", "source": "user"}
    assert scopes["Acme-Org/api"]["employer_ref"]["company"] == "Acme Corp"
    assert {o["owner"]: o for o in response.json()}["acme-org"]["explicit"] == 1


async def test_clearing_the_owner_only_clears_what_it_set(client: AsyncClient) -> None:
    await setup_scopes(client)
    await client.patch(
        "/api/evidence/github/scopes",
        json={"scopes": [{"ref": "acme-org/web", "employer_ref": ACME}]},
    )
    await map_owner(client, "acme-org", ACME)

    await map_owner(client, "acme-org", None)

    scopes = await scopes_by_ref(client)
    assert scopes["Acme-Org/api"]["employer_ref"] is None
    assert scopes["acme-org/web"]["employer_ref"]["source"] == "user"
    owners = {
        o["owner"]: o for o in (await client.get("/api/evidence/github/organizations")).json()
    }
    assert owners["acme-org"]["employer"] is None


async def test_a_repository_cleared_on_its_own_falls_back_to_the_owner(
    client: AsyncClient,
) -> None:
    await setup_scopes(client)
    await map_owner(client, "acme-org", ACME)
    await client.patch(
        "/api/evidence/github/scopes",
        json={"scopes": [{"ref": "acme-org/web", "employer_ref": {"kind": "personal"}}]},
    )

    await client.patch(
        "/api/evidence/github/scopes",
        json={"scopes": [{"ref": "acme-org/web", "employer_ref": None}]},
    )

    assert (await scopes_by_ref(client))["acme-org/web"]["employer_ref"]["source"] == "org"


async def test_a_repository_found_by_a_later_refresh_inherits_the_owner(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    await setup_scopes(client)
    await map_owner(client, "acme-org", ACME)
    install_evidence_source(
        monkeypatch,
        ScriptedEvidenceSource(
            scopes=[ScopeCandidate(ref="acme-org/api"), ScopeCandidate(ref="acme-org/new")]
        ),
    )

    await client.post("/api/evidence/github/scopes/refresh")

    scope = (await scopes_by_ref(client))["acme-org/new"]
    assert scope["employer_ref"] == {**ACME_STORED, "source": "org"}
    assert scope["enabled"] is False


async def test_achievements_of_the_owners_repositories_follow_except_user_choices(
    client: AsyncClient,
) -> None:
    await setup_scopes(client)
    async with session_factory() as session:
        candidate_id = (
            await session.execute(text("SELECT id FROM candidate LIMIT 1"))
        ).scalar_one()
    plain = await seed_achievement(candidate_id, item_ids=[], project_key="Acme-Org/api")
    chosen = await seed_achievement(candidate_id, item_ids=[], project_key="acme-org/web")
    async with session_factory() as session:
        row = await session.get_one(Achievement, chosen)
        row.employer_ref = {"kind": "personal", "source": "user"}
        await session.commit()

    await map_owner(client, "acme-org", ACME)

    async with session_factory() as session:
        rows = {
            a.id: a.employer_ref for a in (await session.execute(select(Achievement))).scalars()
        }
    assert rows[plain] == {**ACME_STORED, "source": "scope"}
    assert rows[chosen] == {"kind": "personal", "source": "user"}


async def test_the_users_own_account_is_flagged(client: AsyncClient) -> None:
    await setup_scopes(client)
    async with session_factory() as session:
        await session.execute(text("UPDATE evidence_source SET account_login = 'Ada'"))
        await session.commit()

    owners = {
        o["owner"]: o for o in (await client.get("/api/evidence/github/organizations")).json()
    }

    assert owners["ada"]["personal_account"] is True
    assert owners["acme-org"]["personal_account"] is False


async def test_an_unknown_employer_or_owner_is_rejected(client: AsyncClient) -> None:
    await setup_scopes(client)

    unknown_employer = await map_owner(client, "acme-org", {"company": "Nowhere Inc"})
    unknown_owner = await map_owner(client, f"nobody-{uuid.uuid4().hex[:6]}", ACME)

    assert unknown_employer.status_code == 400
    assert unknown_owner.status_code == 404
