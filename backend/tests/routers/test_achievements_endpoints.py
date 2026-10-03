import json
import logging
import uuid
from typing import Any

import pytest
from fakes import ProviderError, install_acompletion, llm_response, seed_evidence_chunk
from httpx import ASGITransport, AsyncClient

from app.core.config import get_settings
from app.main import app

pytestmark = pytest.mark.usefixtures("clean_tables")

MARKER = "quokka-marker-5512"
BODIES = [
    f"Cut the nightly import from 42 minutes to 9 minutes by batching writes {MARKER}",
    "Add retry budget for the loader",
]
ACHIEVEMENT = {
    "title": "Faster nightly import",
    "situation": "The import was slow.",
    "task": "Reduce runtime.",
    "action": "Batched writes.",
    "result": "Runtime fell.",
    "result_quote": "from 42 minutes to 9 minutes",
    "metrics": [
        {
            "text": "42 minutes to 9 minutes",
            "source_quote": "from 42 minutes to 9 minutes",
            "evidence_ids": ["E1"],
        }
    ],
    "skills": ["python"],
    "impact_type": "performance",
    "difficulty": 3,
    "evidence_ids": ["E1"],
}


@pytest.fixture(autouse=True)
def _key(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "gemini_api_key", "test-key")
    monkeypatch.setattr(settings, "llm_retry_attempts", 1)
    monkeypatch.setattr(settings, "llm_retry_base_delay_s", 0.0)


@pytest.fixture
async def client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        yield async_client


def provider(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    payload = json.dumps({"achievements": [ACHIEVEMENT]})
    return install_acompletion(monkeypatch, lambda **_: llm_response(payload))


async def test_estimate_then_confirm_runs_the_extraction_and_lists_drafts(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider(monkeypatch)
    await seed_evidence_chunk(bodies=BODIES)

    estimated = (await client.post("/api/evidence/extract/estimate")).json()
    started = await client.post(
        "/api/evidence/extract", json={"confirmed_estimate_id": estimated["estimate_id"]}
    )

    assert estimated["chunks_to_extract"] == 1
    assert estimated["llm_cost"]["usd"] is not None
    assert estimated["private_chunks"] == 0
    assert started.status_code == 202
    run = (await client.get(f"/api/evidence/extract/runs/{started.json()['run_id']}")).json()
    assert run["status"] == "succeeded"
    assert run["progress"]["achievements"] == 1
    assert run["estimate"]["estimate_id"] == estimated["estimate_id"]
    listed = await client.get("/api/achievements")
    (draft,) = listed.json()
    assert draft["status"] == "draft"
    assert draft["skills"] == ["Python"]
    assert draft["metrics"][0]["verified"] == "evidence"
    assert [link["role"] for link in draft["evidence"]] == ["primary"]
    assert listed.headers["x-total-count"] == "1"


async def test_the_list_filters_by_status_and_is_paginated(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider(monkeypatch)
    await seed_evidence_chunk(bodies=BODIES)
    estimated = (await client.post("/api/evidence/extract/estimate")).json()
    await client.post(
        "/api/evidence/extract", json={"confirmed_estimate_id": estimated["estimate_id"]}
    )

    approved = await client.get("/api/achievements", params={"status": "approved"})
    paged = await client.get("/api/achievements", params={"limit": 1, "offset": 5})

    assert approved.json() == []
    assert approved.headers["x-total-count"] == "0"
    assert paged.json() == []
    assert paged.headers["x-total-count"] == "1"
    assert (await client.get("/api/achievements", params={"status": "bogus"})).status_code == 422
    assert (await client.get("/api/achievements", params={"limit": 500})).status_code == 422


async def test_a_stale_estimate_is_refused_with_409(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider(monkeypatch)
    candidate_id, _, _ = await seed_evidence_chunk(bodies=BODIES)
    estimated = (await client.post("/api/evidence/extract/estimate")).json()
    await seed_evidence_chunk(bodies=["New"], project_key="ada/new", candidate_id=candidate_id)

    response = await client.post(
        "/api/evidence/extract", json={"confirmed_estimate_id": estimated["estimate_id"]}
    )

    assert response.status_code == 409
    assert "estimate again" in response.json()["detail"]


async def test_nothing_to_extract_is_400_and_a_malformed_id_is_422(client: AsyncClient) -> None:
    empty = await client.post("/api/evidence/extract/estimate")
    refused = await client.post(
        "/api/evidence/extract", json={"confirmed_estimate_id": empty.json()["estimate_id"]}
    )
    malformed = await client.post("/api/evidence/extract", json={"confirmed_estimate_id": "x"})

    assert empty.json()["chunks_to_extract"] == 0
    assert refused.status_code == 400
    assert malformed.status_code == 422


async def test_a_missing_llm_key_is_503(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "gemini_api_key", None)
    await seed_evidence_chunk(bodies=BODIES)
    estimated = (await client.post("/api/evidence/extract/estimate")).json()

    response = await client.post(
        "/api/evidence/extract", json={"confirmed_estimate_id": estimated["estimate_id"]}
    )

    assert response.status_code == 503


async def test_unknown_runs_are_404(client: AsyncClient) -> None:
    response = await client.get(f"/api/evidence/extract/runs/{uuid.uuid4()}")

    assert response.status_code == 404


async def test_a_failed_run_reports_its_error_without_provider_details(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    install_acompletion(monkeypatch, lambda **_: ProviderError(400))
    await seed_evidence_chunk(bodies=BODIES)
    estimated = (await client.post("/api/evidence/extract/estimate")).json()

    started = await client.post(
        "/api/evidence/extract", json={"confirmed_estimate_id": estimated["estimate_id"]}
    )

    run = (await client.get(f"/api/evidence/extract/runs/{started.json()['run_id']}")).json()
    assert run["status"] == "failed"
    assert "provider error" not in json.dumps(run)


async def test_chunk_text_and_prompts_never_reach_the_logs(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    calls = provider(monkeypatch)
    await seed_evidence_chunk(bodies=BODIES)
    estimated = (await client.post("/api/evidence/extract/estimate")).json()

    await client.post(
        "/api/evidence/extract", json={"confirmed_estimate_id": estimated["estimate_id"]}
    )

    assert calls, "the run must have used the LLM wrapper"
    logged = "\n".join(record.getMessage() for record in caplog.records)
    assert MARKER not in logged
    for call in calls:
        for message in call["messages"]:
            assert message["content"][:80] not in logged
