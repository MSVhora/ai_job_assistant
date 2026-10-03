import uuid
from typing import Any

import pytest
from fakes import FakeResumeLLM, install_acompletion, seed_resume_world
from httpx import ASGITransport, AsyncClient

from app.core.config import get_settings
from app.main import app

pytestmark = pytest.mark.usefixtures("clean_tables")

BASE = "/api/resume-documents"


@pytest.fixture(autouse=True)
def _settings(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "gemini_api_key", "test-key")
    monkeypatch.setattr(settings, "llm_retry_attempts", 1)
    monkeypatch.setattr(settings, "llm_retry_base_delay_s", 0.0)


@pytest.fixture
async def client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        yield async_client


async def generate(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch, **extra: Any
) -> tuple[dict[str, Any], dict[str, Any], FakeResumeLLM]:
    world = await seed_resume_world(with_side_role=extra.pop("with_side_role", False))
    llm = FakeResumeLLM(
        jd={"must_haves": ["Snowflake"], "nice_to_haves": [], "keywords": ["Snowflake"]}
    )
    install_acompletion(monkeypatch, llm)
    response = await client.post(BASE, json={"profile_id": str(world["profile"]), **extra})
    assert response.status_code == 201, response.text
    return response.json(), world, llm


def acme(document: dict[str, Any]) -> dict[str, Any]:
    return next(job for job in document["content"]["work"] if job["company"] == "Acme Corp")


async def test_create_generates_content_and_returns_data_not_a_pdf(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    document, _, _ = await generate(
        client,
        monkeypatch,
        page_target=2,
        job_description="We run Snowflake",
        tailoring_strength="light",
    )

    assert document["jd_weight"] == pytest.approx(0.15)
    assert document["page_target"] == 2
    assert acme(document)["highlights"][0]["origin"] == "generated"
    assert acme(document)["highlights"][0]["id"]
    generation = document["generation"]
    assert generation["tailoring_strength"] == "light"
    assert [gap["requirement"] for gap in generation["gaps"]] == ["Snowflake"]
    assert generation["pool"][0]["written"] is True
    assert generation["usage"]["calls"] > 0
    assert document["layout"]["included_ids"]


@pytest.mark.parametrize(
    "extra",
    [
        {"job_description": "x", "match_id": str(uuid.uuid4())},
        {"tailoring_strength": "extreme"},
        {"job_description": "x" * 20_001},
        {"page_target": 5},
        {"job_description": ""},
    ],
)
async def test_invalid_creation_payloads_are_unprocessable(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch, extra: dict[str, Any]
) -> None:
    world = await seed_resume_world()
    install_acompletion(monkeypatch, FakeResumeLLM())

    response = await client.post(BASE, json={"profile_id": str(world["profile"]), **extra})

    assert response.status_code == 422


async def test_page_target_above_the_configured_maximum_is_a_400(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    world = await seed_resume_world()
    install_acompletion(monkeypatch, FakeResumeLLM())
    monkeypatch.setattr(get_settings(), "resume_max_pages", 2)

    response = await client.post(BASE, json={"profile_id": str(world["profile"]), "page_target": 3})

    assert (response.status_code, response.json()) == (
        400,
        {"detail": "page_target cannot exceed 2"},
    )


async def test_foreign_or_unknown_match_is_a_404(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    world = await seed_resume_world()
    install_acompletion(monkeypatch, FakeResumeLLM())

    response = await client.post(
        BASE, json={"profile_id": str(world["profile"]), "match_id": str(uuid.uuid4())}
    )

    assert response.status_code == 404


async def test_regenerate_whole_or_one_block_and_unknown_block(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    document, _, llm = await generate(client, monkeypatch)
    writes = llm.count("write")
    block_id = acme(document)["id"]

    whole = await client.post(f"{BASE}/{document['id']}/regenerate")
    one = await client.post(f"{BASE}/{document['id']}/regenerate", json={"block_id": block_id})
    missing = await client.post(f"{BASE}/{document['id']}/regenerate", json={"block_id": "nope"})

    assert (whole.status_code, one.status_code, missing.status_code) == (200, 200, 404)
    assert llm.count("write") == writes
    assert whole.json()["content"] == document["content"]


async def test_bullet_edit_pin_and_approve_anyway(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    document, _, _ = await generate(client, monkeypatch)
    bullet_id = acme(document)["highlights"][0]["id"]
    url = f"{BASE}/{document['id']}/bullets/{bullet_id}"

    edited = await client.patch(url, json={"text": "Cut the nightly import by 77%"})
    approved = await client.post(f"{url}/approve-anyway")
    again = await client.post(f"{url}/approve-anyway")
    missing = await client.patch(f"{BASE}/{document['id']}/bullets/missing", json={"pinned": True})
    extra = await client.patch(url, json={"score": 1})

    flagged = next(b for b in acme(edited.json())["highlights"] if b["id"] == bullet_id)
    assert (flagged["origin"], flagged["pinned"], flagged["check"]) == (
        "user_edited",
        True,
        "needs_review",
    )
    final = next(b for b in acme(approved.json())["highlights"] if b["id"] == bullet_id)
    assert (final["check"], final["approved_anyway"]) == ("passed", True)
    assert (again.status_code, missing.status_code, extra.status_code) == (400, 404, 422)


async def test_include_anyway_and_write_on_demand(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    document, world, _ = await generate(client, monkeypatch, with_side_role=True)
    omitted = document["generation"]["omitted_roles"][0]["block_id"]

    included = await client.post(f"{BASE}/{document['id']}/roles/{omitted}/include-anyway")
    unknown_role = await client.post(f"{BASE}/{document['id']}/roles/nope/include-anyway")
    unknown_achievement = await client.post(f"{BASE}/{document['id']}/write/{uuid.uuid4()}")
    already = await client.post(f"{BASE}/{document['id']}/write/{world['import']}")

    companies = [job["company"] for job in included.json()["content"]["work"]]
    assert "Side Gig" in companies
    assert (unknown_role.status_code, unknown_achievement.status_code) == (404, 404)
    assert already.status_code == 200


async def test_comment_lifecycle_through_the_api(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    document, _, llm = await generate(client, monkeypatch)
    target = {"section": "work", "block_id": acme(document)["id"]}
    url = f"{BASE}/{document['id']}/comments"

    created = await client.post(url, json={"target": target, "text": "tighten the wording"})
    comment_id = created.json()["comments"][0]["id"]
    edited = await client.patch(f"{url}/{comment_id}", json={"text": "tighten it more"})
    applied = await client.post(f"{BASE}/{document['id']}/apply-comments")
    removed = await client.delete(f"{url}/{comment_id}")
    gone = await client.delete(f"{url}/{comment_id}")
    bad = await client.post(url, json={"target": {**target, "block_id": "x"}, "text": "a"})
    wrong_section = await client.post(
        url, json={"target": {**target, "section": "skills"}, "text": "a"}
    )

    assert created.status_code == 201
    assert edited.json()["comments"][0]["text"] == "tighten it more"
    assert applied.json()["comments"][0]["status"] == "applied"
    assert llm.items("Faster nightly import")[-1]["instruction"] == "tighten it more"
    assert (removed.status_code, removed.json()["comments"]) == (200, [])
    assert (gone.status_code, bad.status_code, wrong_section.status_code) == (404, 422, 422)


async def test_unknown_documents_are_404_for_every_new_route(client: AsyncClient) -> None:
    missing = uuid.uuid4()
    calls = [
        client.post(f"{BASE}/{missing}/regenerate"),
        client.patch(f"{BASE}/{missing}/bullets/x", json={"pinned": True}),
        client.post(f"{BASE}/{missing}/bullets/x/approve-anyway"),
        client.post(f"{BASE}/{missing}/roles/x/include-anyway"),
        client.post(f"{BASE}/{missing}/write/{uuid.uuid4()}"),
        client.post(f"{BASE}/{missing}/apply-comments"),
        client.delete(f"{BASE}/{missing}/comments/x"),
    ]

    statuses = [(await call).status_code for call in calls]

    assert statuses == [404] * len(calls)


async def test_put_is_not_allowed_on_the_new_routes(client: AsyncClient) -> None:
    response = await client.put(f"{BASE}/{uuid.uuid4()}/comments/x", json={})

    assert response.status_code == 405
