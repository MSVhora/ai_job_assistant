import logging
import uuid
from typing import Any

import pytest
from fakes import fake_vector, seed_achievement, seed_evidence_chunk
from httpx import ASGITransport, AsyncClient

from app.core.config import get_settings
from app.main import app

pytestmark = pytest.mark.usefixtures("clean_tables")

BODIES = ["Cut the import from 42 minutes to 9", "Add retry budget", "Tidy tests", "Fix loader"]
MARKER = "okapi-marker-9921"
PENDING = [
    {"text": "10x", "source_quote": "ten", "evidence_ids": [], "verified": "needs_confirmation"}
]


@pytest.fixture(autouse=True)
def _key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "gemini_api_key", "test-key")


@pytest.fixture
async def client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        yield async_client


async def seeded(**kwargs: Any) -> tuple[uuid.UUID, uuid.UUID, list[uuid.UUID]]:
    candidate_id, _, items = await seed_evidence_chunk(bodies=BODIES)
    use = kwargs.pop("item_ids", items[:1])
    return candidate_id, await seed_achievement(candidate_id, item_ids=use, **kwargs), items


async def test_the_list_ranks_by_difficulty_and_evidence_and_filters() -> None:
    candidate_id, _, items = await seed_evidence_chunk(bodies=BODIES)
    await seed_achievement(candidate_id, item_ids=items[:1], title="Easy", difficulty=1)
    await seed_achievement(
        candidate_id, item_ids=items[:3], title="Hard well evidenced", difficulty=5
    )
    await seed_achievement(
        candidate_id, item_ids=items[:1], title="Other repo", difficulty=3, project_key="ada/other"
    )
    await seed_achievement(
        candidate_id, item_ids=items[:1], title="Secret", difficulty=2, private=True, stale=True
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as c:
        ranked = (await c.get("/api/achievements")).json()
        recent = (await c.get("/api/achievements", params={"sort": "recent"})).json()
        in_repo = (await c.get("/api/achievements", params={"project_key": "ada/other"})).json()
        private = (await c.get("/api/achievements", params={"private": "true"})).json()
        stale = (await c.get("/api/achievements", params={"stale": "true"})).json()
        fresh = (await c.get("/api/achievements", params={"stale": "false"})).json()

    assert [a["title"] for a in ranked] == ["Hard well evidenced", "Other repo", "Secret", "Easy"]
    assert recent[0]["title"] == "Secret"
    assert [a["title"] for a in in_repo] == ["Other repo"]
    assert [a["title"] for a in private] == ["Secret"]
    assert [a["title"] for a in stale] == ["Secret"]
    assert len(fresh) == 3


async def test_detail_404s_for_unknown_and_foreign_ids(client: AsyncClient) -> None:
    _, achievement_id, _ = await seeded()
    stranger, _, stranger_items = await seed_evidence_chunk(bodies=["Other candidate"])
    foreign = await seed_achievement(stranger, item_ids=stranger_items[:1])

    ok = await client.get(f"/api/achievements/{achievement_id}")

    assert ok.status_code == 200
    assert ok.json()["id"] == str(achievement_id)
    for missing in (uuid.uuid4(), foreign):
        assert (await client.get(f"/api/achievements/{missing}")).status_code == 404
        assert (await client.post(f"/api/achievements/{missing}/approve")).status_code == 404


async def test_patching_validates_the_body_and_records_the_edit(client: AsyncClient) -> None:
    _, achievement_id, _ = await seeded()
    url = f"/api/achievements/{achievement_id}"

    assert (await client.patch(url, json={})).status_code == 422
    assert (await client.patch(url, json={"difficulty": 9})).status_code == 422
    assert (await client.patch(url, json={"title": None})).status_code == 422
    assert (
        await client.patch(url, json={"time_start": "2024-05-01", "time_end": "2024-04-01"})
    ).status_code == 400
    edited = await client.patch(url, json={"result": f"Fixed it {MARKER}", "difficulty": 4})

    assert edited.status_code == 200
    assert edited.json()["difficulty"] == 4
    revisions = (await client.get(f"{url}/revisions")).json()
    assert [r["source"] for r in revisions] == ["manual_edit"]
    assert revisions[0]["diff"]["difficulty"] == [3, 4]


async def test_the_approval_gate_returns_409_with_the_reason(client: AsyncClient) -> None:
    candidate_id, bare, items = await seeded(item_ids=[])
    pending = await seed_achievement(candidate_id, item_ids=items[:1], metrics=PENDING)

    no_evidence = await client.post(f"/api/achievements/{bare}/approve")
    unconfirmed = await client.post(f"/api/achievements/{pending}/approve")
    confirm_without_text = await client.post(
        f"/api/achievements/{pending}/confirm-metric", json={"index": 0, "mode": "edit"}
    )
    bad_index = await client.post(
        f"/api/achievements/{pending}/confirm-metric", json={"index": 7, "mode": "as_written"}
    )
    confirmed = await client.post(
        f"/api/achievements/{pending}/confirm-metric", json={"index": 0, "mode": "as_written"}
    )
    approved = await client.post(f"/api/achievements/{pending}/approve")

    assert (no_evidence.status_code, unconfirmed.status_code) == (409, 409)
    assert "no evidence link" in no_evidence.json()["detail"]
    assert "need confirmation" in unconfirmed.json()["detail"]
    assert confirm_without_text.status_code == 422
    assert bad_index.status_code == 400
    assert confirmed.json()["metrics"][0]["verified"] == "user"
    assert approved.json()["status"] == "approved"


async def test_status_routes_follow_the_state_table(client: AsyncClient) -> None:
    _, achievement_id, _ = await seeded()
    base = f"/api/achievements/{achievement_id}"

    assert (await client.post(f"{base}/archive")).status_code == 409
    assert (await client.post(f"{base}/reject")).json()["status"] == "rejected"
    assert (await client.post(f"{base}/approve")).status_code == 409
    assert (await client.post(f"{base}/restore")).json()["status"] == "draft"
    assert (await client.post(f"{base}/approve")).json()["status"] == "approved"
    assert (await client.post(f"{base}/unapprove")).json()["status"] == "draft"
    assert (await client.post(f"{base}/approve")).json()["status"] == "approved"
    assert (await client.post(f"{base}/archive")).json()["status"] == "archived"
    assert (await client.post(f"{base}/restore")).status_code == 409
    sources = [r["source"] for r in (await client.get(f"{base}/revisions")).json()]
    assert sources == ["status_change"] * 6


async def test_evidence_can_be_linked_and_unlinked(client: AsyncClient) -> None:
    _, achievement_id, items = await seeded()
    base = f"/api/achievements/{achievement_id}"

    linked = await client.post(f"{base}/evidence", json={"item_id": str(items[1]), "quote": "q"})
    duplicate = await client.post(f"{base}/evidence", json={"item_id": str(items[1])})
    unknown = await client.post(f"{base}/evidence", json={"item_id": str(uuid.uuid4())})
    unlinked = await client.delete(f"{base}/evidence/{items[1]}")
    again = await client.delete(f"{base}/evidence/{items[1]}")

    assert linked.status_code == 201
    assert {e["item_id"] for e in linked.json()["evidence"]} == {str(items[0]), str(items[1])}
    assert (duplicate.status_code, unknown.status_code) == (409, 404)
    assert unlinked.status_code == 200
    assert [e["item_id"] for e in unlinked.json()["evidence"]] == [str(items[0])]
    assert again.status_code == 404


async def test_merge_and_split_routes(client: AsyncClient) -> None:
    candidate_id, _, items = await seed_evidence_chunk(bodies=BODIES)
    first = await seed_achievement(candidate_id, item_ids=items[:2], title="First")
    second = await seed_achievement(candidate_id, item_ids=items[2:4], title="Second")

    too_few = await client.post("/api/achievements/merge", json={"ids": [str(first)]})
    merged = await client.post("/api/achievements/merge", json={"ids": [str(first), str(second)]})
    split = await client.post(
        f"/api/achievements/{merged.json()['id']}/split",
        json={"evidence_item_ids": [str(items[3])], "title": "Loader fix"},
    )
    bad_split = await client.post(
        f"/api/achievements/{merged.json()['id']}/split", json={"evidence_item_ids": []}
    )

    assert too_few.status_code == 422
    assert (merged.status_code, merged.json()["origin"]) == (201, "merged")
    assert (split.status_code, split.json()["title"]) == (201, "Loader fix")
    assert bad_split.status_code == 422
    archived = (await client.get("/api/achievements", params={"status": "archived"})).json()
    assert {a["title"] for a in archived} == {"First", "Second"}


async def test_revisions_are_paginated_with_a_total(client: AsyncClient) -> None:
    _, achievement_id, _ = await seeded()
    base = f"/api/achievements/{achievement_id}"
    for index in range(3):
        await client.patch(base, json={"title": f"Title {index}"})

    response = await client.get(f"{base}/revisions", params={"limit": 2})

    assert len(response.json()) == 2
    assert response.headers["x-total-count"] == "3"
    assert (await client.get(f"{base}/revisions", params={"limit": 500})).status_code == 422


async def test_bulk_approval_routes_preview_then_commit(client: AsyncClient) -> None:
    candidate_id, _, items = await seed_evidence_chunk(bodies=BODIES)
    clean = await seed_achievement(candidate_id, item_ids=items[:1], title="Clean")
    private = await seed_achievement(
        candidate_id, item_ids=items[1:2], title="Private", private=True
    )

    preview = (await client.get("/api/achievements/bulk-approve/eligible")).json()
    done = (
        await client.post(
            "/api/achievements/bulk-approve", json={"ids": [str(clean), str(private)]}
        )
    ).json()
    empty = await client.post("/api/achievements/bulk-approve", json={"ids": []})

    assert [item["title"] for item in preview["items"]] == ["Clean", "Private"]
    assert preview["count"] == 2
    assert done["approved"] == [str(clean), str(private)]
    assert done["skipped"] == []
    assert empty.status_code == 422


async def test_bulk_reject_and_archive_routes(client: AsyncClient) -> None:
    candidate_id, _, items = await seed_evidence_chunk(bodies=BODIES)
    draft = await seed_achievement(candidate_id, item_ids=items[:1], title="Draft")
    approved = await seed_achievement(
        candidate_id, item_ids=items[1:2], status="approved", title="Approved"
    )

    rejected = await client.post("/api/achievements/bulk-reject", json={"ids": [str(draft)]})
    archived = await client.post("/api/achievements/bulk-archive", json={"ids": [str(approved)]})
    wrong = await client.post("/api/achievements/bulk-reject", json={"ids": [str(approved)]})

    assert rejected.json()["done"] == [str(draft)]
    assert archived.json()["done"] == [str(approved)]
    assert wrong.json()["done"] == []
    assert len(wrong.json()["skipped"]) == 1


async def test_groups_route_counts_drafts_per_employer_and_repository(
    client: AsyncClient,
) -> None:
    candidate_id, _, items = await seed_evidence_chunk(bodies=[*BODIES, "Four"])
    acme = {"company": "Acme", "source": "scope"}
    await seed_achievement(candidate_id, item_ids=items[:1], title="A", employer_ref=acme)
    await seed_achievement(
        candidate_id, item_ids=[], title="B", employer_ref=acme, project_key="ada/other"
    )
    await seed_achievement(
        candidate_id,
        item_ids=items[1:2],
        title="C",
        employer_ref={"kind": "personal", "source": "scope"},
    )
    await seed_achievement(candidate_id, item_ids=items[2:3], title="D")

    groups = (await client.get("/api/achievements/groups")).json()["groups"]

    summary = [(g["kind"], g["label"], g["total"], g["eligible"]) for g in groups]
    assert summary[0] == ("employer", "Acme", 2, 1)
    assert set(summary[1:]) == {("personal", "Personal", 1, 1), ("unassigned", "No employer", 1, 1)}
    assert {(r["project_key"], r["total"]) for r in groups[0]["repositories"]} == {
        ("ada/engine", 1),
        ("ada/other", 1),
    }


async def test_list_filters_by_employer_personal_and_unassigned(client: AsyncClient) -> None:
    candidate_id, _, items = await seed_evidence_chunk(bodies=[*BODIES, "Four", "Five"])
    await seed_achievement(
        candidate_id,
        item_ids=items[:1],
        title="Acme",
        employer_ref={"company": "Acme", "source": "scope"},
    )
    await seed_achievement(
        candidate_id,
        item_ids=items[1:2],
        title="Other",
        employer_ref={"company": "Globex", "source": "scope"},
    )
    await seed_achievement(
        candidate_id,
        item_ids=items[2:3],
        title="Mine",
        employer_ref={"kind": "personal", "source": "scope"},
    )
    await seed_achievement(candidate_id, item_ids=items[3:4], title="Nobody")

    async def titles(**params: str) -> list[str]:
        response = await client.get("/api/achievements", params=params)
        return [row["title"] for row in response.json()]

    assert await titles(employer="Acme") == ["Acme"]
    assert await titles(employer_kind="personal") == ["Mine"]
    assert await titles(employer_kind="unassigned") == ["Nobody"]
    assert (await client.get("/api/achievements", params={"employer_kind": "x"})).status_code == 422


async def test_merge_proposals_route_lists_pairs_without_applying_them(client: AsyncClient) -> None:
    candidate_id, _, items = await seed_evidence_chunk(bodies=BODIES)
    for index in range(2):
        await seed_achievement(
            candidate_id, item_ids=items[index : index + 1], embedding=fake_vector("same")
        )

    proposals = await client.get("/api/achievements/merge-proposals")

    assert proposals.status_code == 200
    assert len(proposals.json()) == 1
    assert proposals.json()[0]["similarity"] == 1.0
    assert len((await client.get("/api/achievements")).json()) == 2


async def test_acknowledging_stale_evidence_over_http(client: AsyncClient) -> None:
    _, achievement_id, _ = await seeded(status="approved", stale=True)

    response = await client.post(f"/api/achievements/{achievement_id}/acknowledge")

    assert response.json()["evidence_stale_at"] is None
    approved = (await client.get("/api/achievements", params={"status": "approved"})).json()
    assert approved[0]["evidence_stale_at"] is None


async def test_review_text_never_reaches_the_logs(
    client: AsyncClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    _, achievement_id, _ = await seeded()
    base = f"/api/achievements/{achievement_id}"

    await client.patch(base, json={"action": f"Rewrote the loader {MARKER}"})
    await client.post(f"{base}/approve")
    await client.patch(base, json={"result": f"Faster {MARKER}"})

    assert MARKER not in "\n".join(record.getMessage() for record in caplog.records)
