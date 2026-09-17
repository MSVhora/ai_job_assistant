import decimal
import json
import math
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fakes import (
    VALID_PROFILE,
    ProviderError,
    fake_vector,
    install_acompletion,
    llm_response,
)
from fastapi import BackgroundTasks
from sqlalchemy import select

from app.core.config import Settings
from app.core.db import session_factory
from app.models import JobPosting, JobSearch, JobSearchStatus, Match, Profile, SearchPosting
from app.schemas.matching import MatchQueryParams, MatchResponse
from app.schemas.profile import Preferences, ProfileCreate, ProfileUpdate, StructuredProfile
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


async def seed_postings(
    specs: list[dict[str, Any]], found_by: uuid.UUID | None = None
) -> list[JobPosting]:
    """Seed postings; with `found_by`, attach them via an owned search (scoped corpus)."""
    async with session_factory() as session:
        search: JobSearch | None = None
        if found_by is not None:
            search = JobSearch(
                profile_id=found_by,
                source="adzuna",
                status=JobSearchStatus.succeeded,
                query={"profile_id": str(found_by)},
            )
            session.add(search)
            await session.flush()
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
                salary_min=spec.get("salary_min"),
                salary_max=spec.get("salary_max"),
                currency=spec.get("currency"),
                raw_payload={"id": f"ext-{index}"},
            )
            session.add(posting)
            postings.append(posting)
        await session.flush()
        if search is not None:
            for posting in postings:
                session.add(SearchPosting(search_id=search.id, posting_id=posting.id))
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


# The default DESCRIPTION ("Analyse data with SQL and Python") hits 2 of the
# profile's 3 skills; postings seeded without posted_at/salary make the
# recency/salary signals neutral (0.5). describing the default fixtures.
DEFAULT_SKILL_SCORE = 2.0 / 3.0
DEFAULT_RECENCY_SCORE = 0.5
DEFAULT_SALARY_SCORE = 0.5


def expected_final(
    vector: float | None, *, role_fit: float | None = None, company_fit: float | None = None
) -> float:
    """Python mirror of `_final_score` under default Settings weights (#37)."""
    weights = Settings()
    if vector is None:
        denom = (
            weights.match_weight_skill + weights.match_weight_recency + weights.match_weight_salary
        )
        weighted = (
            weights.match_weight_skill * DEFAULT_SKILL_SCORE
            + weights.match_weight_recency * DEFAULT_RECENCY_SCORE
            + weights.match_weight_salary * DEFAULT_SALARY_SCORE
        )
        total = weighted / denom
    else:
        total = (
            weights.match_weight_vector * vector
            + weights.match_weight_skill * DEFAULT_SKILL_SCORE
            + weights.match_weight_recency * DEFAULT_RECENCY_SCORE
            + weights.match_weight_salary * DEFAULT_SALARY_SCORE
        )
    if role_fit is not None:
        total += weights.match_weight_role_fit * role_fit / 10.0
    if company_fit is not None:
        total += weights.match_weight_company_fit * company_fit / 10.0
    return max(0.0, min(1.0, total))


async def refresh(profile_id: uuid.UUID) -> Any:
    async with session_factory() as session:
        outcome = await matching.refresh_matches_for_profile(session, profile_id)
        await session.commit()
        return outcome


async def test_refresh_scores_and_reranks_all_postings(monkeypatch: pytest.MonkeyPatch) -> None:
    profile_id = await seed_profile()
    _, profile_embedding = await fetch_profile_ids_with_embeddings(profile_id)
    postings = await seed_postings(
        [{"embedding": fake_vector(f"j{i}")} for i in range(3)], found_by=profile_id
    )
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
        assert match.skill_score == pytest.approx(DEFAULT_SKILL_SCORE, abs=1e-6)
        assert match.recency_score == pytest.approx(DEFAULT_RECENCY_SCORE, abs=1e-6)
        assert match.salary_score == pytest.approx(DEFAULT_SALARY_SCORE, abs=1e-6)
        assert match.role_fit == 8.0
        assert match.company_fit == 6.0
        assert match.rationale == "Strong fit."
        assert match.final_score == pytest.approx(
            expected_final(match.vector_score, role_fit=8.0, company_fit=6.0), abs=1e-6
        )


async def test_second_refresh_makes_no_llm_calls_when_all_rationaled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile_id = await seed_profile()
    postings = await seed_postings(
        [{"embedding": fake_vector(f"j{i}")} for i in range(2)], found_by=profile_id
    )
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
    postings = await seed_postings(
        [{"embedding": fake_vector(f"j{i}")} for i in range(3)], found_by=profile_id
    )
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
    postings = await seed_postings([{"embedding": fake_vector("j0")}], found_by=profile_id)
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
    assert matches[0].final_score == pytest.approx(expected_final(scores[postings[0].id]), abs=1e-6)


async def test_unknown_llm_item_ids_are_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    profile_id = await seed_profile()
    postings = await seed_postings(
        [{"embedding": fake_vector(f"j{i}")} for i in range(2)], found_by=profile_id
    )
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
    postings = await seed_postings([{"embedding": fake_vector("j0")}], found_by=profile_id)
    install_rerank_for(monkeypatch, postings)
    await refresh(profile_id)
    calls = install_acompletion(monkeypatch, lambda **kw: ProviderError(400))

    modified = structured_profile().model_copy(deep=True)
    modified.headline = "Lead Data Analyst"
    async with session_factory() as session:
        await save_profile(
            session,
            BackgroundTasks(),
            profile_id,
            ProfileUpdate(structured_profile=modified),
        )
        await session.commit()

    matches = await fetch_matches(profile_id)
    assert len(matches) == 1
    assert matches[0].rationale is None
    assert matches[0].role_fit is None
    assert matches[0].company_fit is None
    assert matches[0].final_score == pytest.approx(
        expected_final(matches[0].vector_score), abs=1e-6
    )
    assert len(calls) == 0


async def test_refresh_skips_profile_without_embedding() -> None:
    profile_id = await seed_profile()
    await seed_postings([{"embedding": fake_vector("j0")}], found_by=profile_id)
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
    profile = structured_profile()
    prompt = matching._rerank_prompt(profile, [posting], profile.skills)

    assert str(posting.id) in prompt
    assert "Senior Data Analyst" in prompt
    assert "Skills: SQL, Python, Tableau" in prompt
    assert "x" * 1500 in prompt
    assert "x" * 1501 not in prompt
    assert "company: Acme" in prompt


def test_rerank_prompt_lists_skill_overlap_and_preference_lines() -> None:
    posting = JobPosting(
        source="adzuna",
        external_id="ext-1",
        title="Golang Backend Dev",
        company="Acme",
        location="Berlin",
        description="Build pipelines with Python, dbt tooling and Tableau dashboards.",
        raw_payload={},
    )
    profile = structured_profile().model_copy(deep=True)
    profile.preferences = Preferences(
        salary_min=60000, salary_max=80000, currency="EUR", remote_preference="remote"
    )
    prompt = matching._rerank_prompt(profile, [posting], profile.skills)

    assert "Salary preference: 60000.0–80000.0 EUR" in prompt
    assert "Remote preference: remote" in prompt
    assert "skills overlap: Python, Tableau" in prompt
    assert "Skills: SQL, Python, Tableau" in prompt


def test_priority_weights_split_judgment_mass() -> None:
    assert matching.priority_weights(0.0) == (pytest.approx(0.0), pytest.approx(0.2))
    assert matching.priority_weights(1.0) == (pytest.approx(0.2), pytest.approx(0.0))
    w_role, w_company = matching.priority_weights(matching.default_priority())
    assert (w_role, w_company) == (pytest.approx(0.15), pytest.approx(0.05))
    assert matching.priority_weights(5.0) == matching.priority_weights(1.0)
    assert matching.priority_weights(-1.0) == matching.priority_weights(0.0)


def test_default_priority_tracks_settings_weights(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        matching,
        "get_settings",
        lambda: Settings(
            match_weight_vector=0.6,
            match_weight_skill=0.2,
            match_weight_recency=0.05,
            match_weight_role_fit=0.1,
            match_weight_company_fit=0.05,
            match_weight_salary=0.0,
        ),
    )

    assert matching.default_priority() == pytest.approx(0.1 / 0.15)
    assert matching.priority_weights(matching.default_priority()) == (
        pytest.approx(0.1),
        pytest.approx(0.05),
    )


def test_settings_rejects_unbalanced_match_weights() -> None:
    for field in (
        "match_weight_vector",
        "match_weight_skill",
        "match_weight_recency",
        "match_weight_role_fit",
        "match_weight_company_fit",
        "match_weight_salary",
    ):
        kwargs = dict(
            match_weight_vector=0.35,
            match_weight_skill=0.25,
            match_weight_recency=0.15,
            match_weight_role_fit=0.15,
            match_weight_company_fit=0.05,
            match_weight_salary=0.05,
        )
        kwargs[field] = 0.5
        with pytest.raises(ValueError, match="must sum to 1.0"):
            Settings(**kwargs)


async def seed_subscored(
    monkeypatch: pytest.MonkeyPatch, role_fit: float
) -> tuple[uuid.UUID, list[JobPosting]]:
    profile_id = await seed_profile()
    postings = await seed_postings(
        [{"embedding": fake_vector("twin")} for _ in range(2)], found_by=profile_id
    )
    items = [
        {
            "posting_id": str(postings[0].id),
            "role_fit": role_fit,
            "company_fit": 10.0 - role_fit,
            "rationale": "Role leaning.",
        },
        {
            "posting_id": str(postings[1].id),
            "role_fit": 10.0 - role_fit,
            "company_fit": role_fit,
            "rationale": "Company leaning.",
        },
    ]
    install_rerank(monkeypatch, json.dumps({"items": items}))
    await refresh(profile_id)
    return profile_id, postings


async def list_ordered(profile_id: uuid.UUID, **params: Any) -> list[MatchResponse]:
    async with session_factory() as session:
        return await matching.list_matches(
            session, MatchQueryParams(profile_id=profile_id, **params)
        )


async def test_list_matches_blends_subscores_under_custom_priority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile_id, _ = await seed_subscored(monkeypatch, role_fit=9.0)

    role_first = await list_ordered(profile_id, priority=1.0)
    company_first = await list_ordered(profile_id, priority=0.0)

    assert [row.job_posting.title for row in role_first] == ["Job 0", "Job 1"]
    assert [row.job_posting.title for row in company_first] == ["Job 1", "Job 0"]
    vector_score = role_first[0].vector_score
    signals = (
        Settings().match_weight_skill * DEFAULT_SKILL_SCORE
        + Settings().match_weight_recency * DEFAULT_RECENCY_SCORE
        + Settings().match_weight_salary * DEFAULT_SALARY_SCORE
    )
    assert role_first[0].final_score == pytest.approx(
        0.35 * vector_score + signals + 0.2 * 0.9, abs=1e-6
    )
    assert company_first[0].final_score == pytest.approx(
        0.35 * vector_score + signals + 0.2 * 0.9, abs=1e-6
    )


async def test_list_matches_uses_stored_preference_and_falls_back_on_junk(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile_id, _ = await seed_subscored(monkeypatch, role_fit=9.0)

    async with session_factory() as session:
        profile = await session.get(Profile, profile_id)
        assert profile is not None
        profile.preferences = {"priority": 0.0}
        await session.commit()

    stored = await list_ordered(profile_id)
    assert [row.job_posting.title for row in stored] == ["Job 1", "Job 0"]

    async with session_factory() as session:
        profile = await session.get(Profile, profile_id)
        assert profile is not None
        profile.preferences = {"priority": "junk", "future_field": 1}
        await session.commit()

    fallback = await list_ordered(profile_id)
    assert [row.job_posting.title for row in fallback] == ["Job 0", "Job 1"]
    for row in fallback:
        assert row.final_score == pytest.approx(
            expected_final(row.vector_score, role_fit=row.role_fit, company_fit=row.company_fit)
        )


async def test_scoped_corpus_postings_from_other_profile_never_scored(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile_a = await seed_profile("A")
    profile_b = await seed_profile("B")
    _, profile_b_embedding = await fetch_profile_ids_with_embeddings(profile_b)
    postings = await seed_postings(
        [{"embedding": fake_vector(f"j{i}")} for i in range(2)], found_by=profile_a
    )
    install_rerank_for(monkeypatch, postings)

    outcome = await refresh(profile_b)

    assert outcome.status == "ok"
    assert outcome.scored_count == 0
    assert await fetch_matches(profile_b) == []
    outcome_a = await refresh(profile_a)
    assert outcome_a.status == "ok"
    assert outcome_a.scored_count == 2
    matches = await fetch_matches(profile_a)
    assert {match.job_posting_id for match in matches} == {posting.id for posting in postings}


async def test_un_embedded_postings_score_via_fallback_signals(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile_id = await seed_profile()
    postings = await seed_postings(
        [{"embedding": fake_vector("embedded")}, {"embedding": None}], found_by=profile_id
    )
    install_rerank_for(monkeypatch, postings[:1])

    outcome = await refresh(profile_id)

    assert outcome.status == "ok"
    assert outcome.scored_count == 2
    matches = await fetch_matches(profile_id)
    fallback = next(match for match in matches if match.vector_score is None)
    embedded = next(match for match in matches if match.vector_score is not None)
    assert fallback.job_posting_id == postings[1].id
    assert fallback.skill_score == pytest.approx(DEFAULT_SKILL_SCORE, abs=1e-6)
    assert fallback.final_score == pytest.approx(expected_final(None), abs=1e-6)
    assert embedded.final_score == pytest.approx(
        expected_final(
            embedded.vector_score, role_fit=embedded.role_fit, company_fit=embedded.company_fit
        ),
        abs=1e-6,
    )
    assert len(await fetch_matches(profile_id)) == 2


async def test_delete_out_of_corpus_matches_removes_only_stale_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile_id = await seed_profile()
    postings = await seed_postings(
        [{"embedding": fake_vector(f"j{i}")} for i in range(2)], found_by=profile_id
    )
    await refresh(profile_id)
    orphan = JobPosting(
        source="adzuna",
        external_id="orphan-0",
        title="Orphan",
        location="Berlin",
        description=DESCRIPTION,
        embedding=fake_vector("orphan"),
        raw_payload={"id": "orphan-0"},
    )
    async with session_factory() as session:
        session.add(orphan)
        await session.commit()
        await session.refresh(orphan)
        session.add(
            Match(
                profile_id=profile_id,
                job_posting_id=orphan.id,
                vector_score=0.9,
                final_score=0.9,
            )
        )
        await session.commit()

        deleted = await matching.delete_out_of_corpus_matches(session, profile_id)
        await session.commit()

    assert deleted == 1
    matches = await fetch_matches(profile_id)
    assert {match.job_posting_id for match in matches} == {posting.id for posting in postings}


async def test_sql_skill_signal_matches_python_twin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile_id = await seed_profile()
    postings = await seed_postings(
        [
            {"embedding": fake_vector("a0"), "title": "Golang developer", "description": None},
            {"embedding": fake_vector("a1"), "title": "Senior SQL Engineer", "description": None},
        ],
        found_by=profile_id,
    )
    install_rerank_for(monkeypatch, postings)

    await refresh(profile_id)

    matches = await fetch_matches(profile_id)
    by_posting = {match.job_posting_id: match for match in matches}
    skills = ["SQL", "Python", "Tableau"]
    for posting in postings:
        match = by_posting[posting.id]
        expected = len(matching.skill_hit_terms(posting.title, posting.description, skills))
        assert match.skill_score == pytest.approx(expected / len(skills), abs=1e-6)
    assert by_posting[postings[0].id].skill_score == 0.0
    assert by_posting[postings[1].id].skill_score == pytest.approx(1.0 / len(skills), abs=1e-6)


def _salary_posting_spec(
    index: int, lo: decimal.Decimal | None, hi: decimal.Decimal | None, currency: str | None
) -> dict[str, Any]:
    return {
        "embedding": fake_vector(f"s{index}"),
        "description": "No skills mentioned here at all.",
        "salary_min": lo,
        "salary_max": hi,
        "currency": currency,
    }


async def test_sql_salary_signal_matches_python_twin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile_id = await seed_profile()
    specs = [
        _salary_posting_spec(0, decimal.Decimal("70000"), decimal.Decimal("90000"), "GBP"),
        _salary_posting_spec(1, None, None, None),
        _salary_posting_spec(2, decimal.Decimal("40000"), decimal.Decimal("60000"), "GBP"),
        _salary_posting_spec(3, decimal.Decimal("10000"), decimal.Decimal("20000"), "GBP"),
        _salary_posting_spec(4, decimal.Decimal("120000"), decimal.Decimal("140000"), "GBP"),
    ]
    postings = await seed_postings(specs, found_by=profile_id)
    install_rerank_for(monkeypatch, postings)

    structured = structured_profile().model_copy(deep=True)
    structured.preferences = Preferences(salary_min=60_000.0, salary_max=80_000.0, currency="GBP")
    async with session_factory() as session:
        profile = await session.get(Profile, profile_id)
        assert profile is not None
        profile.structured_profile = structured.model_dump(mode="json")
        await session.commit()

    await refresh(profile_id)

    matches = await fetch_matches(profile_id)
    by_posting = {match.job_posting_id: match for match in matches}
    for posting in postings:
        match = by_posting[posting.id]
        expected = matching.salary_fit_score(
            float(posting.salary_min) if posting.salary_min is not None else None,
            float(posting.salary_max) if posting.salary_max is not None else None,
            posting.currency,
            60_000.0,
            80_000.0,
            "GBP",
        )
        assert match.salary_score == pytest.approx(expected, abs=1e-6)
    assert by_posting[postings[0].id].salary_score == 1.0
    assert by_posting[postings[1].id].salary_score == 1.0
    assert by_posting[postings[2].id].salary_score == 1.0
    assert by_posting[postings[3].id].salary_score == 0.0
    assert by_posting[postings[4].id].salary_score == 0.0


async def test_recency_decay_follows_posted_at(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile_id = await seed_profile()
    now = datetime.now(UTC)
    postings = await seed_postings(
        [
            {"embedding": fake_vector("r0"), "posted_at": now},
            {"embedding": fake_vector("r1"), "posted_at": now - timedelta(days=7)},
            {"embedding": fake_vector("r2"), "posted_at": None},
        ],
        found_by=profile_id,
    )
    install_rerank_for(monkeypatch, postings)

    await refresh(profile_id)

    matches = await fetch_matches(profile_id)
    by_posting = {match.job_posting_id: match for match in matches}
    assert by_posting[postings[0].id].recency_score == pytest.approx(1.0, abs=1e-6)
    assert by_posting[postings[1].id].recency_score == pytest.approx(
        math.exp(-7.0 / 14.0), abs=1e-5
    )
    assert by_posting[postings[2].id].recency_score == pytest.approx(0.5, abs=1e-6)


async def test_rerank_pool_is_chosen_by_hybrid_signal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile_id = await seed_profile()
    postings = await seed_postings(
        [{"embedding": fake_vector("p0")}, {"embedding": None}], found_by=profile_id
    )
    strong, weak = postings

    async with session_factory() as session:
        session.add(
            Match(
                profile_id=profile_id,
                job_posting_id=strong.id,
                vector_score=0.5,
                skill_score=0.0,
                recency_score=0.5,
                salary_score=0.5,
                final_score=0.9,
            )
        )
        session.add(
            Match(
                profile_id=profile_id,
                job_posting_id=weak.id,
                vector_score=None,
                skill_score=1.0,
                recency_score=0.5,
                salary_score=0.5,
                final_score=1.0,
            )
        )
        await session.commit()

    calls = install_rerank(monkeypatch, json.dumps({"items": rerank_items_for([weak])}))
    monkeypatch.setattr(matching, "get_settings", lambda: Settings(rerank_top_n=1))

    async with session_factory() as session:
        profile = await session.get(Profile, profile_id)
        assert profile is not None
        outcome = await matching._rerank_top_matches(session, profile, scored_count=2)
        await session.commit()

    assert outcome.rationale_count == 1
    assert len(calls) == 1
    matches = await fetch_matches(profile_id)
    rationaled = [match for match in matches if match.rationale is not None]
    assert len(rationaled) == 1
    assert rationaled[0].job_posting_id == weak.id
    strong_match = next(m for m in matches if m.job_posting_id == strong.id)
    assert strong_match.rationale is None
