import json
import math
import uuid
from typing import Any

import pytest
from fakes import (
    VALID_PROFILE,
    ProviderError,
    fake_vector,
    install_acompletion,
    llm_response,
)
from sqlalchemy import select

from app.core.config import Settings
from app.core.db import session_factory
from app.models import JobPosting, Match, Profile
from app.schemas.profile import ProfileCreate, ProfileUpdate, StructuredProfile
from app.services import matching
from app.services.profile_service import create_profile as create_profile_service
from app.services.profile_service import save_profile

pytestmark = pytest.mark.usefixtures("clean_tables")

DESCRIPTION = "Analyse data with SQL and Python. " * 100


def structured_profile() -> StructuredProfile:
    return StructuredProfile.model_validate(VALID_PROFILE)


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    return dot / (norm_a * norm_b)


async def seed_profile(name: str = "Default") -> uuid.UUID:
    async with session_factory() as session:
        response = await create_profile_service(
            session, ProfileCreate(name=name, structured_profile=structured_profile())
        )
        await session.commit()
        return response.profile_id


async def seed_postings(specs: list[dict[str, Any]]) -> list[JobPosting]:
    async with session_factory() as session:
        postings: list[JobPosting] = []
        for index, spec in enumerate(specs):
            posting = JobPosting(
                source="adzuna",
                external_id=f"ext-{index}",
                title=spec.get("title", f"Job {index}"),
                company=spec.get("company"),
                location=spec.get("location", "Berlin"),
                job_type=spec.get("job_type"),
                remote_type=spec.get("remote_type"),
                description=spec.get("description", DESCRIPTION),
                embedding=spec["embedding"],
                posted_at=spec.get("posted_at"),
                raw_payload={"id": f"ext-{index}"},
            )
            session.add(posting)
            postings.append(posting)
        await session.commit()
        for posting in postings:
            await session.refresh(posting)
        return postings


async def fetch_matches(profile_id: uuid.UUID) -> list[Match]:
    async with session_factory() as session:
        result = await session.execute(
            select(Match).where(Match.profile_id == profile_id).order_by(Match.vector_score.desc())
        )
        return list(result.scalars().all())


async def fetch_profile_embedding(profile_id: uuid.UUID) -> list[float]:
    async with session_factory() as session:
        profile = await session.get(Profile, profile_id)
        assert profile is not None
        assert profile.embedding is not None
        return profile.embedding


async def fetch_profile_ids_with_embeddings(
    profile_id: uuid.UUID,
) -> tuple[uuid.UUID, list[float]]:
    async with session_factory() as session:
        profile = await session.get(Profile, profile_id)
        assert profile is not None
        await session.refresh(profile)
        assert profile.embedding is not None
        return profile.id, profile.embedding


async def clear_profile_embedding(profile_id: uuid.UUID) -> None:
    async with session_factory() as session:
        profile = await session.get(Profile, profile_id)
        assert profile is not None
        profile.embedding = None
        await session.commit()


def rerank_items_for(postings: list[JobPosting]) -> list[dict[str, Any]]:
    return [
        {"posting_id": str(p.id), "role_fit": 8.0, "company_fit": 6.0, "rationale": "Strong fit."}
        for p in postings
    ]


def install_rerank(monkeypatch: pytest.MonkeyPatch, content: str) -> list[dict[str, Any]]:
    return install_acompletion(monkeypatch, lambda **kw: llm_response(content, prompt_tokens=11))


def install_rerank_for(
    monkeypatch: pytest.MonkeyPatch, postings: list[JobPosting]
) -> list[dict[str, Any]]:
    return install_rerank(monkeypatch, json.dumps({"items": rerank_items_for(postings)}))


def expected_scores(
    profile_embedding: list[float], postings: list[JobPosting]
) -> dict[uuid.UUID, float]:
    return {
        posting.id: max(0.0, min(1.0, cosine(profile_embedding, posting.embedding)))
        for posting in postings
    }


async def refresh(profile_id: uuid.UUID) -> Any:
    async with session_factory() as session:
        outcome = await matching.refresh_matches_for_profile(session, profile_id)
        await session.commit()
        return outcome


async def test_refresh_scores_and_reranks_all_postings(monkeypatch: pytest.MonkeyPatch) -> None:
    profile_id = await seed_profile()
    _, profile_embedding = await fetch_profile_ids_with_embeddings(profile_id)
    postings = await seed_postings([{"embedding": fake_vector(f"j{i}")} for i in range(3)])
    scores = expected_scores(profile_embedding, postings)
    calls = install_rerank_for(monkeypatch, postings)

    outcome = await refresh(profile_id)

    assert outcome.status == "ok"
    assert outcome.scored_count == 3
    assert outcome.rationale_count == 3
    assert outcome.rerank_prompt_tokens == 11
    assert outcome.rerank_completion_tokens == 5
    assert len(calls) == 1

    matches = await fetch_matches(profile_id)
    assert len(matches) == 3
    for match in matches:
        assert match.vector_score == pytest.approx(scores[match.job_posting_id], abs=1e-6)
        assert match.role_fit == 8.0
        assert match.company_fit == 6.0
        assert match.rationale == "Strong fit."
        assert match.final_score == pytest.approx(
            0.4 * match.vector_score + 0.4 * 0.8 + 0.2 * 0.6, abs=1e-6
        )


async def test_second_refresh_makes_no_llm_calls_when_all_rationaled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile_id = await seed_profile()
    postings = await seed_postings([{"embedding": fake_vector(f"j{i}")} for i in range(2)])
    calls = install_rerank_for(monkeypatch, postings)

    first = await refresh(profile_id)
    second = await refresh(profile_id)

    assert first.status == "ok"
    assert second.status == "ok"
    assert second.rationale_count == 0
    assert second.rerank_prompt_tokens == 0
    assert len(calls) == 1
    assert len(await fetch_matches(profile_id)) == 2


async def test_rerank_caps_to_top_n_and_targets_rationaleless(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile_id = await seed_profile()
    _, profile_embedding = await fetch_profile_ids_with_embeddings(profile_id)
    postings = await seed_postings([{"embedding": fake_vector(f"j{i}")} for i in range(3)])
    scores = expected_scores(profile_embedding, postings)
    calls = install_rerank_for(monkeypatch, postings)
    monkeypatch.setattr(matching, "get_settings", lambda: Settings(rerank_top_n=1))

    await refresh(profile_id)
    matches = await fetch_matches(profile_id)
    rationaled = [match for match in matches if match.rationale is not None]
    assert len(rationaled) == 1
    assert rationaled[0].vector_score == pytest.approx(max(scores.values()), abs=1e-6)

    await refresh(profile_id)
    assert len([m for m in await fetch_matches(profile_id) if m.rationale]) == 2

    await refresh(profile_id)
    assert len([m for m in await fetch_matches(profile_id) if m.rationale]) == 3
    assert len(calls) == 3

    outcome = await refresh(profile_id)
    assert outcome.rationale_count == 0
    assert len(calls) == 3


async def test_rerank_failure_degrades_to_vector_scores(monkeypatch: pytest.MonkeyPatch) -> None:
    profile_id = await seed_profile()
    _, profile_embedding = await fetch_profile_ids_with_embeddings(profile_id)
    postings = await seed_postings([{"embedding": fake_vector("j0")}])
    scores = expected_scores(profile_embedding, postings)
    install_acompletion(monkeypatch, lambda **kw: ProviderError(400))

    outcome = await refresh(profile_id)

    assert outcome.status == "failed"
    assert outcome.warning is not None
    assert "re-rank unavailable" in outcome.warning
    assert outcome.scored_count == 1
    matches = await fetch_matches(profile_id)
    assert len(matches) == 1
    assert matches[0].rationale is None
    assert matches[0].role_fit is None
    assert matches[0].final_score == pytest.approx(scores[postings[0].id], abs=1e-6)


async def test_unknown_llm_item_ids_are_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    profile_id = await seed_profile()
    postings = await seed_postings([{"embedding": fake_vector(f"j{i}")} for i in range(2)])
    items = rerank_items_for(postings[:1])
    items.append(
        {"posting_id": str(uuid.uuid4()), "role_fit": 9.0, "company_fit": 9.0, "rationale": "Nope."}
    )
    install_rerank(monkeypatch, json.dumps({"items": items}))

    outcome = await refresh(profile_id)

    assert outcome.status == "ok"
    assert outcome.rationale_count == 1
    matches = await fetch_matches(profile_id)
    rationaled = [match for match in matches if match.rationale is not None]
    assert len(rationaled) == 1
    assert rationaled[0].job_posting_id == postings[0].id


async def test_rescore_with_invalidation_clears_llm_state_without_llm_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile_id = await seed_profile()
    postings = await seed_postings([{"embedding": fake_vector("j0")}])
    install_rerank_for(monkeypatch, postings)
    await refresh(profile_id)
    calls = install_acompletion(monkeypatch, lambda **kw: ProviderError(400))

    modified = structured_profile().model_copy(deep=True)
    modified.headline = "Lead Data Analyst"
    async with session_factory() as session:
        await save_profile(
            session,
            profile_id,
            ProfileUpdate(structured_profile=modified),
        )
        await session.commit()

    matches = await fetch_matches(profile_id)
    assert len(matches) == 1
    assert matches[0].rationale is None
    assert matches[0].role_fit is None
    assert matches[0].company_fit is None
    assert matches[0].final_score == pytest.approx(matches[0].vector_score, abs=1e-6)
    assert len(calls) == 0


async def test_refresh_skips_profile_without_embedding() -> None:
    profile_id = await seed_profile()
    await seed_postings([{"embedding": fake_vector("j0")}])
    await clear_profile_embedding(profile_id)

    outcome = await refresh(profile_id)

    assert outcome.status == "skipped"
    assert outcome.warning is not None
    assert "no embedding" in outcome.warning
    assert await fetch_matches(profile_id) == []


async def test_refresh_unknown_profile_is_skipped() -> None:
    outcome = await refresh(uuid.uuid4())

    assert outcome.status == "skipped"
    assert outcome.warning == "profile not found"


def test_rerank_prompt_truncates_description_and_includes_digest() -> None:
    posting = JobPosting(
        source="adzuna",
        external_id="ext-0",
        title="Data Analyst",
        company="Acme",
        location="Berlin",
        description="x" * 3000,
        raw_payload={},
    )
    prompt = matching._rerank_prompt(structured_profile(), [posting])

    assert str(posting.id) in prompt
    assert "Senior Data Analyst" in prompt
    assert "Skills: SQL, Python, Tableau" in prompt
    assert "x" * 1500 in prompt
    assert "x" * 1501 not in prompt
    assert "company: Acme" in prompt
