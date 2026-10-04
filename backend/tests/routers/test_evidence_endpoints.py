import logging
import uuid
from datetime import UTC, datetime

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


REFRESH = "/api/evidence/github/scopes/refresh"
LIST = "/api/evidence/github/scopes"


class NoGitHubSource(ScriptedEvidenceSource):
    """Any call to GitHub fails the test: used to prove the list is read from the database."""

    async def identify(self) -> object:
        message = "the repository list must not ask GitHub"
        raise AssertionError(message)

    async def list_scopes(self) -> list[object]:
        message = "the repository list must not ask GitHub"
        raise AssertionError(message)


async def test_refresh_stores_new_repos_disabled_and_flags_them_until_the_next_refresh(
    client: AsyncClient, source: ScriptedEvidenceSource
) -> None:
    first = (await client.post(REFRESH)).json()
    second = (await client.post(REFRESH)).json()

    assert [scope["ref"] for scope in first] == ["ada/engine", "ada/secret", "grace/fork"]
    assert all(scope["enabled"] is False and scope["is_new"] is True for scope in first)
    assert all(scope["is_new"] is False for scope in second)
    by_ref = {scope["ref"]: scope for scope in second}
    assert by_ref["ada/secret"]["is_private"] is True
    assert by_ref["grace/fork"]["is_fork"] is True
    status = (await client.get("/api/evidence/github/status")).json()
    assert (status["login"], status["scopes_total"], status["scopes_enabled"]) == ("ada", 3, 0)
    assert status["scopes_refreshed_at"] is not None


async def test_the_list_is_read_from_the_database_and_never_asks_github(
    client: AsyncClient, source: ScriptedEvidenceSource, monkeypatch: pytest.MonkeyPatch
) -> None:
    refreshed = (await client.post(REFRESH)).json()
    install_evidence_source(monkeypatch, NoGitHubSource())

    listed = await client.get(LIST)

    assert listed.status_code == 200
    assert listed.json() == refreshed


async def test_the_list_is_empty_and_status_unrefreshed_before_the_first_refresh(
    client: AsyncClient, source: ScriptedEvidenceSource
) -> None:
    assert (await client.get(LIST)).json() == []
    status = (await client.get("/api/evidence/github/status")).json()
    assert status["scopes_refreshed_at"] is None


async def test_refresh_stores_listing_details_and_never_enables_anything(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "github_token", TOKEN)
    pushed = datetime(2026, 9, 1, 10, 0, tzinfo=UTC)
    install_evidence_source(
        monkeypatch,
        ScriptedEvidenceSource(
            scopes=[
                ScopeCandidate(
                    ref="ada/engine",
                    description="Engine",
                    pushed_at=pushed,
                    contributed=True,
                    is_fork=True,
                ),
                ScopeCandidate(ref="outsider/lib", contributed=True),
            ]
        ),
    )

    await client.post(REFRESH)
    listed = {scope["ref"]: scope for scope in (await client.get(LIST)).json()}

    engine = listed["ada/engine"]
    assert (engine["description"], engine["is_fork"], engine["contributed"]) == (
        "Engine",
        True,
        True,
    )
    assert engine["pushed_at"].startswith("2026-09-01T10:00:00")
    assert listed["outsider/lib"]["pushed_at"] is None
    assert not any(scope["enabled"] for scope in listed.values())


async def test_the_list_puts_recently_pushed_repos_first_and_contributed_only_ones_last(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "github_token", TOKEN)
    older, newer = datetime(2025, 1, 1, tzinfo=UTC), datetime(2026, 1, 1, tzinfo=UTC)
    install_evidence_source(
        monkeypatch,
        ScriptedEvidenceSource(
            scopes=[
                ScopeCandidate(ref="a/contributed-only", contributed=True),
                ScopeCandidate(ref="a/older", pushed_at=older),
                ScopeCandidate(ref="a/newer", pushed_at=newer),
            ]
        ),
    )

    await client.post(REFRESH)

    assert [scope["ref"] for scope in (await client.get(LIST)).json()] == [
        "a/newer",
        "a/older",
        "a/contributed-only",
    ]


async def test_listing_marks_contributed_repos_and_skips_old_unrelated_ones(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "github_token", TOKEN)
    install_evidence_source(
        monkeypatch,
        ScriptedEvidenceSource(
            scopes=[
                ScopeCandidate(ref="ada/engine", contributed=True),
                ScopeCandidate(ref="ada/ancient", outside_lookback=True),
                ScopeCandidate(ref="outsider/lib", contributed=True),
            ]
        ),
    )

    listed = (await client.post(REFRESH)).json()

    assert [scope["ref"] for scope in listed] == ["ada/engine", "outsider/lib"]
    assert all(scope["contributed"] is True and scope["visible"] is True for scope in listed)


async def test_a_stored_repo_the_provider_stops_listing_is_marked_not_visible(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "github_token", TOKEN)
    first = ScriptedEvidenceSource(scopes=scopes())
    install_evidence_source(monkeypatch, first)
    await client.post("/api/evidence/github/scopes/refresh")
    await enable(client, "ada/engine")
    install_evidence_source(
        monkeypatch,
        ScriptedEvidenceSource(scopes=[ScopeCandidate(ref="ada/secret", is_private=True)]),
    )

    listed = {scope["ref"]: scope for scope in (await client.post(REFRESH)).json()}

    assert listed["ada/secret"]["visible"] is True
    assert listed["ada/engine"]["visible"] is False
    assert listed["ada/engine"]["enabled"] is True
    assert listed["grace/fork"]["visible"] is False


async def test_a_repo_that_is_old_but_already_stored_stays_visible(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "github_token", TOKEN)
    install_evidence_source(monkeypatch, ScriptedEvidenceSource(scopes=scopes()))
    await client.post("/api/evidence/github/scopes/refresh")
    install_evidence_source(
        monkeypatch,
        ScriptedEvidenceSource(scopes=[ScopeCandidate(ref="ada/engine", outside_lookback=True)]),
    )

    listed = {scope["ref"]: scope for scope in (await client.post(REFRESH)).json()}

    assert listed["ada/engine"]["visible"] is True


@pytest.mark.parametrize(
    ("permissions", "token_type", "private_access", "warns"),
    [
        (["public_repo", "read:org"], "classic", False, True),
        (["repo", "read:org"], "classic", True, False),
        ([], "fine_grained_or_app", None, False),
    ],
)
async def test_the_token_check_reports_scopes_and_warns_when_private_repos_are_hidden(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    permissions: list[str],
    token_type: str,
    private_access: bool | None,
    warns: bool,
) -> None:
    monkeypatch.setattr(get_settings(), "github_token", TOKEN)
    install_evidence_source(monkeypatch, ScriptedEvidenceSource(permissions=permissions))
    await client.post(REFRESH)
    install_evidence_source(monkeypatch, NoGitHubSource())

    body = (await client.get("/api/evidence/github/token")).json()

    assert body["login"] == "ada"
    assert body["token_type"] == token_type
    assert body["private_access"] is private_access
    assert body["scopes"] == sorted(permissions)
    assert bool(body["warnings"]) is warns
    if warns:
        assert "`repo`" in body["warnings"][0]
    assert TOKEN not in str(body)


async def test_the_token_check_is_null_until_the_first_refresh(
    client: AsyncClient, source: ScriptedEvidenceSource
) -> None:
    response = await client.get("/api/evidence/github/token")

    assert response.status_code == 200
    assert response.json() is None


async def test_refreshing_the_list_requires_a_configured_token(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    install_evidence_source(monkeypatch, ScriptedEvidenceSource(configured=False))

    response = await client.post(REFRESH)

    assert response.status_code == 400
    assert "GITHUB_TOKEN" in response.json()["detail"]


async def test_enabling_a_private_scope_requires_the_disclosure_then_stamps_it(
    client: AsyncClient, source: ScriptedEvidenceSource
) -> None:
    await client.post("/api/evidence/github/scopes/refresh")

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
    await client.post("/api/evidence/github/scopes/refresh")

    response = await client.patch(
        "/api/evidence/github/scopes",
        json={
            "scopes": [
                {
                    "ref": "ada/engine",
                    "enabled": True,
                    "content_level": "metadata_only",
                    "employer_ref": {"kind": "personal"},
                }
            ]
        },
    )

    assert response.status_code == 200
    updated = response.json()[0]
    assert updated["enabled"] is True
    assert updated["content_level"] == "metadata_only"
    assert updated["employer_ref"] == {"kind": "personal", "source": "user"}


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
    await client.post("/api/evidence/github/scopes/refresh")
    response = await client.post("/api/evidence/github/sync")

    assert response.status_code == 400
    assert "enable at least one" in response.json()["detail"]


async def test_sync_runs_in_the_background_and_is_pollable(
    client: AsyncClient, source: ScriptedEvidenceSource
) -> None:
    await client.post("/api/evidence/github/scopes/refresh")
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
    await client.post("/api/evidence/github/scopes/refresh")
    await enable(client, "ada/engine")

    started = await client.post("/api/evidence/github/sync")
    bad = await client.post("/api/evidence/github/sync", json={"mode": "everything"})

    sync_id = started.json()["sync_id"]
    assert (await client.get(f"/api/evidence/syncs/{sync_id}")).json()["mode"] == "incremental"
    assert bad.status_code == 422


async def test_duplicate_start_returns_409_with_the_active_sync_id(
    client: AsyncClient, source: ScriptedEvidenceSource
) -> None:
    await client.post("/api/evidence/github/scopes/refresh")
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
    await client.post("/api/evidence/github/scopes/refresh")
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
    await client.post("/api/evidence/github/scopes/refresh")
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
    bodies = [(await client.post(REFRESH)).text, (await client.get(LIST)).text]
    await enable(client, "ada/engine")
    started = await client.post("/api/evidence/github/sync")
    bodies.append(started.text)
    bodies.append((await client.get(f"/api/evidence/syncs/{started.json()['sync_id']}")).text)
    bodies.append((await client.get("/api/evidence/syncs")).text)
    bodies.append((await client.get("/api/evidence/github/status")).text)

    assert all(TOKEN not in body for body in bodies)
    assert TOKEN not in "\n".join(record.getMessage() for record in caplog.records)
