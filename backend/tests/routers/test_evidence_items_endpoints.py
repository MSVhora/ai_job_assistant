import logging
import uuid

import pytest
from fakes import seed_profile_light
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import session_factory
from app.main import app
from app.models import Candidate, EvidenceItem, EvidenceItemStatus, EvidenceKind

pytestmark = pytest.mark.usefixtures("clean_tables")

MARKER = "zebra-marker-7781"


@pytest.fixture(autouse=True)
def _no_llm_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "gemini_api_key", None)


@pytest.fixture
async def client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        yield async_client


async def post_note(client: AsyncClient, body: str = "Moved 40 services", **extra: str) -> dict:
    response = await client.post("/api/evidence/notes", json={"body": body, **extra})
    assert response.status_code == 201, response.text
    return response.json()


async def seed_items(*specs: tuple[str, str, str, bool]) -> list[uuid.UUID]:
    async with session_factory() as session:
        candidate = Candidate()
        session.add(candidate)
        await session.flush()
        ids: list[uuid.UUID] = []
        for status, external_id, project, private in specs:
            item = EvidenceItem(
                candidate_id=candidate.id,
                kind=EvidenceKind.commit,
                external_id=external_id,
                project_key=project,
                body=f"Change {external_id}",
                status=EvidenceItemStatus(status),
                filter_reason="merge_commit" if status == "filtered" else None,
                is_private=private,
                content_hash=external_id,
            )
            session.add(item)
            await session.flush()
            ids.append(item.id)
        await session.commit()
        return ids


async def test_creating_a_note_chunks_it_in_the_background(client: AsyncClient) -> None:
    created = await post_note(client, title="Payments", body="Moved 40 services to the ledger.")

    summary = (await client.get("/api/evidence/chunks/summary")).json()

    assert created["kind"] == "note"
    assert created["project_key"] == "note:payments"
    assert summary["chunks"] == 1
    assert summary["by_kind"] == {"note": 1}
    assert summary["pending_embedding"] == 1


async def test_duplicate_note_is_409_and_invalid_notes_are_422(client: AsyncClient) -> None:
    await post_note(client)

    duplicate = await client.post("/api/evidence/notes", json={"body": "Moved 40 services"})
    empty = await client.post("/api/evidence/notes", json={"body": ""})
    huge = await client.post("/api/evidence/notes", json={"body": "x" * 20_001})

    assert duplicate.status_code == 409
    assert (empty.status_code, huge.status_code) == (422, 422)


async def test_note_list_reports_total_and_respects_limit(client: AsyncClient) -> None:
    for index in range(3):
        await post_note(client, body=f"Note number {index}")

    response = await client.get("/api/evidence/notes", params={"limit": 2})

    assert len(response.json()) == 2
    assert response.headers["x-total-count"] == "3"
    assert (await client.get("/api/evidence/notes", params={"limit": 500})).status_code == 422


async def test_patching_a_note_returns_a_new_version_and_hides_the_old(client: AsyncClient) -> None:
    original = await post_note(client, body="First draft")

    updated = await client.patch(
        f"/api/evidence/notes/{original['id']}", json={"body": "Second draft"}
    )

    assert updated.status_code == 200
    assert updated.json()["id"] != original["id"]
    listed = [note["body"] for note in (await client.get("/api/evidence/notes")).json()]
    assert listed == ["Second draft"]
    old = (
        await client.get("/api/evidence/items", params={"status": "excluded", "kind": "note"})
    ).json()
    assert [item["id"] for item in old] == [original["id"]]


async def test_patching_a_note_needs_a_change(client: AsyncClient) -> None:
    original = await post_note(client)

    response = await client.patch(f"/api/evidence/notes/{original['id']}", json={})

    assert response.status_code == 422


async def test_deleting_a_note_is_204_then_404(client: AsyncClient) -> None:
    original = await post_note(client)

    first = await client.delete(f"/api/evidence/notes/{original['id']}")
    second = await client.delete(f"/api/evidence/notes/{original['id']}")

    assert (first.status_code, second.status_code) == (204, 404)
    assert (await client.get("/api/evidence/notes")).json() == []
    assert (await client.get("/api/evidence/chunks/summary")).json()["chunks"] == 0


async def test_links_validate_the_scheme_and_conflict_on_duplicates(client: AsyncClient) -> None:
    ok = await client.post(
        "/api/evidence/links", json={"url": "https://example.com/talk", "title": "Talk"}
    )
    again = await client.post("/api/evidence/links", json={"url": "https://example.com/talk"})
    bad = await client.post("/api/evidence/links", json={"url": "javascript:alert(1)"})

    assert ok.status_code == 201
    assert ok.json()["meta"] == {"url_only": True}
    assert again.status_code == 409
    assert bad.status_code == 422
    assert (await client.get("/api/evidence/chunks/summary")).json()["chunks"] == 0


async def test_resume_ingest_creates_lines_and_chunks_them(client: AsyncClient) -> None:
    profile_id = await seed_profile_light()

    first = await client.post("/api/evidence/resume/ingest", json={"profile_id": str(profile_id)})
    second = await client.post("/api/evidence/resume/ingest", json={"profile_id": str(profile_id)})

    assert first.json() == {"created": 3, "unchanged": 0, "excluded": 0}
    assert second.json() == {"created": 0, "unchanged": 3, "excluded": 0}
    summary = (await client.get("/api/evidence/chunks/summary")).json()
    assert summary["by_kind"] == {"resume_entry": 2}


async def test_resume_ingest_unknown_profile_is_404(client: AsyncClient) -> None:
    await seed_profile_light()

    response = await client.post(
        "/api/evidence/resume/ingest", json={"profile_id": str(uuid.uuid4())}
    )

    assert response.status_code == 404


async def test_items_default_to_kept_and_filter_by_status_kind_project_and_privacy(
    client: AsyncClient,
) -> None:
    await seed_items(
        ("kept", "a", "ada/open", False),
        ("kept", "b", "ada/secret", True),
        ("filtered", "c", "ada/open", False),
        ("excluded", "d", "ada/open", False),
    )

    default = (await client.get("/api/evidence/items")).json()
    filtered = (await client.get("/api/evidence/items", params={"status": "filtered"})).json()
    private = (await client.get("/api/evidence/items", params={"is_private": "true"})).json()
    project = (await client.get("/api/evidence/items", params={"project_key": "ada/open"})).json()
    kind = (await client.get("/api/evidence/items", params={"kind": "issue"})).json()

    assert sorted(item["external_id"] for item in default) == ["a", "b"]
    assert [item["external_id"] for item in filtered] == ["c"]
    assert filtered[0]["filter_reason"] == "merge_commit"
    assert [item["external_id"] for item in private] == ["b"]
    assert [item["external_id"] for item in project] == ["a"]
    assert kind == []
    assert (await client.get("/api/evidence/items", params={"status": "bogus"})).status_code == 422


async def test_items_are_paginated_with_a_total(client: AsyncClient) -> None:
    await seed_items(*[("kept", f"c{i}", "ada/open", False) for i in range(5)])

    response = await client.get("/api/evidence/items", params={"limit": 2, "offset": 1})

    assert len(response.json()) == 2
    assert response.headers["x-total-count"] == "5"
    assert (await client.get("/api/evidence/items", params={"limit": 201})).status_code == 422


async def test_a_filtered_item_can_be_restored_and_a_kept_one_excluded(client: AsyncClient) -> None:
    filtered_id, kept_id = await seed_items(
        ("filtered", "merge", "ada/open", False), ("kept", "real", "ada/open", False)
    )

    restored = await client.patch(f"/api/evidence/items/{filtered_id}", json={"status": "kept"})
    excluded = await client.patch(f"/api/evidence/items/{kept_id}", json={"status": "excluded"})

    assert restored.status_code == 200
    assert (restored.json()["status"], restored.json()["filter_reason"]) == ("kept", None)
    assert excluded.json()["status"] == "excluded"
    kept = (await client.get("/api/evidence/items")).json()
    assert [item["external_id"] for item in kept] == ["merge"]
    assert (await client.get("/api/evidence/chunks/summary")).json()["by_kind"] == {
        "commit_cluster": 1
    }


async def test_item_updates_reject_bad_status_and_unknown_ids(client: AsyncClient) -> None:
    (item_id,) = await seed_items(("kept", "a", "ada/open", False))

    bad = await client.patch(f"/api/evidence/items/{item_id}", json={"status": "filtered"})
    missing = await client.patch(f"/api/evidence/items/{uuid.uuid4()}", json={"status": "kept"})

    assert (bad.status_code, missing.status_code) == (422, 404)


async def test_an_item_of_another_candidate_is_a_404(client: AsyncClient) -> None:
    await seed_items(("kept", "mine", "ada/open", False))
    async with session_factory() as session:
        stranger = Candidate()
        session.add(stranger)
        await session.flush()
        foreign = EvidenceItem(
            candidate_id=stranger.id,
            kind=EvidenceKind.note,
            external_id="theirs",
            body="not yours",
            content_hash="t",
        )
        session.add(foreign)
        await session.commit()
        foreign_id = foreign.id

    response = await client.patch(f"/api/evidence/items/{foreign_id}", json={"status": "excluded"})

    assert response.status_code == 404
    async with session_factory() as session:
        stored = (
            await session.execute(select(EvidenceItem).where(EvidenceItem.id == foreign_id))
        ).scalar_one()
    assert stored.status is EvidenceItemStatus.kept


async def test_note_text_never_reaches_the_logs(
    client: AsyncClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)

    await post_note(client, body=f"Confidential detail {MARKER}")
    await client.get("/api/evidence/chunks/summary")

    assert MARKER not in "\n".join(record.getMessage() for record in caplog.records)
