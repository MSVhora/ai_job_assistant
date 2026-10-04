import json
from typing import Any

import pytest
from fakes import ProviderError, install_acompletion, llm_response, seed_employers
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import session_factory
from app.main import app
from app.models import Candidate

pytestmark = pytest.mark.usefixtures("clean_tables")

ESTIMATE = "/api/evidence/employers/merge-suggestions/estimate"
SUGGEST = "/api/evidence/employers/merge-suggestions"
SAMSUNG_GROUP = {
    "canonical": "Samsung",
    "members": ["Samsung", "Samsung Research Institute"],
    "reason": "Same company, one is its research arm.",
}


@pytest.fixture(autouse=True)
def _llm(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "gemini_api_key", "test-key")
    monkeypatch.setattr(settings, "llm_retry_attempts", 1)
    monkeypatch.setattr(settings, "llm_retry_base_delay_s", 0.0)
    monkeypatch.setattr(settings, "llm_price_in_per_mtok", 1.0)
    monkeypatch.setattr(settings, "llm_price_out_per_mtok", 2.0)


@pytest.fixture
async def client() -> AsyncClient:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as c:
        yield c


def answer(*groups: dict[str, Any]) -> Any:
    return lambda **_: llm_response(json.dumps({"groups": list(groups)}))


async def test_estimating_prices_the_prompt_without_calling_the_provider(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    await seed_employers("Samsung", "Samsung Research Institute", "Acme Corp")
    calls = install_acompletion(monkeypatch, answer())

    response = await client.post(ESTIMATE)

    body = response.json()
    assert response.status_code == 200
    assert calls == []
    assert body["basis"] == "configured_prices"
    assert body["prompt_tokens"] > 0
    assert body["usd"] == pytest.approx(
        (body["prompt_tokens"] * 1.0 + body["completion_tokens"] * 2.0) / 1_000_000
    )


async def test_suggestions_group_names_the_model_says_belong_together(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    await seed_employers("Samsung", "Samsung Research Institute", "Acme Corp")
    calls = install_acompletion(monkeypatch, answer(SAMSUNG_GROUP))

    response = await client.post(SUGGEST)

    body = response.json()
    assert response.status_code == 200
    assert body["suggestions"] == [SAMSUNG_GROUP]
    assert body["cached"] is False
    assert body["cost_usd"] is not None
    assert len(calls) == 1
    prompt = calls[0]["messages"][-1]["content"]
    assert all(name in prompt for name in ("Samsung", "Samsung Research Institute", "Acme Corp"))
    assert "untrusted data" in prompt


async def test_suggestions_are_never_stored_and_a_repeat_is_served_from_the_cache(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    await seed_employers("Samsung", "Samsung Research Institute")
    calls = install_acompletion(monkeypatch, answer(SAMSUNG_GROUP))
    first = (await client.post(SUGGEST)).json()

    estimate = (await client.post(ESTIMATE)).json()
    second = (await client.post(SUGGEST)).json()

    assert second["suggestions"] == first["suggestions"]
    assert second["cached"] is True
    assert (estimate["prompt_tokens"], estimate["completion_tokens"], estimate["usd"]) == (0, 0, 0)
    assert len(calls) == 1
    async with session_factory() as session:
        assert (await session.execute(select(Candidate.employer_merges))).scalar_one() is None
    options = (await client.get("/api/evidence/employers")).json()
    assert [o["company"] for o in options if o["kind"] == "experience"] == [
        "Samsung Research Institute",
        "Samsung",
    ]


async def test_invented_overlapping_and_single_name_groups_are_dropped(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    await seed_employers("Samsung", "Samsung Research Institute", "Acme Corp")
    install_acompletion(
        monkeypatch,
        answer(
            {
                "canonical": "samsung",
                "members": ["SAMSUNG", "samsung research institute", "Nonexistent Corp"],
            },
            {"canonical": "Acme Corp", "members": ["Acme Corp", "Samsung"]},
            {"canonical": "Acme Corp", "members": ["Acme Corp"]},
            {"canonical": "Invented", "members": ["Invented", "Acme Corp"]},
        ),
    )

    suggestions = (await client.post(SUGGEST)).json()["suggestions"]

    assert suggestions == [
        {
            "canonical": "Samsung",
            "members": ["Samsung", "Samsung Research Institute"],
            "reason": "",
        }
    ]


async def test_an_empty_answer_is_a_valid_no_merges_result(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    await seed_employers("Samsung", "Acme Corp")
    install_acompletion(monkeypatch, answer())

    response = await client.post(SUGGEST)

    assert response.status_code == 200
    assert response.json()["suggestions"] == []


async def test_already_merged_names_are_compared_once(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    await seed_employers("Samsung", "Samsung Research Institute", "Acme Corp")
    await client.post(
        "/api/evidence/employers/merges",
        json={"canonical": "Samsung", "members": ["Samsung Research Institute"]},
    )
    calls = install_acompletion(monkeypatch, answer())

    await client.post(SUGGEST)

    prompt = calls[0]["messages"][-1]["content"]
    assert "Samsung Research Institute" not in prompt
    assert "- Samsung\n" in prompt


@pytest.mark.parametrize("path", [ESTIMATE, SUGGEST])
async def test_one_employer_is_nothing_to_compare(client: AsyncClient, path: str) -> None:
    await seed_employers("Samsung")

    response = await client.post(path)

    assert response.status_code == 400
    assert "at least two different employers" in response.json()["detail"]


@pytest.mark.parametrize("path", [ESTIMATE, SUGGEST])
async def test_a_missing_llm_key_is_503(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch, path: str
) -> None:
    await seed_employers("Samsung", "Acme Corp")
    monkeypatch.setattr(get_settings(), "gemini_api_key", None)

    assert (await client.post(path)).status_code == 503


async def test_a_provider_failure_is_a_502_without_internals(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    await seed_employers("Samsung", "Acme Corp")
    install_acompletion(monkeypatch, lambda **_: ProviderError(500))

    response = await client.post(SUGGEST)

    assert response.status_code == 502
    assert "Traceback" not in response.text
