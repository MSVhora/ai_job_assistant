import json
import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest
from fakes import (
    ProviderError,
    embedding_response,
    fake_vector,
    install_acompletion,
    install_aembedding,
    llm_response,
    seed_evidence_chunk,
    seed_profile_light,
)
from fastapi import BackgroundTasks
from sqlalchemy import func, select, text

from app.adapters.llm import estimate_tokens
from app.core.config import get_settings
from app.core.db import session_factory
from app.core.errors import EstimateMismatchError, NothingToExtractError
from app.models import (
    Achievement,
    AchievementEvidence,
    AchievementExtractionRun,
    AchievementRevision,
    AchievementStatus,
    EvidenceChunk,
    Profile,
    SyncStatus,
)
from app.services import achievement_extraction
from app.services.achievement_extraction import estimate, run_extraction, start_extraction
from app.services.employer_mapping import Experience, suggest_employer

pytestmark = pytest.mark.usefixtures("clean_tables")

BODIES = [
    "Cut the nightly import from 42 minutes to 9 minutes by batching writes",
    "Add retry budget for the loader",
]


@pytest.fixture(autouse=True)
def _settings(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "gemini_api_key", "test-key")
    monkeypatch.setattr(settings, "llm_retry_attempts", 1)
    monkeypatch.setattr(settings, "llm_retry_base_delay_s", 0.0)
    monkeypatch.setattr(settings, "llm_model_extract", None)


def achievement_json(**overrides: object) -> dict[str, Any]:
    base: dict[str, Any] = {
        "title": "Faster nightly import",
        "situation": "The nightly import took 42 minutes.",
        "task": "Reduce the runtime.",
        "action": "Batched the database writes.",
        "result": "The import now takes 9 minutes.",
        "result_quote": "from 42 minutes to 9 minutes",
        "metrics": [
            {
                "text": "42 minutes to 9 minutes",
                "source_quote": "from 42 minutes to 9 minutes",
                "evidence_ids": ["E1"],
            }
        ],
        "skills": ["python", "postgres"],
        "impact_type": "performance",
        "difficulty": 3,
        "evidence_ids": ["E1"],
    }
    return {**base, **overrides}


def llm(monkeypatch: pytest.MonkeyPatch, *achievements: dict[str, Any]) -> list[dict[str, Any]]:
    payload = json.dumps({"achievements": list(achievements)})

    def handler(**kwargs: Any) -> Any:
        return llm_response(
            payload,
            prompt_tokens=estimate_tokens(kwargs["messages"]),
            completion_tokens=len(payload) // 4,
        )

    return install_acompletion(monkeypatch, handler)


async def run_once() -> uuid.UUID:
    async with session_factory() as session:
        current = await estimate(session)
        response = await start_extraction(session, BackgroundTasks(), current.estimate_id)
        await session.commit()
    await run_extraction(response.run_id)
    return response.run_id


async def run_row(run_id: uuid.UUID) -> AchievementExtractionRun:
    async with session_factory() as session:
        return await session.get_one(AchievementExtractionRun, run_id)


async def drafts() -> list[Achievement]:
    async with session_factory() as session:
        return list((await session.execute(select(Achievement))).scalars().all())


async def test_a_chunk_becomes_a_validated_draft_with_evidence_revision_and_embedding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    llm(monkeypatch, achievement_json())
    _, chunk_id, item_ids = await seed_evidence_chunk(bodies=BODIES)

    run_id = await run_once()

    (draft,) = await drafts()
    assert draft.status is AchievementStatus.draft
    assert draft.title == "Faster nightly import"
    assert draft.result == "The import now takes 9 minutes."
    assert draft.metrics[0]["verified"] == "evidence"
    assert draft.metrics[0]["evidence_ids"] == [str(item_ids[0])]
    assert draft.skills == ["Python", "PostgreSQL"]
    assert draft.embedding is not None
    assert (draft.prompt_version, draft.derived_from_private) == ("achievement_v1", False)
    async with session_factory() as session:
        links = (await session.execute(select(AchievementEvidence))).scalars().all()
        revisions = (await session.execute(select(AchievementRevision))).scalars().all()
        chunk = await session.get_one(EvidenceChunk, chunk_id)
    assert [(link.item_id, link.role) for link in links] == [(item_ids[0], "primary")]
    assert links[0].quote == "from 42 minutes to 9 minutes"
    assert [rev.source.value for rev in revisions] == ["ai_extraction"]
    assert chunk.extracted_hash is not None
    run = await run_row(run_id)
    assert run.status is SyncStatus.succeeded
    assert run.progress["achievements"] == 1
    assert run.usage["prompt_tokens"] > 0


async def test_a_trap_chunk_without_a_metric_yields_no_metrics_and_no_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    llm(
        monkeypatch,
        achievement_json(
            result="Saved a lot of money", result_quote=None, metrics=[], evidence_ids=["E2"]
        ),
    )
    await seed_evidence_chunk(bodies=["Add retry budget for the loader", "Tidy loader tests"])

    await run_once()

    (draft,) = await drafts()
    assert draft.metrics == []
    assert draft.result is None
    assert "result_removed_unsupported" in draft.review_flags


async def test_a_fabricated_metric_is_kept_only_as_needs_confirmation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    llm(
        monkeypatch,
        achievement_json(
            metrics=[{"text": "10x faster", "source_quote": "ten times", "evidence_ids": ["E1"]}]
        ),
    )
    await seed_evidence_chunk(bodies=BODIES)

    await run_once()

    (draft,) = await drafts()
    assert draft.metrics[0]["verified"] == "needs_confirmation"
    assert "metric_needs_confirmation" in draft.review_flags


async def test_evidence_outside_the_chunk_is_rejected_but_the_chunk_counts_as_done(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    llm(monkeypatch, achievement_json(evidence_ids=["E9"]))
    _, chunk_id, _ = await seed_evidence_chunk(bodies=BODIES)

    run_id = await run_once()

    assert await drafts() == []
    run = await run_row(run_id)
    assert (run.progress["rejected"], run.progress["done"]) == (1, 1)
    async with session_factory() as session:
        assert (await session.get_one(EvidenceChunk, chunk_id)).extracted_hash is not None


async def test_a_second_run_makes_zero_provider_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = llm(monkeypatch, achievement_json())
    await seed_evidence_chunk(bodies=BODIES)
    await run_once()
    first_calls = len(calls)

    async with session_factory() as session:
        current = await estimate(session)
        with pytest.raises(NothingToExtractError):
            await start_extraction(session, BackgroundTasks(), current.estimate_id)

    assert first_calls == 1
    assert len(calls) == first_calls
    assert (current.chunks_to_extract, current.chunks_up_to_date) == (0, 1)
    assert len(await drafts()) == 1


async def test_a_lost_marker_is_served_from_the_cache_without_duplicates_or_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = llm(monkeypatch, achievement_json())
    await seed_evidence_chunk(bodies=BODIES)
    await run_once()
    async with session_factory() as session:
        await session.execute(text("UPDATE evidence_chunk SET extracted_hash = NULL"))
        await session.commit()
        current = await estimate(session)

    run_id = await run_once()

    assert (current.chunks_cached, current.chunks_to_extract) == (1, 0)
    assert len(calls) == 1
    assert len(await drafts()) == 1
    assert (await run_row(run_id)).status is SyncStatus.succeeded


async def test_a_new_prompt_version_reextracts_and_supersedes_old_drafts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = llm(monkeypatch, achievement_json())
    await seed_evidence_chunk(bodies=BODIES)
    await run_once()
    monkeypatch.setattr(achievement_extraction, "ACHIEVEMENT_PROMPT_VERSION", "achievement_v2")

    await run_once()

    assert len(calls) == 2
    stored = {draft.prompt_version: draft for draft in await drafts()}
    assert stored["achievement_v1"].status is AchievementStatus.archived
    assert stored["achievement_v2"].status is AchievementStatus.draft


async def test_one_failing_chunk_does_not_fail_the_run_and_is_retried_next_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate_id, good_chunk, _ = await seed_evidence_chunk(bodies=BODIES, project_key="ada/good")
    _, bad_chunk, _ = await seed_evidence_chunk(
        bodies=["Break the importer on purpose"], project_key="ada/bad", candidate_id=candidate_id
    )
    payload = json.dumps({"achievements": [achievement_json()]})

    def flaky(**kwargs: Any) -> Any:
        if "Break the importer" in kwargs["messages"][-1]["content"]:
            return ProviderError(400)
        return llm_response(payload)

    install_acompletion(monkeypatch, flaky)

    run_id = await run_once()

    run = await run_row(run_id)
    assert run.status is SyncStatus.succeeded
    assert (run.progress["failed"], run.progress["done"], run.progress["achievements"]) == (1, 2, 1)
    async with session_factory() as session:
        good = await session.get_one(EvidenceChunk, good_chunk)
        bad = await session.get_one(EvidenceChunk, bad_chunk)
    assert good.extracted_hash is not None
    assert bad.extracted_hash is None
    async with session_factory() as session:
        again = await estimate(session)
    assert again.chunks_to_extract == 1


async def test_a_run_where_every_chunk_fails_is_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    install_acompletion(monkeypatch, lambda **_: ProviderError(400))
    await seed_evidence_chunk(bodies=BODIES)

    run_id = await run_once()

    run = await run_row(run_id)
    assert run.status is SyncStatus.failed
    assert run.error is not None


async def test_embedding_failure_keeps_the_draft_without_a_vector(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    llm(monkeypatch, achievement_json())
    install_aembedding(monkeypatch, lambda **_: ProviderError(400))
    await seed_evidence_chunk(bodies=BODIES)

    run_id = await run_once()

    (draft,) = await drafts()
    assert draft.embedding is None
    assert (await run_row(run_id)).progress["embed_failed"] == 1


async def test_private_evidence_marks_the_draft_and_the_estimate_reports_the_share(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    llm(monkeypatch, achievement_json())
    candidate_id, _, _ = await seed_evidence_chunk(bodies=BODIES, private=True)
    await seed_evidence_chunk(
        bodies=["Public work on the reader"], project_key="ada/open", candidate_id=candidate_id
    )

    async with session_factory() as session:
        current = await estimate(session)
    await run_once()

    assert (current.private_chunks, current.private_share) == (1, 0.5)
    private_drafts = [d for d in await drafts() if d.derived_from_private]
    assert len(private_drafts) >= 1


async def test_estimate_prices_the_real_prompts_within_a_quarter_of_the_metered_tokens(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    llm(monkeypatch, achievement_json())
    candidate_id, _, _ = await seed_evidence_chunk(bodies=BODIES, project_key="ada/a")
    await seed_evidence_chunk(
        bodies=["Rework the reader buffer"], project_key="ada/b", candidate_id=candidate_id
    )
    async with session_factory() as session:
        current = await estimate(session)

    run_id = await run_once()

    usage = (await run_row(run_id)).usage
    assert current.chunks_to_extract == 2
    assert (
        abs(current.llm_cost.prompt_tokens - usage["prompt_tokens"])
        <= 0.25 * usage["prompt_tokens"]
    )  # type: ignore[operator]
    assert current.llm_cost.completion_tokens >= usage["completion_tokens"]  # type: ignore[operator]
    assert current.llm_cost.usd is not None
    assert current.total_usd is not None


async def test_unpriced_models_report_cost_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "llm_model_extract", "nope/unpriced-model")
    monkeypatch.setattr(settings, "llm_price_in_per_mtok", None)
    monkeypatch.setattr(settings, "llm_price_out_per_mtok", None)
    await seed_evidence_chunk(bodies=BODIES)

    async with session_factory() as session:
        current = await estimate(session)

    assert current.llm_cost.usd is None
    assert current.llm_cost.message == "cost unavailable for this model"
    assert current.total_usd is None


async def test_estimate_id_changes_with_the_evidence_and_a_stale_id_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    llm(monkeypatch, achievement_json())
    candidate_id, _, _ = await seed_evidence_chunk(bodies=BODIES)
    async with session_factory() as session:
        before = await estimate(session)
    await seed_evidence_chunk(bodies=["New work"], project_key="ada/new", candidate_id=candidate_id)

    async with session_factory() as session:
        after = await estimate(session)
        with pytest.raises(EstimateMismatchError):
            await start_extraction(session, BackgroundTasks(), before.estimate_id)

    assert before.estimate_id != after.estimate_id
    assert len(before.estimate_id) == 64


async def test_the_prompt_sends_redacted_text_and_fences_the_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = llm(monkeypatch, achievement_json())
    await seed_evidence_chunk(
        bodies=["Mail ada@example.com about the importer"],
        text="Mail <EMAIL_1> about the importer",
    )

    await run_once()

    sent = "\n".join(m["content"] for m in calls[0]["messages"])
    assert "ada@example.com" not in sent
    assert "<<<EVIDENCE" in sent
    assert "untrusted data" in sent
    assert "E1:" in sent


async def test_stale_reconciliation_archives_drafts_and_flags_approved_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    llm(monkeypatch, achievement_json())
    candidate_id, _, _ = await seed_evidence_chunk(bodies=BODIES)
    async with session_factory() as session:
        for status in (AchievementStatus.draft, AchievementStatus.approved):
            session.add(
                Achievement(
                    candidate_id=candidate_id,
                    status=status,
                    title=f"Old {status.value}",
                    source_chunk_hash="gone" * 16,
                    impact_type="other",
                    difficulty=3,
                )
            )
        await session.commit()

    await run_once()

    by_title = {d.title: d for d in await drafts()}
    assert by_title["Old draft"].status is AchievementStatus.archived
    assert by_title["Old approved"].status is AchievementStatus.approved
    assert by_title["Old approved"].evidence_stale_at is not None
    assert by_title["Faster nightly import"].evidence_stale_at is None
    async with session_factory() as session:
        reasons = (
            await session.execute(
                select(func.count())
                .select_from(AchievementRevision)
                .where(AchievementRevision.source == "status_change")
            )
        ).scalar_one()
    assert reasons == 1


async def test_employer_comes_from_the_scope_else_from_date_overlap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    llm(monkeypatch, achievement_json())
    await seed_profile_light()
    async with session_factory() as session:
        profile = (await session.execute(select(Profile))).scalar_one()
        data = dict(profile.structured_profile)
        data["experience"] = [
            {
                "company": "Acme Corp",
                "title": "Engineer",
                "start_date": "Jan 2024",
                "end_date": "Dec 2024",
                "bullets": [],
            }
        ]
        profile.structured_profile = data
        await session.commit()
        candidate_id = profile.candidate_id
    await seed_evidence_chunk(
        bodies=BODIES,
        project_key="ada/engine",
        candidate_id=candidate_id,
        when=datetime(2024, 6, 1, tzinfo=UTC),
    )

    await run_once()

    (draft,) = await drafts()
    assert draft.employer_ref == {
        "company": "Acme Corp",
        "start_date": "Jan 2024",
        "source": "suggested",
    }


async def test_a_scope_employer_overrides_the_suggestion(monkeypatch: pytest.MonkeyPatch) -> None:
    llm(monkeypatch, achievement_json())
    await seed_evidence_chunk(
        bodies=BODIES, scope_employer={"company": "Chosen Ltd", "start_date": "2022"}
    )

    await run_once()

    (draft,) = await drafts()
    assert draft.employer_ref == {
        "company": "Chosen Ltd",
        "start_date": "2022",
        "source": "scope",
    }


def test_suggest_employer_skips_non_repository_chunks_and_non_overlapping_ranges() -> None:
    experience = Experience("Acme", "Jan 2024", date(2024, 1, 1), date(2024, 12, 31))
    during = date(2024, 5, 1)
    after = date(2026, 1, 1)

    assert suggest_employer("ada/engine", during, during, [experience])["company"] == "Acme"  # type: ignore[index]
    assert suggest_employer("resume:Acme", during, during, [experience]) is None
    assert suggest_employer("note:ideas", during, during, [experience]) is None
    assert suggest_employer("ada/engine", after, after, [experience]) is None
    assert suggest_employer("ada/engine", None, None, [experience]) is None


def test_fake_vector_dimension_matches_the_pinned_embedding_size() -> None:
    assert len(fake_vector("x")) == get_settings().embedding_dimensions
    assert embedding_response([fake_vector("x")]).data[0]["embedding"]
    assert timedelta(minutes=get_settings().max_run_age_minutes) > timedelta(0)
