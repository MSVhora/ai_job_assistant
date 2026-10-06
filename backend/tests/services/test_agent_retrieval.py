import uuid
from typing import Any

import pytest
from fakes import (
    WORLD_ACHIEVEMENTS,
    fake_vector,
    install_agent_embeddings,
    seed_achievement,
    seed_evidence_chunk,
    seed_resume_world,
)
from sqlalchemy import update

from app.core.config import get_settings
from app.core.db import session_factory
from app.models import EvidenceChunk
from app.services.agent_retrieval import Retrieval, retrieve

pytestmark = pytest.mark.usefixtures("clean_tables")


@pytest.fixture(autouse=True)
def _settings(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "gemini_api_key", "test-key")
    monkeypatch.setattr(settings, "llm_retry_attempts", 1)
    monkeypatch.setattr(settings, "llm_retry_base_delay_s", 0.0)


async def run(candidate_id: uuid.UUID, query: str) -> Retrieval:
    async with session_factory() as session:
        return await retrieve(session, candidate_id, query)


def titles(result: Retrieval) -> list[str]:
    return [
        block.text.split("\n", 1)[0].removeprefix("Title: ")
        for block in result.blocks
        if block.kind == "achievement"
    ]


@pytest.mark.parametrize(
    "spec", WORLD_ACHIEVEMENTS, ids=[spec["key"] for spec in WORLD_ACHIEVEMENTS]
)
async def test_the_matching_achievement_ranks_first(
    monkeypatch: pytest.MonkeyPatch, spec: dict[str, Any]
) -> None:
    install_agent_embeddings(monkeypatch)
    world = await seed_resume_world(embeddings=True)

    result = await run(world["candidate"], f"Tell me about {spec['title']}")

    assert titles(result)[0] == spec["title"]
    assert result.blocks[0].marker == "A1"
    assert result.best_score >= get_settings().agent_min_retrieval_score


async def test_only_approved_achievements_are_retrieved(monkeypatch: pytest.MonkeyPatch) -> None:
    install_agent_embeddings(monkeypatch)
    world = await seed_resume_world(embeddings=True)
    for status in ("draft", "rejected", "archived"):
        await seed_achievement(
            world["candidate"],
            status=status,
            title="Faster nightly import",
            embedding=fake_vector("Faster nightly import"),
        )

    result = await run(world["candidate"], "Faster nightly import")

    assert titles(result).count("Faster nightly import") == 1
    assert len(result.achievement_ids) == len(set(result.achievement_ids))
    assert result.approved == len(WORLD_ACHIEVEMENTS)


async def test_a_project_named_in_the_question_narrows_the_search(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_agent_embeddings(monkeypatch)
    world = await seed_resume_world(embeddings=True)

    result = await run(
        world["candidate"], "What did you build in pipeline-kit, the Streaming toolkit?"
    )

    assert titles(result)[0] == "Streaming toolkit"
    assert len(result.achievement_ids) == 1


async def test_an_employer_named_in_the_question_narrows_the_search(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_agent_embeddings(monkeypatch)
    world = await seed_resume_world(embeddings=True)

    result = await run(world["candidate"], "Tell me about the Kubernetes rollout at Beta Inc")

    assert titles(result)[0] == "Kubernetes rollout"
    assert len(result.achievement_ids) == 1


async def test_an_empty_knowledge_base_returns_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    install_agent_embeddings(monkeypatch)
    world = await seed_resume_world(embeddings=True)
    other_candidate, _, _ = await seed_evidence_chunk(bodies=["x"])

    result = await run(other_candidate, "Faster nightly import")

    assert result.approved == 0
    assert result.blocks == []
    assert world["candidate"] != other_candidate


async def test_a_question_nothing_matches_falls_below_the_floor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_agent_embeddings(monkeypatch)
    world = await seed_resume_world(embeddings=True)
    monkeypatch.setattr(get_settings(), "agent_min_retrieval_score", 0.6)

    result = await run(world["candidate"], "How do you feel about sailing?")

    assert result.approved == len(WORLD_ACHIEVEMENTS)
    assert result.achievement_ids == []
    assert result.best_score < 0.6


async def test_the_floor_is_a_setting(monkeypatch: pytest.MonkeyPatch) -> None:
    install_agent_embeddings(monkeypatch)
    world = await seed_resume_world(embeddings=True)
    monkeypatch.setattr(get_settings(), "agent_min_retrieval_score", 0.0)

    result = await run(world["candidate"], "How do you feel about sailing?")

    assert len(titles(result)) == 5


async def test_highlights_give_broad_questions_the_best_work_per_employer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_agent_embeddings(monkeypatch)
    world = await seed_resume_world(embeddings=True)
    monkeypatch.setattr(get_settings(), "agent_min_retrieval_score", 0.9)

    result = await run(world["candidate"], "Tell me about yourself")

    assert result.achievement_ids == []
    assert titles(result) == ["Faster nightly import", "Kubernetes rollout", "Streaming toolkit"]
    first = result.blocks[0]
    assert "Action:" not in first.text
    assert "Result:" in first.text or "Title:" in first.text


async def test_highlights_never_repeat_a_relevant_achievement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_agent_embeddings(monkeypatch)
    world = await seed_resume_world(embeddings=True)

    result = await run(world["candidate"], "Tell me about Faster nightly import")

    assert len(titles(result)) == len(set(titles(result)))
    assert titles(result)[0] == "Faster nightly import"
    assert [block.marker for block in result.blocks if block.kind == "achievement"] == [
        f"A{n}" for n in range(1, len(titles(result)) + 1)
    ]


async def test_citations_carry_readable_labels_and_cleaned_quotes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_agent_embeddings(monkeypatch)
    candidate_id, _, item_ids = await seed_evidence_chunk(
        bodies=[
            (
                "Speed up the nightly import\n\nBatch the writes.\n\n"
                "Co-Authored-By: Claude <noreply@anthropic.com>"
            )
        ]
    )
    await seed_achievement(
        candidate_id,
        item_ids=item_ids,
        status="approved",
        title="Faster nightly import",
        embedding=fake_vector("Faster nightly import"),
    )

    result = await run(candidate_id, "Faster nightly import")

    achievement, evidence = result.blocks[0], result.blocks[1]
    assert achievement.label == "Faster nightly import"
    assert evidence.label.startswith("ada/engine: Speed up the nightly import")
    assert evidence.quote == "Speed up the nightly import Batch the writes."


async def test_user_written_notes_close_to_the_question_become_direct_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_agent_embeddings(monkeypatch)
    candidate_id, _, item_ids = await seed_evidence_chunk(
        bodies=["Faster nightly import: I mentored two interns while doing it"],
        chunk_kind="note",
        item_kind="note",
        embedding=fake_vector("Faster nightly import"),
    )

    result = await run(candidate_id, "Tell me about Faster nightly import")

    notes = [block for block in result.blocks if block.kind == "evidence"]
    assert [block.evidence_item_id for block in notes] == item_ids
    assert notes[0].achievement_id is None
    assert "mentored two interns" in notes[0].text


async def test_commit_chunks_are_not_offered_without_an_approved_achievement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_agent_embeddings(monkeypatch)
    candidate_id, _, _ = await seed_evidence_chunk(
        bodies=["Tuned the loader"], embedding=fake_vector("Faster nightly import")
    )

    result = await run(candidate_id, "Tell me about Faster nightly import")

    assert result.blocks == []


async def test_evidence_snippets_and_drill_down_chunks_carry_markers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_agent_embeddings(monkeypatch)
    candidate_id, chunk_id, item_ids = await seed_evidence_chunk(
        bodies=["Switch the loader to Kafka because the batch job could not keep up"],
        text="PR description: we moved to Kafka because the nightly batch could not keep up",
    )
    async with session_factory() as session:
        await session.execute(
            update(EvidenceChunk)
            .where(EvidenceChunk.id == chunk_id)
            .values(embedding=fake_vector("Faster nightly import"))
        )
        await session.commit()
    await seed_achievement(
        candidate_id,
        item_ids=item_ids,
        status="approved",
        title="Faster nightly import",
        embedding=fake_vector("Faster nightly import"),
    )

    result = await run(candidate_id, "Why Kafka? Faster nightly import")

    evidence = [block for block in result.blocks if block.kind == "evidence"]
    assert [block.marker for block in evidence] == ["E1"]
    assert evidence[0].evidence_item_id == item_ids[0]
    assert "Context from the same work" in evidence[0].text
    assert "because the nightly batch" in evidence[0].text


async def test_private_provenance_reaches_the_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    install_agent_embeddings(monkeypatch)
    world = await seed_resume_world(embeddings=True, private={"import"})

    result = await run(world["candidate"], "Faster nightly import")

    flags = {block.marker: block.private for block in result.blocks[:2]}
    assert flags == {"A1": True, "E1": True}


async def test_evidence_text_is_redacted_before_it_is_offered(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_agent_embeddings(monkeypatch)
    candidate_id, _, item_ids = await seed_evidence_chunk(
        bodies=["Fixed the loader, ping ada@example.com for details"]
    )
    await seed_achievement(
        candidate_id,
        item_ids=item_ids,
        status="approved",
        title="Faster nightly import",
        embedding=fake_vector("Faster nightly import"),
    )

    result = await run(candidate_id, "Faster nightly import")

    assert all("ada@example.com" not in block.text for block in result.blocks)
