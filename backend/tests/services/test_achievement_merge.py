import uuid
from datetime import date
from typing import Any

import pytest
from fakes import fake_vector, seed_achievement, seed_evidence_chunk
from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import session_factory
from app.core.errors import InvalidAchievementInputError
from app.models import (
    Achievement,
    AchievementEvidence,
    AchievementOrigin,
    AchievementRevision,
    AchievementStatus,
)
from app.schemas.achievement import MergeRequest, SplitRequest
from app.services import achievement_merge as merging

pytestmark = pytest.mark.usefixtures("clean_tables")

BODIES = ["Cut the import from 42 minutes to 9", "Add retry budget", "Tidy tests", "Fix loader"]
METRIC = {
    "text": "42 to 9 minutes",
    "source_quote": "x",
    "evidence_ids": [],
    "verified": "evidence",
}


@pytest.fixture(autouse=True)
def _key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "gemini_api_key", "test-key")


async def call(fn: Any, *args: Any) -> Any:
    async with session_factory() as session:
        result = await fn(session, *args)
        await session.commit()
        return result


async def load(achievement_id: uuid.UUID) -> Achievement:
    async with session_factory() as session:
        return await session.get_one(Achievement, achievement_id)


async def evidence_of(achievement_id: uuid.UUID) -> list[tuple[uuid.UUID, str]]:
    async with session_factory() as session:
        rows = (
            await session.execute(
                select(AchievementEvidence).where(
                    AchievementEvidence.achievement_id == achievement_id
                )
            )
        ).scalars()
        return sorted((row.item_id, row.role) for row in rows)


async def revision_sources(achievement_id: uuid.UUID) -> list[tuple[str, dict[str, Any]]]:
    async with session_factory() as session:
        rows = (
            await session.execute(
                select(AchievementRevision).where(
                    AchievementRevision.achievement_id == achievement_id
                )
            )
        ).scalars()
        return [(row.source.value, row.diff) for row in rows]


async def two_achievements() -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, list[uuid.UUID]]:
    candidate_id, _, items = await seed_evidence_chunk(bodies=BODIES)
    first = await seed_achievement(
        candidate_id,
        item_ids=items[:2],
        title="Faster import",
        metrics=[METRIC],
        skills=["Python"],
        difficulty=2,
        time_start=date(2024, 3, 1),
        time_end=date(2024, 3, 10),
    )
    second = await seed_achievement(
        candidate_id,
        item_ids=items[1:3],
        status="approved",
        title="Import retry budget",
        metrics=[{**METRIC, "text": "42  to 9 MINUTES"}, {"text": "5 retries", "verified": "user"}],
        skills=["PostgreSQL", "python"],
        difficulty=4,
        time_start=date(2024, 3, 8),
        time_end=date(2024, 4, 2),
    )
    return candidate_id, first, second, items


async def test_merge_creates_a_merged_draft_with_the_union_and_archives_the_sources() -> None:
    _, first, second, items = await two_achievements()

    merged = await call(merging.merge, MergeRequest(ids=[first, second], title="Import hardening"))

    assert (merged.status, merged.origin) == (AchievementStatus.draft, AchievementOrigin.merged)
    assert merged.title == "Import hardening"
    assert merged.skills == ["Python", "PostgreSQL"]
    assert merged.difficulty == 4
    assert (merged.time_start, merged.time_end) == (date(2024, 3, 1), date(2024, 4, 2))
    assert [m["text"] for m in merged.metrics] == ["42 to 9 minutes", "5 retries"]
    assert "merged" in merged.review_flags
    linked = {(link.item_id, link.role) for link in merged.evidence}
    assert {item for item, _ in linked} == set(items[:3])
    assert sorted(role for _, role in linked) == ["primary", "supporting", "supporting"]
    for source in (first, second):
        assert (await load(source)).status is AchievementStatus.archived
        sources = await revision_sources(source)
        assert sources[0][0] == "merge"
        assert sources[0][1]["merged_into"] == str(merged.id)
    ((kind, diff),) = await revision_sources(merged.id)
    assert (kind, diff) == ("merge", {"merged_from": [str(first), str(second)]})


async def test_merge_recomputes_privacy_and_embeds_the_new_row(
    fake_embedding: list[dict[str, Any]],
) -> None:
    candidate_id, _, items = await seed_evidence_chunk(bodies=BODIES[:2], private=True)
    first = await seed_achievement(candidate_id, item_ids=items[:1], title="One")
    second = await seed_achievement(candidate_id, item_ids=items[1:2], title="Two")
    fake_embedding.clear()

    merged = await call(merging.merge, MergeRequest(ids=[first, second]))

    assert merged.derived_from_private is True
    assert len(fake_embedding) == 1
    assert (await load(merged.id)).embedding is not None


@pytest.mark.parametrize("case", ["duplicate", "archived"])
async def test_merge_rejects_duplicate_ids_and_archived_sources(case: str) -> None:
    _, first, second, _ = await two_achievements()
    async with session_factory() as session:
        (await session.get_one(Achievement, second)).status = AchievementStatus.archived
        await session.commit()
    ids = [first, first] if case == "duplicate" else [first, second]

    with pytest.raises(InvalidAchievementInputError):
        await call(merging.merge, MergeRequest(ids=ids))


async def test_split_moves_the_chosen_evidence_to_a_new_draft_and_unapproves_the_original() -> None:
    candidate_id, _, items = await seed_evidence_chunk(bodies=BODIES)
    original = await seed_achievement(
        candidate_id, item_ids=items[:3], status="approved", metrics=[METRIC], stale=True
    )

    part = await call(
        merging.split, original, SplitRequest(evidence_item_ids=[items[2]], title="Retry work")
    )

    assert (part.status, part.title, part.id != original) == (
        AchievementStatus.draft,
        "Retry work",
        True,
    )
    assert "split" in part.review_flags
    assert [(link.item_id, link.role) for link in part.evidence] == [(items[2], "primary")]
    kept = await evidence_of(original)
    assert {item for item, _ in kept} == set(items[:2])
    assert sorted(role for _, role in kept) == ["primary", "supporting"]
    stored = await load(original)
    assert (stored.status, stored.evidence_stale_at) == (AchievementStatus.draft, None)
    ((kind, diff),) = await revision_sources(original)
    assert kind == "split"
    assert diff["split_to"] == str(part.id)
    assert diff["status"] == ["approved", "draft"]
    assert await revision_sources(part.id) == [("split", {"split_from": str(original)})]


async def test_split_promotes_a_primary_when_the_moved_item_was_the_primary_one() -> None:
    candidate_id, _, items = await seed_evidence_chunk(bodies=BODIES)
    original = await seed_achievement(candidate_id, item_ids=items[:2])

    await call(merging.split, original, SplitRequest(evidence_item_ids=[items[0]]))

    assert await evidence_of(original) == [(items[1], "primary")]


@pytest.mark.parametrize("case", ["all", "foreign", "archived"])
async def test_split_rejects_moving_everything_foreign_evidence_and_archived_rows(
    case: str,
) -> None:
    candidate_id, _, items = await seed_evidence_chunk(bodies=BODIES)
    original = await seed_achievement(
        candidate_id, item_ids=items[:2], status="archived" if case == "archived" else "draft"
    )
    ids = {"all": items[:2], "foreign": [items[3]], "archived": [items[0]]}[case]

    with pytest.raises(InvalidAchievementInputError):
        await call(merging.split, original, SplitRequest(evidence_item_ids=ids))

    assert len(await evidence_of(original)) == 2


async def seed_pair(
    *,
    project_a: str = "ada/engine",
    project_b: str = "ada/engine",
    vector_b: str = "same",
    start_b: date = date(2024, 6, 5),
    status_b: str = "draft",
) -> tuple[uuid.UUID, uuid.UUID]:
    candidate_id, _, items = await seed_evidence_chunk(bodies=BODIES)
    first = await seed_achievement(
        candidate_id,
        item_ids=items[:1],
        project_key=project_a,
        embedding=fake_vector("same"),
        time_start=date(2024, 6, 1),
        time_end=date(2024, 6, 10),
        title="Faster import",
    )
    second = await seed_achievement(
        candidate_id,
        item_ids=items[1:2],
        project_key=project_b,
        embedding=fake_vector(vector_b),
        time_start=start_b,
        status=status_b,
        title="Import is faster",
    )
    return first, second


async def proposals() -> list[Any]:
    async with session_factory() as session:
        return await merging.propose_merges(session)


async def test_near_duplicates_in_one_project_with_overlapping_dates_are_proposed_not_applied() -> (
    None
):
    first, second = await seed_pair()

    found = await proposals()

    assert len(found) == 1
    assert {found[0].first_id, found[0].second_id} == {first, second}
    assert found[0].first_id < found[0].second_id
    assert found[0].similarity == 1.0
    assert found[0].project_key == "ada/engine"
    assert (await load(first)).status is AchievementStatus.draft
    assert (await load(second)).status is AchievementStatus.draft
    assert await revision_sources(first) == []


@pytest.mark.parametrize(
    "override",
    [
        {"project_b": "ada/other"},
        {"vector_b": "something else entirely"},
        {"start_b": date(2025, 1, 1)},
        {"status_b": "rejected"},
        {"status_b": "archived"},
    ],
)
async def test_dissimilar_other_project_non_overlapping_or_closed_rows_are_not_proposed(
    override: dict[str, Any],
) -> None:
    await seed_pair(**override)

    assert await proposals() == []


async def test_rows_without_embeddings_or_dates_are_never_proposed() -> None:
    candidate_id, _, items = await seed_evidence_chunk(bodies=BODIES)
    await seed_achievement(candidate_id, item_ids=items[:1], embedding=None)
    await seed_achievement(candidate_id, item_ids=items[1:2], embedding=fake_vector("same"))
    await seed_achievement(
        candidate_id, item_ids=items[2:3], embedding=fake_vector("same"), project_key=None
    )

    assert await proposals() == []
