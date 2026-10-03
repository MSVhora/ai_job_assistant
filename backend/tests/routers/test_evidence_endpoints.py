import logging
import uuid

import pytest
from fakes import ScriptedEvidenceSource, install_evidence_source
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import session_factory
from app.main import app
from app.models import EvidenceItem, EvidenceSourceAccount, EvidenceSyncRun, SyncStatus
from app.schemas.evidence import EvidenceItemData, ScopeCandidate, SyncPage

pytestmark = pytest.mark.usefixtures("clean_tables")

TOKEN = "ghp_" + "r0uter" * 6


@pytest.fixture
async def client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        yield async_client


def scopes() -> list[ScopeCandidate]:
    return [
        ScopeCandidate(ref="ada/engine", description="Engine"),
        ScopeCandidate(ref="ada/secret", is_private=True),
        ScopeCandidate(ref="grace/fork", is_fork=True),
    ]


def one_page(external_id: str = "c1") -> SyncPage:
    item = EvidenceItemData(
        kind="commit",
        external_id=external_id,
        project_key="ada/engine",
        title="Ship loader",
        body="Ship the loader with streaming input",
        meta={"additions": 30, "deletions": 2, "parents": 1},
    )
    return SyncPage(items=[item], next_cursor={"stage": "done"}, requests_used=1)


@pytest.fixture
def source(monkeypatch: pytest.MonkeyPatch) -> ScriptedEvidenceSource:
    monkeypatch.setattr(get_settings(), "github_token", TOKEN)
    scripted = ScriptedEvidenceSource({"ada/engine": [one_page()]}, scopes=scopes())
    install_evidence_source(monkeypatch, scripted)
    return scripted


async def enable(client: AsyncClient, *refs: str, acknowledged: bool = False) -> dict[str, object]:
    response = await client.patch(
        "/api/evidence/github/scopes",
        json={
            "scopes": [{"ref": ref, "enabled": True} for ref in refs],
            "acknowledged_disclosure": acknowledged,
        },
    )
    return {"status": response.status_code, "body": response.json()}


async def test_status_reports_an_unconfigured_connector(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    install_evidence_source(monkeypatch, ScriptedEvidenceSource(configured=False))

    body = (await client.get("/api/evidence/github/status")).json()

    assert body["configured"] is False
    assert body["scopes_total"] == 0
    assert body["latest_sync"] is None


async def test_listing_scopes_stores_new_repos_disabled_and_flags_them_once(
    client: AsyncClient, source: ScriptedEvidenceSource
) -> None:
    first = (await client.get("/api/evidence/github/scopes")).json()
    second = (await client.get("/api/evidence/github/scopes")).json()

    assert [scope["ref"] for scope in first] == ["ada/engine", "ada/secret", "grace/fork"]
    assert all(scope["enabled"] is False and scope["is_new"] is True for scope in first)
    assert all(scope["is_new"] is False for scope in second)
    by_ref = {scope["ref"]: scope for scope in second}
    assert by_ref["ada/secret"]["is_private"] is True
    assert by_ref["grace/fork"]["is_fork"] is True
    status = (await client.get("/api/evidence/github/status")).json()
    assert (status["login"], status["scopes_total"], status["scopes_enabled"]) == ("ada", 3, 0)


async def test_scopes_require_a_configured_token(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    install_evidence_source(monkeypatch, ScriptedEvidenceSource(configured=False))

    response = await client.get("/api/evidence/github/scopes")

    assert response.status_code == 400
    assert "GITHUB_TOKEN" in response.json()["detail"]


async def test_enabling_a_private_scope_requires_the_disclosure_then_stamps_it(
    client: AsyncClient, source: ScriptedEvidenceSource
) -> None:
    await client.get("/api/evidence/github/scopes")

    refused = await enable(client, "ada/secret")
    granted = await enable(client, "ada/secret", acknowledged=True)

    assert refused["status"] == 409
    assert "disclosure" in str(refused["body"])
    assert granted["status"] == 200
    status = (await client.get("/api/evidence/github/status")).json()
    assert status["acknowledged_at"] is not None
    assert status["scopes_enabled"] == 1


async def test_public_scopes_enable_without_disclosure_and_update_settings(
    client: AsyncClient, source: ScriptedEvidenceSource
) -> None:
    await client.get("/api/evidence/github/scopes")

    response = await client.patch(
        "/api/evidence/github/scopes",
        json={
            "scopes": [
                {
                    "ref": "ada/engine",
                    "enabled": True,
                    "content_level": "metadata_only",
                    "employer_ref": {"company": "Analytical Ltd", "start_date": "2024-01"},
                }
            ]
        },
    )

    assert response.status_code == 200
    updated = response.json()[0]
    assert updated["enabled"] is True
    assert updated["content_level"] == "metadata_only"
    assert updated["employer_ref"]["company"] == "Analytical Ltd"


async def test_updating_an_unlisted_scope_is_a_404(
    client: AsyncClient, source: ScriptedEvidenceSource
) -> None:
    result = await enable(client, "ghost/missing")

    assert result["status"] == 404


async def test_sync_requires_a_token_and_an_enabled_scope(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    install_evidence_source(monkeypatch, ScriptedEvidenceSource(configured=False))
    assert (await client.post("/api/evidence/github/sync")).status_code == 400

    monkeypatch.setattr(get_settings(), "github_token", TOKEN)
    install_evidence_source(monkeypatch, ScriptedEvidenceSource(scopes=scopes()))
    await client.get("/api/evidence/github/scopes")
    response = await client.post("/api/evidence/github/sync")

    assert response.status_code == 400
    assert "enable at least one" in response.json()["detail"]


async def test_sync_runs_in_the_background_and_is_pollable(
    client: AsyncClient, source: ScriptedEvidenceSource
) -> None:
    await client.get("/api/evidence/github/scopes")
    await enable(client, "ada/engine")

    started = await client.post("/api/evidence/github/sync", json={"mode": "full"})

    assert started.status_code == 202
    sync_id = started.json()["sync_id"]
    polled = (await client.get(f"/api/evidence/syncs/{sync_id}")).json()
    assert polled["status"] == "succeeded"
    assert polled["mode"] == "full"
    assert polled["progress"]["items"] == 1
    async with session_factory() as session:
        assert len((await session.execute(select(EvidenceItem))).scalars().all()) == 1


async def test_sync_mode_defaults_to_incremental_and_rejects_unknown_modes(
    client: AsyncClient, source: ScriptedEvidenceSource
) -> None:
    await client.get("/api/evidence/github/scopes")
    await enable(client, "ada/engine")

    started = await client.post("/api/evidence/github/sync")
    bad = await client.post("/api/evidence/github/sync", json={"mode": "everything"})

    sync_id = started.json()["sync_id"]
    assert (await client.get(f"/api/evidence/syncs/{sync_id}")).json()["mode"] == "incremental"
    assert bad.status_code == 422


async def test_duplicate_start_returns_409_with_the_active_sync_id(
    client: AsyncClient, source: ScriptedEvidenceSource
) -> None:
    await client.get("/api/evidence/github/scopes")
    await enable(client, "ada/engine")
    async with session_factory() as session:
        account = (await session.execute(select(EvidenceSourceAccount))).scalar_one()
        active = EvidenceSyncRun(source_id=account.id, status=SyncStatus.running)
        session.add(active)
        await session.commit()
        active_id = str(active.id)

    response = await client.post("/api/evidence/github/sync")

    assert response.status_code == 409
    assert response.json()["active_sync_id"] == active_id


async def test_unknown_sync_ids_are_404(
    client: AsyncClient, source: ScriptedEvidenceSource
) -> None:
    response = await client.get(f"/api/evidence/syncs/{uuid.uuid4()}")

    assert response.status_code == 404


async def test_runs_of_another_candidate_are_not_visible(
    client: AsyncClient, source: ScriptedEvidenceSource
) -> None:
    await client.get("/api/evidence/github/scopes")
    from app.models import Candidate

    async with session_factory() as session:
        stranger = Candidate()
        session.add(stranger)
        await session.flush()
        account = EvidenceSourceAccount(candidate_id=stranger.id, kind="github")
        session.add(account)
        await session.flush()
        run = EvidenceSyncRun(source_id=account.id, status=SyncStatus.succeeded)
        session.add(run)
        await session.commit()
        foreign_id = run.id

    own = (await client.get("/api/evidence/syncs")).json()

    assert (await client.get(f"/api/evidence/syncs/{foreign_id}")).status_code == 404
    assert all(entry["id"] != str(foreign_id) for entry in own)


async def test_sync_list_is_bounded_and_reports_the_total(
    client: AsyncClient, source: ScriptedEvidenceSource
) -> None:
    await client.get("/api/evidence/github/scopes")
    await enable(client, "ada/engine")
    for _ in range(3):
        await client.post("/api/evidence/github/sync")

    response = await client.get("/api/evidence/syncs", params={"limit": 2})

    assert response.status_code == 200
    assert len(response.json()) == 2
    assert response.headers["x-total-count"] == "3"
    assert (await client.get("/api/evidence/syncs", params={"limit": 500})).status_code == 422


async def test_responses_and_logs_never_contain_the_token(
    client: AsyncClient, source: ScriptedEvidenceSource, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    bodies = [(await client.get("/api/evidence/github/scopes")).text]
    await enable(client, "ada/engine")
    started = await client.post("/api/evidence/github/sync")
    bodies.append(started.text)
    bodies.append((await client.get(f"/api/evidence/syncs/{started.json()['sync_id']}")).text)
    bodies.append((await client.get("/api/evidence/syncs")).text)
    bodies.append((await client.get("/api/evidence/github/status")).text)

    assert all(TOKEN not in body for body in bodies)
    assert TOKEN not in "\n".join(record.getMessage() for record in caplog.records)
