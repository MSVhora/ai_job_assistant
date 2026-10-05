import uuid

import pytest
from fakes import (
    FakeAgentLLM,
    install_acompletion,
    install_agent_embeddings,
    new_agent_session,
    seed_resume_world,
)
from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import session_factory
from app.models import AgentSession
from app.services import agent
from app.services.agent_memory import fallback_summary

pytestmark = pytest.mark.usefixtures("clean_tables")

QUESTIONS = [
    "Tell me about a time you made something faster: Faster nightly import",
    "Tell me about a time you improved reliability: Retry budget for the loader",
    "Tell me about a time you shipped a tool: Docs generator",
]


@pytest.fixture(autouse=True)
def _settings(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "gemini_api_key", "test-key")
    monkeypatch.setattr(settings, "llm_retry_attempts", 1)
    monkeypatch.setattr(settings, "llm_retry_base_delay_s", 0.0)
    monkeypatch.setattr(settings, "agent_history_turns", 1)


async def ask(session_id: uuid.UUID, question: str) -> None:
    async with session_factory() as session:
        await agent.answer(session, session_id, question)
        await session.commit()


async def stored(session_id: uuid.UUID) -> AgentSession:
    async with session_factory() as session:
        return (
            await session.execute(select(AgentSession).where(AgentSession.id == session_id))
        ).scalar_one()


async def start(monkeypatch: pytest.MonkeyPatch, llm: FakeAgentLLM) -> uuid.UUID:
    install_agent_embeddings(monkeypatch)
    install_acompletion(monkeypatch, llm)
    world = await seed_resume_world(embeddings=True)
    return await new_agent_session(world["profile"])


async def test_the_window_holds_the_last_turns_and_older_ones_fold_into_the_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    llm = FakeAgentLLM()
    session_id = await start(monkeypatch, llm)

    await ask(session_id, QUESTIONS[0])
    assert (await stored(session_id)).summary is None
    assert llm.count("summary") == 0

    await ask(session_id, QUESTIONS[1])
    await ask(session_id, QUESTIONS[2])

    row = await stored(session_id)
    assert row.summary == "The candidate practised a behavioural question."
    assert row.summarized_through == 4
    assert llm.count("summary") == 2
    last = llm.prompts("answer")[2]
    assert QUESTIONS[1] in last
    assert QUESTIONS[0] not in last
    assert "The candidate practised a behavioural question." in last


async def test_history_in_the_prompt_has_no_citation_markers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    llm = FakeAgentLLM()
    session_id = await start(monkeypatch, llm)

    await ask(session_id, QUESTIONS[0])
    await ask(session_id, QUESTIONS[1])

    recent = llm.prompts("answer")[1].split("<<<RECENT TURNS")[1].split("RECENT TURNS>>>")[0]
    assert "Coach: I worked on faster nightly import" in recent
    assert "[A1]" not in recent


async def test_a_summary_that_adds_a_fact_is_replaced_by_the_question_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    llm = FakeAgentLLM(summary="The candidate saved $7 million by rewriting everything in Rust.")
    session_id = await start(monkeypatch, llm)

    for question in QUESTIONS[:2]:
        await ask(session_id, question)

    summary = (await stored(session_id)).summary or ""
    assert "Rust" not in summary
    assert "7" not in summary
    assert QUESTIONS[0][:40] in summary


async def test_the_session_reloads_in_order(monkeypatch: pytest.MonkeyPatch) -> None:
    session_id = await start(monkeypatch, FakeAgentLLM())

    for question in QUESTIONS[:2]:
        await ask(session_id, question)

    async with session_factory() as session:
        loaded = await agent.get_session(session, session_id)
    assert [m.role for m in loaded.messages] == ["user", "assistant", "user", "assistant"]
    assert [m.content for m in loaded.messages if m.role == "user"] == QUESTIONS[:2]


async def test_a_follow_up_is_rewritten_before_retrieval(monkeypatch: pytest.MonkeyPatch) -> None:
    llm = FakeAgentLLM(rewrite=lambda q: f"{q} (about the Faster nightly import)")
    session_id = await start(monkeypatch, llm)
    await ask(session_id, QUESTIONS[0])

    await ask(session_id, "Why did you choose that?")

    assert llm.count("rewrite") == 1
    assert "Candidate: " + QUESTIONS[0][:30] in llm.prompts("rewrite")[0]


async def test_a_first_question_is_never_rewritten(monkeypatch: pytest.MonkeyPatch) -> None:
    llm = FakeAgentLLM()
    session_id = await start(monkeypatch, llm)

    await ask(session_id, "Why did you choose that? Faster nightly import")

    assert llm.count("rewrite") == 0


def test_the_fallback_summary_lists_questions_only() -> None:
    summary = fallback_summary("", [("Candidate", "Why Kafka?"), ("Coach", "Because of volume.")])

    assert "Why Kafka?" in summary
    assert "volume" not in summary
