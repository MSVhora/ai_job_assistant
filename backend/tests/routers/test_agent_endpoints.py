import uuid

import pytest
from fakes import (
    FakeAgentLLM,
    ProviderError,
    install_acompletion,
    install_agent_embeddings,
    seed_match,
    seed_resume_world,
)
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import session_factory
from app.main import app
from app.models import AgentMessage, Profile

pytestmark = pytest.mark.usefixtures("clean_tables")

BASE = "/api/agent/sessions"
QUESTION = "Tell me about a time you made something faster: Faster nightly import"


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


async def messages_in_db() -> list[AgentMessage]:
    async with session_factory() as session:
        result = await session.execute(select(AgentMessage).order_by(AgentMessage.created_at))
        return list(result.scalars().all())


async def create(client: AsyncClient, profile_id: uuid.UUID, **extra: object) -> str:
    response = await client.post(BASE, json={"profile_id": str(profile_id), **extra})
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def test_a_session_round_trips_with_its_messages(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    install_agent_embeddings(monkeypatch)
    install_acompletion(monkeypatch, FakeAgentLLM())
    world = await seed_resume_world(embeddings=True)
    session_id = await create(client, world["profile"], style_notes="Be brief")

    sent = await client.post(f"{BASE}/{session_id}/messages", json={"content": QUESTION})
    loaded = await client.get(f"{BASE}/{session_id}")

    assert sent.status_code == 200, sent.text
    turn = sent.json()
    assert turn["assistant_message"]["citations"][0]["marker"] == "A1"
    assert turn["assistant_message"]["grounding"]["status"] == "grounded"
    body = loaded.json()
    assert body["style_notes"] == "Be brief"
    assert [m["role"] for m in body["messages"]] == ["user", "assistant"]
    assert body["messages"][1]["content"] == turn["assistant_message"]["content"]


async def test_templated_replies_are_persisted_too(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    install_acompletion(monkeypatch, FakeAgentLLM())
    world = await seed_resume_world(embeddings=True)
    session_id = await create(client, world["profile"])

    response = await client.post(
        f"{BASE}/{session_id}/messages", json={"content": "Tell me a joke"}
    )

    assert response.json()["assistant_message"]["question_type"] == "out_of_scope"
    assert [m.role.value for m in await messages_in_db()] == ["user", "assistant"]


async def test_a_failed_model_call_keeps_the_question_and_says_so(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    install_agent_embeddings(monkeypatch)
    install_acompletion(monkeypatch, lambda **_: ProviderError(400))
    world = await seed_resume_world(embeddings=True)
    session_id = await create(client, world["profile"])

    response = await client.post(f"{BASE}/{session_id}/messages", json={"content": QUESTION})

    assert response.status_code == 200
    assert response.json()["assistant_message"]["grounding"]["error"] is True
    stored = await messages_in_db()
    assert (stored[0].role.value, stored[0].content) == ("user", QUESTION)
    assert len(stored) == 2


async def test_a_pinned_match_must_belong_to_the_profile(client: AsyncClient) -> None:
    world = await seed_resume_world()
    async with session_factory() as session:
        other = Profile(
            candidate_id=world["candidate"], name="Other", structured_profile={"contact": {}}
        )
        session.add(other)
        await session.flush()
        other_id = other.id
        await session.commit()
    foreign_match = await seed_match(other_id)
    own_match = await seed_match(world["profile"], description="Another posting body")

    refused = await client.post(
        BASE, json={"profile_id": str(world["profile"]), "match_id": str(foreign_match)}
    )
    accepted = await client.post(
        BASE, json={"profile_id": str(world["profile"]), "match_id": str(own_match)}
    )

    assert refused.status_code == 404
    assert accepted.status_code == 201
    assert accepted.json()["match_id"] == str(own_match)


async def test_unknown_ids_are_404(client: AsyncClient) -> None:
    world = await seed_resume_world()
    unknown = uuid.uuid4()

    assert (await client.post(BASE, json={"profile_id": str(unknown)})).status_code == 404
    assert (await client.get(f"{BASE}/{unknown}")).status_code == 404
    assert (await client.delete(f"{BASE}/{unknown}")).status_code == 404
    posted = await client.post(f"{BASE}/{unknown}/messages", json={"content": "Hi there"})
    assert posted.status_code == 404
    assert world["profile"]


async def test_an_empty_or_oversized_question_is_422(client: AsyncClient) -> None:
    world = await seed_resume_world()
    session_id = await create(client, world["profile"])

    empty = await client.post(f"{BASE}/{session_id}/messages", json={"content": ""})
    huge = await client.post(f"{BASE}/{session_id}/messages", json={"content": "x" * 2001})

    assert empty.status_code == 422
    assert huge.status_code == 422


async def test_sessions_list_is_bounded_and_counted_then_delete_removes_messages(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    install_acompletion(monkeypatch, FakeAgentLLM())
    world = await seed_resume_world()
    first = await create(client, world["profile"])
    await create(client, world["profile"])
    await client.post(f"{BASE}/{first}/messages", json={"content": "Tell me a joke"})

    listed = await client.get(BASE, params={"profile_id": str(world["profile"]), "limit": 1})
    deleted = await client.delete(f"{BASE}/{first}")
    after = await client.get(f"{BASE}/{first}")

    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert listed.headers["X-Total-Count"] == "2"
    assert listed.json()[0]["id"] == first
    assert deleted.status_code == 204
    assert after.status_code == 404
    assert await messages_in_db() == []
