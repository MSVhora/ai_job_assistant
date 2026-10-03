import json
import uuid
from typing import Any

import pytest
from fakes import golden_profile
from httpx import ASGITransport, AsyncClient

from app.core.db import session_factory
from app.main import app
from app.models import Achievement, AchievementStatus, Candidate, Profile
from app.schemas.evidence import SourceIdentity
from app.services import resume_documents

pytestmark = pytest.mark.usefixtures("clean_tables")

BASE = "/api/resume-documents"
TOTAL = "x-total-count"
PRIVATE_TEXT = "Wrote the confidential ingestion layer"


class FakeGitHub:
    def is_configured(self) -> bool:
        return True

    async def identify(self) -> SourceIdentity:
        return SourceIdentity(login="ada", name="Augusta Byron", location="London")


@pytest.fixture(autouse=True)
def _github(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(resume_documents, "get_source", lambda _name: FakeGitHub())


@pytest.fixture
async def client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        yield async_client


async def seed_profile() -> uuid.UUID:
    async with session_factory() as session:
        candidate = Candidate()
        session.add(candidate)
        await session.flush()
        profile = Profile(
            candidate_id=candidate.id,
            name="Ada profile",
            structured_profile=golden_profile().model_dump(mode="json"),
        )
        session.add(profile)
        await session.flush()
        session.add(
            Achievement(
                candidate_id=candidate.id,
                status=AchievementStatus.approved,
                title="Kubernetes rollout",
                impact_type="delivery",
                difficulty=3,
                skills=["Kubernetes"],
            )
        )
        profile_id = profile.id
        await session.commit()
        return profile_id


async def create(client: AsyncClient, profile_id: uuid.UUID, **extra: Any) -> dict[str, Any]:
    response = await client.post(BASE, json={"profile_id": str(profile_id), **extra})
    assert response.status_code == 201, response.text
    return response.json()


async def test_create_read_update_delete_round_trip(client: AsyncClient) -> None:
    profile_id = await seed_profile()

    created = await create(client, profile_id, title="Backend roles", page_target=2)
    fetched = await client.get(f"{BASE}/{created['id']}")
    content = fetched.json()["content"]
    content["basics"]["summary"] = "Edited"
    patched = await client.patch(
        f"{BASE}/{created['id']}", json={"content": content, "status": "final"}
    )
    deleted = await client.delete(f"{BASE}/{created['id']}")
    gone = await client.get(f"{BASE}/{created['id']}")

    # Creation writes version 1; generation then drops the golden profile's overlapping role.
    assert (created["title"], created["page_target"], created["version"]) == ("Backend roles", 2, 2)
    assert fetched.json()["content"]["basics"]["full_name"] == "Ada Lovelace"
    assert (patched.status_code, patched.json()["version"], patched.json()["status"]) == (
        200,
        3,
        "final",
    )
    assert deleted.status_code == 204
    assert deleted.content == b""
    assert (gone.status_code, gone.json()) == (404, {"detail": "resume document not found"})


@pytest.mark.parametrize("pages", [0, 5])
async def test_page_target_outside_one_to_four_is_unprocessable(
    client: AsyncClient, pages: int
) -> None:
    profile_id = await seed_profile()
    created = await create(client, profile_id)

    on_create = await client.post(BASE, json={"profile_id": str(profile_id), "page_target": pages})
    on_update = await client.patch(f"{BASE}/{created['id']}", json={"page_target": pages})

    assert (on_create.status_code, on_update.status_code) == (422, 422)


async def test_unknown_profile_and_unknown_fields_are_rejected(client: AsyncClient) -> None:
    profile_id = await seed_profile()
    created = await create(client, profile_id)

    missing = await client.post(BASE, json={"profile_id": str(uuid.uuid4())})
    extra = await client.patch(f"{BASE}/{created['id']}", json={"layout": {}})

    assert missing.status_code == 404
    assert extra.status_code == 422


async def test_list_is_paginated_and_bounded(client: AsyncClient) -> None:
    profile_id = await seed_profile()
    for _ in range(3):
        await create(client, profile_id)

    page = await client.get(BASE, params={"limit": 2, "profile_id": str(profile_id)})
    too_many = await client.get(BASE, params={"limit": 201})

    assert (page.status_code, len(page.json()), page.headers[TOTAL]) == (200, 2, "3")
    assert "content" not in page.json()[0]
    assert too_many.status_code == 422


async def test_put_is_not_an_allowed_method(client: AsyncClient) -> None:
    profile_id = await seed_profile()
    created = await create(client, profile_id)

    response = await client.put(f"{BASE}/{created['id']}", json={})

    assert response.status_code == 405


async def test_export_formats_are_clean_and_typed(client: AsyncClient) -> None:
    profile_id = await seed_profile()
    created = await create(client, profile_id)
    content = created["content"]
    content["work"][0]["highlights"].append(
        {"text": PRIVATE_TEXT, "from_private": True, "origin": "generated", "check": "needs_review"}
    )
    await client.patch(f"{BASE}/{created['id']}", json={"content": content})

    text = await client.get(f"{BASE}/{created['id']}/export")
    markdown = await client.get(f"{BASE}/{created['id']}/export", params={"format": "markdown"})
    json_resume = await client.get(
        f"{BASE}/{created['id']}/export", params={"format": "json_resume"}
    )
    invalid = await client.get(f"{BASE}/{created['id']}/export", params={"format": "pdf"})

    assert text.headers["content-type"].startswith("text/plain")
    assert markdown.headers["content-type"].startswith("text/markdown")
    assert json_resume.headers["content-type"].startswith("application/json")
    assert markdown.text.startswith("# Ada Lovelace")
    assert json.loads(json_resume.text)["basics"]["name"] == "Ada Lovelace"
    for body in (text.text, markdown.text, json_resume.text):
        assert body.count(PRIVATE_TEXT) == 1
        assert "from_private" not in body
        assert "needs_review" not in body
    assert invalid.status_code == 422


async def test_conflicts_resolve_and_reopen_through_the_api(client: AsyncClient) -> None:
    profile_id = await seed_profile()
    created = await create(client, profile_id)
    url = f"{BASE}/{created['id']}/conflicts"

    report = (await client.get(url)).json()
    kinds = {item["kind"] for item in report["open"]}
    key = next(i["key"] for i in report["open"] if i["kind"] == "identity_mismatch")
    kept = await client.post(f"{url}/{key}/resolve", json={"action": "keep_as_is"})
    reopened = await client.post(f"{url}/{key}/resolve", json={"action": "reopen"})
    unknown = await client.post(f"{url}/nope/resolve", json={"action": "keep_as_is"})
    bad_action = await client.post(f"{url}/{key}/resolve", json={"action": "delete"})

    assert {"identity_mismatch", "overlapping_roles", "skill_missing_in_profile"} <= kinds
    assert report["github_checked"] is True
    assert [i["key"] for i in kept.json()["resolved"]] == [key]
    assert reopened.json()["resolved"] == []
    assert (unknown.status_code, bad_action.status_code) == (404, 422)


async def test_resync_identity_endpoint_returns_the_document(client: AsyncClient) -> None:
    profile_id = await seed_profile()
    created = await create(client, profile_id)

    response = await client.post(f"{BASE}/{created['id']}/resync-identity")

    assert response.status_code == 200
    assert response.json()["id"] == created["id"]
