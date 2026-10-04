import uuid
from datetime import date
from typing import Any

import pytest
from fakes import fake_vector, seed_achievement, seed_evidence_chunk
from sqlalchemy import select, text

from app.core.config import get_settings
from app.core.db import session_factory
from app.core.errors import (
    AchievementConflictError,
    AchievementNotFoundError,
    EvidenceItemNotFoundError,
    InvalidAchievementInputError,
)
from app.models import (
    Achievement,
    AchievementEvidence,
    AchievementRevision,
    AchievementStatus,
)
from app.schemas.achievement import (
    AchievementUpdate,
    ConfirmMetricRequest,
    EvidenceLinkCreate,
)
from app.services import achievement_review as review

pytestmark = pytest.mark.usefixtures("clean_tables")

BODIES = ["Cut the import from 42 minutes to 9 minutes", "Add retry budget", "Tidy tests"]
PENDING = [
    {"text": "10x", "source_quote": "ten", "evidence_ids": [], "verified": "needs_confirmation"}
]


@pytest.fixture(autouse=True)
def _key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "gemini_api_key", "test-key")


async def seeded(**kwargs: Any) -> tuple[uuid.UUID, uuid.UUID, list[uuid.UUID]]:
    candidate_id, _, item_ids = await seed_evidence_chunk(bodies=BODIES)
    use = kwargs.pop("item_ids", item_ids[:1])
    achievement_id = await seed_achievement(candidate_id, item_ids=use, **kwargs)
    return candidate_id, achievement_id, item_ids


async def revisions(achievement_id: uuid.UUID) -> list[AchievementRevision]:
    async with session_factory() as session:
        rows = (
            await session.execute(
                select(AchievementRevision)
                .where(AchievementRevision.achievement_id == achievement_id)
                .order_by(AchievementRevision.created_at, AchievementRevision.id)
            )
        ).scalars()
        return list(rows)


async def load(achievement_id: uuid.UUID) -> Achievement:
    async with session_factory() as session:
        return await session.get_one(Achievement, achievement_id)


async def call(fn: Any, *args: Any) -> Any:
    async with session_factory() as session:
        result = await fn(session, *args)
        await session.commit()
        return result


async def test_approving_without_evidence_is_refused_with_the_reason() -> None:
    _, achievement_id, _ = await seeded(item_ids=[])

    with pytest.raises(AchievementConflictError, match="no evidence link"):
        await call(review.transition, achievement_id, AchievementStatus.approved)

    assert (await load(achievement_id)).status is AchievementStatus.draft
    assert await revisions(achievement_id) == []


async def test_approving_with_an_unconfirmed_metric_is_refused() -> None:
    _, achievement_id, _ = await seeded(metrics=PENDING)

    with pytest.raises(AchievementConflictError, match="need confirmation"):
        await call(review.transition, achievement_id, AchievementStatus.approved)


async def test_approval_writes_exactly_one_status_revision_and_embeds_if_missing() -> None:
    _, achievement_id, _ = await seeded()

    response = await call(review.transition, achievement_id, AchievementStatus.approved)

    assert response.status is AchievementStatus.approved
    assert (await load(achievement_id)).embedding is not None
    (revision,) = await revisions(achievement_id)
    assert revision.source.value == "status_change"
    assert revision.diff == {"status": ["draft", "approved"]}


@pytest.mark.parametrize(
    ("start", "target"),
    [
        ("rejected", "approved"),
        ("draft", "archived"),
        ("archived", "draft"),
        ("approved", "rejected"),
    ],
)
async def test_invalid_transitions_are_refused(start: str, target: str) -> None:
    _, achievement_id, _ = await seeded(status=start)

    with pytest.raises(AchievementConflictError, match="cannot move"):
        await call(review.transition, achievement_id, AchievementStatus(target))


async def test_unapprove_and_restore_round_trip_with_revisions() -> None:
    _, achievement_id, _ = await seeded(status="approved", stale=True)

    await call(review.transition, achievement_id, AchievementStatus.draft)
    back = await load(achievement_id)
    await call(review.transition, achievement_id, AchievementStatus.rejected)
    await call(review.transition, achievement_id, AchievementStatus.draft)

    assert back.status is AchievementStatus.draft
    assert back.evidence_stale_at is None
    assert [r.diff["status"] for r in await revisions(achievement_id)] == [
        ["approved", "draft"],
        ["draft", "rejected"],
        ["rejected", "draft"],
    ]


async def test_edit_writes_one_manual_revision_with_a_field_diff() -> None:
    _, achievement_id, _ = await seeded(skills=["Go"])

    response = await call(
        review.edit,
        achievement_id,
        AchievementUpdate(title="Faster import", difficulty=4, skills=["js", "go", "JavaScript"]),
    )

    assert response.skills == ["JavaScript", "Go"]
    stored = await load(achievement_id)
    assert (stored.title, stored.difficulty, stored.edited_by_user) == ("Faster import", 4, True)
    (revision,) = await revisions(achievement_id)
    assert revision.source.value == "manual_edit"
    assert revision.diff == {
        "title": ["Faster nightly import", "Faster import"],
        "difficulty": [3, 4],
        "skills": [["Go"], ["JavaScript", "Go"]],
    }


async def test_an_edit_that_changes_nothing_writes_no_revision() -> None:
    _, achievement_id, _ = await seeded()

    await call(review.edit, achievement_id, AchievementUpdate(title="Faster nightly import"))

    assert await revisions(achievement_id) == []
    assert (await load(achievement_id)).edited_by_user is False


async def test_edit_validates_dates_and_employer() -> None:
    _, achievement_id, _ = await seeded()

    with pytest.raises(InvalidAchievementInputError):
        await call(
            review.edit,
            achievement_id,
            AchievementUpdate(time_start=date(2024, 5, 1), time_end=date(2024, 4, 1)),
        )
    with pytest.raises(InvalidAchievementInputError, match="experience entries"):
        await call(
            review.edit,
            achievement_id,
            AchievementUpdate(employer_ref={"company": "Nowhere Inc", "start_date": "2020"}),
        )
    await call(review.edit, achievement_id, AchievementUpdate(employer_ref={"kind": "personal"}))
    assert (await load(achievement_id)).employer_ref == {"kind": "personal", "source": "user"}


async def test_editing_an_approved_row_reembeds_and_recomputes_privacy(
    fake_embedding: list[dict[str, Any]],
) -> None:
    candidate_id, _, item_ids = await seed_evidence_chunk(bodies=BODIES, private=True)
    achievement_id = await seed_achievement(
        candidate_id, item_ids=item_ids[:1], status="approved", embedding=fake_vector("old")
    )
    fake_embedding.clear()

    response = await call(
        review.edit, achievement_id, AchievementUpdate(action="Rewrote the loader")
    )

    assert response.status is AchievementStatus.approved
    assert len(fake_embedding) == 1
    stored = await load(achievement_id)
    assert stored.derived_from_private is True
    assert stored.embedding is not None
    assert list(stored.embedding) != fake_vector("old")


async def test_editing_a_draft_does_not_embed(fake_embedding: list[dict[str, Any]]) -> None:
    _, achievement_id, _ = await seeded()
    fake_embedding.clear()

    await call(review.edit, achievement_id, AchievementUpdate(action="Rewrote the loader"))

    assert fake_embedding == []


async def test_confirm_metric_as_written_marks_it_user_verified_and_unblocks_approval() -> None:
    _, achievement_id, _ = await seeded(metrics=PENDING)

    await call(
        review.confirm_metric, achievement_id, ConfirmMetricRequest(index=0, mode="as_written")
    )
    await call(review.transition, achievement_id, AchievementStatus.approved)

    stored = await load(achievement_id)
    assert stored.metrics[0]["verified"] == "user"
    assert stored.metrics[0]["text"] == "10x"
    first = (await revisions(achievement_id))[0]
    assert first.source.value == "metric_confirmation"
    assert first.diff["before"] == {"text": "10x", "verified": "needs_confirmation"}
    assert first.diff["after"] == {"text": "10x", "verified": "user"}
    assert "confirmed_at" in first.diff


async def test_confirm_metric_can_edit_the_value_and_rejects_a_bad_index() -> None:
    _, achievement_id, _ = await seeded(metrics=PENDING)

    await call(
        review.confirm_metric,
        achievement_id,
        ConfirmMetricRequest(index=0, mode="edit", text="about 8x"),
    )
    with pytest.raises(InvalidAchievementInputError):
        await call(
            review.confirm_metric, achievement_id, ConfirmMetricRequest(index=3, mode="as_written")
        )

    assert (await load(achievement_id)).metrics[0]["text"] == "about 8x"
    assert len(await revisions(achievement_id)) == 1


async def test_linking_evidence_adds_a_link_recomputes_privacy_and_writes_a_revision() -> None:
    candidate_id, _, public_items = await seed_evidence_chunk(bodies=BODIES)
    _, _, private_items = await seed_evidence_chunk(
        bodies=["Private fix"], private=True, candidate_id=candidate_id, project_key="ada/secret"
    )
    achievement_id = await seed_achievement(candidate_id, item_ids=public_items[:1])

    response = await call(
        review.link_evidence, achievement_id, EvidenceLinkCreate(item_id=private_items[0])
    )

    assert {link.item_id for link in response.evidence} == {public_items[0], private_items[0]}
    assert (await load(achievement_id)).derived_from_private is True
    (revision,) = await revisions(achievement_id)
    assert revision.diff == {"evidence": {"added": [str(private_items[0])]}}


async def test_linking_rejects_duplicates_and_foreign_items() -> None:
    _, achievement_id, item_ids = await seeded()
    _, _, foreign = await seed_evidence_chunk(bodies=["Someone else's work"])

    with pytest.raises(AchievementConflictError, match="already linked"):
        await call(review.link_evidence, achievement_id, EvidenceLinkCreate(item_id=item_ids[0]))
    with pytest.raises(EvidenceItemNotFoundError):
        await call(review.link_evidence, achievement_id, EvidenceLinkCreate(item_id=foreign[0]))
    with pytest.raises(EvidenceItemNotFoundError):
        await call(review.link_evidence, achievement_id, EvidenceLinkCreate(item_id=uuid.uuid4()))


async def test_unlinking_keeps_an_approved_achievement_evidenced_and_promotes_a_primary() -> None:
    _, achievement_id, item_ids = await seeded(status="approved", item_ids=None)
    async with session_factory() as session:
        for index, item_id in enumerate(item_ids[:2]):
            session.add(
                AchievementEvidence(
                    achievement_id=achievement_id,
                    item_id=item_id,
                    role="primary" if index == 0 else "supporting",
                )
            )
        await session.commit()

    response = await call(review.unlink_evidence, achievement_id, item_ids[0])
    with pytest.raises(AchievementConflictError, match="at least one evidence link"):
        await call(review.unlink_evidence, achievement_id, item_ids[1])
    with pytest.raises(EvidenceItemNotFoundError):
        await call(review.unlink_evidence, achievement_id, item_ids[2])

    assert [(link.item_id, link.role) for link in response.evidence] == [(item_ids[1], "primary")]
    assert len(await revisions(achievement_id)) == 1


async def test_unlinking_the_last_link_of_a_draft_is_allowed() -> None:
    _, achievement_id, item_ids = await seeded()

    response = await call(review.unlink_evidence, achievement_id, item_ids[0])

    assert response.evidence == []


async def test_acknowledge_clears_the_stale_flag_with_a_revision_and_is_a_noop_otherwise() -> None:
    _, achievement_id, _ = await seeded(status="approved", stale=True)

    await call(review.acknowledge, achievement_id)
    await call(review.acknowledge, achievement_id)

    assert (await load(achievement_id)).evidence_stale_at is None
    (revision,) = await revisions(achievement_id)
    assert revision.diff["reviewed"] is True


async def test_changed_evidence_flags_an_approved_achievement_and_re_review_clears_it() -> None:
    candidate_id, _, item_ids = await seed_evidence_chunk(bodies=BODIES)
    achievement_id = await seed_achievement(candidate_id, item_ids=item_ids[:1])
    await call(review.transition, achievement_id, AchievementStatus.approved)

    async def flag() -> int:
        async with session_factory() as session:
            flagged = await review.mark_stale_after_sync(session, candidate_id)
            await session.commit()
            return flagged

    assert await flag() == 0
    async with session_factory() as session:
        await session.execute(
            text("UPDATE evidence_item SET body = 'Rewritten after a refresh' WHERE id = :id"),
            {"id": item_ids[0]},
        )
        await session.commit()

    assert await flag() == 1
    assert await flag() == 0
    assert (await load(achievement_id)).evidence_stale_at is not None

    await call(review.acknowledge, achievement_id)

    assert await flag() == 0
    assert (await load(achievement_id)).evidence_stale_at is None


async def test_only_approved_achievements_with_changed_linked_items_are_flagged() -> None:
    candidate_id, _, item_ids = await seed_evidence_chunk(bodies=BODIES)
    draft = await seed_achievement(candidate_id, item_ids=item_ids[:1], title="Draft one")
    other = await seed_achievement(
        candidate_id, item_ids=item_ids[1:2], status="approved", title="Approved untouched"
    )
    async with session_factory() as session:
        await session.execute(
            text("UPDATE evidence_item SET body = 'changed' WHERE id = :id"), {"id": item_ids[0]}
        )
        await session.commit()

    async with session_factory() as session:
        flagged = await review.mark_stale_after_sync(session, candidate_id)
        await session.commit()

    assert flagged == 0
    assert (await load(draft)).evidence_stale_at is None
    assert (await load(other)).evidence_stale_at is None


async def test_bulk_approval_covers_only_clean_non_private_drafts_and_records_bulk() -> None:
    candidate_id, _, items = await seed_evidence_chunk(
        bodies=[*BODIES, "Four", "Five", "Six", "Seven"]
    )
    clean = await seed_achievement(candidate_id, item_ids=items[:1], title="Clean")
    private = await seed_achievement(
        candidate_id, item_ids=items[1:2], title="Private", private=True
    )
    flagged = await seed_achievement(
        candidate_id, item_ids=items[2:3], title="Flagged", flags=["contains_redaction_placeholder"]
    )
    pending = await seed_achievement(
        candidate_id, item_ids=items[3:4], title="Pending", metrics=PENDING
    )
    bare = await seed_achievement(candidate_id, item_ids=[], title="Bare")
    stale = await seed_achievement(candidate_id, item_ids=items[4:5], title="Stale", stale=True)

    eligible = await call(review.bulk_eligible)
    outcome = await call(
        review.bulk_approve, [clean, private, flagged, pending, bare, stale, uuid.uuid4(), clean]
    )

    assert [item.id for item in eligible.items] == [clean]
    assert eligible.count == 1
    assert eligible.items[0].evidence_count == 1
    assert outcome.approved == [clean]
    reasons = {skip.id: " ".join(skip.reasons) for skip in outcome.skipped}
    assert "private data" in reasons[private]
    assert "redaction placeholder" in reasons[flagged]
    assert "need confirmation" in reasons[pending]
    assert "no evidence link" in reasons[bare]
    assert "evidence changed" in reasons[stale]
    assert len(outcome.skipped) == 6
    (revision,) = await revisions(clean)
    assert revision.diff == {"status": ["draft", "approved"], "bulk": True}
    assert (await load(private)).status is AchievementStatus.draft


async def test_a_confirmed_repo_employer_is_applied_to_its_existing_achievements() -> None:
    candidate_id, _, items = await seed_evidence_chunk(bodies=BODIES)
    one = await seed_achievement(candidate_id, item_ids=items[:1], title="One")
    archived = await seed_achievement(
        candidate_id, item_ids=items[1:2], status="approved", title="Two"
    )
    elsewhere = await seed_achievement(
        candidate_id, item_ids=items[2:3], project_key="ada/other", title="Three"
    )
    async with session_factory() as session:
        (await session.get_one(Achievement, archived)).status = AchievementStatus.archived
        await session.commit()
    employer = {"kind": "personal", "source": "user"}

    first = await call(review.apply_scope_employer, candidate_id, "ada/engine", employer)
    second = await call(review.apply_scope_employer, candidate_id, "ada/engine", employer)

    assert (first, second) == (1, 0)
    assert (await load(one)).employer_ref == {"kind": "personal", "source": "scope"}
    assert (await load(archived)).employer_ref is None
    assert (await load(elsewhere)).employer_ref is None
    (revision,) = await revisions(one)
    assert revision.diff == {"employer_ref": [None, {"kind": "personal", "source": "scope"}]}


async def set_employer(achievement_id: uuid.UUID, employer: dict[str, Any] | None) -> None:
    async with session_factory() as session:
        (await session.get_one(Achievement, achievement_id)).employer_ref = employer
        await session.commit()


async def test_a_repo_employer_never_overwrites_one_the_user_chose_for_an_achievement() -> None:
    candidate_id, _, items = await seed_evidence_chunk(bodies=BODIES)
    chosen = await seed_achievement(candidate_id, item_ids=items[:1], title="Mine")
    following = await seed_achievement(candidate_id, item_ids=items[1:2], title="Follows")
    personal = {"kind": "personal", "source": "user"}
    await set_employer(chosen, personal)
    employer = {"company": "Acme Corp", "start_date": "Mar 2021", "source": "user"}

    changed = await call(review.apply_scope_employer, candidate_id, "ada/engine", employer)

    assert changed == 1
    assert (await load(chosen)).employer_ref == personal
    assert (await load(following)).employer_ref == {
        "company": "Acme Corp",
        "start_date": "Mar 2021",
        "source": "scope",
    }
    assert await revisions(chosen) == []


async def test_a_suggested_employer_is_still_replaced_by_the_repo_mapping() -> None:
    candidate_id, _, items = await seed_evidence_chunk(bodies=BODIES)
    suggested = await seed_achievement(candidate_id, item_ids=items[:1])
    await set_employer(
        suggested, {"company": "Old Co", "start_date": "2019", "source": "suggested"}
    )

    await call(
        review.apply_scope_employer,
        candidate_id,
        "ada/engine",
        {"kind": "personal", "source": "user"},
    )

    assert (await load(suggested)).employer_ref == {"kind": "personal", "source": "scope"}


async def test_clearing_an_achievements_employer_follows_its_repository_again() -> None:
    candidate_id, _, items = await seed_evidence_chunk(
        bodies=BODIES, scope_employer={"company": "Acme Corp", "start_date": "Mar 2021"}
    )
    achievement_id = await seed_achievement(candidate_id, item_ids=items[:1])
    await set_employer(achievement_id, {"kind": "personal", "source": "user"})

    await call(review.edit, achievement_id, AchievementUpdate(employer_ref=None))

    assert (await load(achievement_id)).employer_ref == {
        "company": "Acme Corp",
        "start_date": "Mar 2021",
        "source": "scope",
    }
    (revision,) = await revisions(achievement_id)
    assert "employer_ref" in revision.diff


async def test_clearing_the_employer_of_an_unmapped_repository_leaves_it_unset() -> None:
    _, achievement_id, _ = await seeded()
    await set_employer(achievement_id, {"kind": "personal", "source": "user"})

    await call(review.edit, achievement_id, AchievementUpdate(employer_ref=None))

    assert (await load(achievement_id)).employer_ref is None


async def test_revisions_are_listed_newest_first_with_a_total() -> None:
    _, achievement_id, _ = await seeded()
    await call(review.edit, achievement_id, AchievementUpdate(title="Second title"))
    await call(review.transition, achievement_id, AchievementStatus.approved)

    async with session_factory() as session:
        rows, total = await review.list_revisions(session, achievement_id)

    assert total == 2
    assert [row.source for row in rows] == ["status_change", "manual_edit"]


async def test_unknown_and_foreign_achievements_are_not_found() -> None:
    await seeded()
    stranger_candidate, _, stranger_items = await seed_evidence_chunk(bodies=["Other candidate"])
    foreign = await seed_achievement(stranger_candidate, item_ids=stranger_items[:1])

    # the single-candidate app owns the first candidate created; the second one's rows are foreign
    for achievement_id in (uuid.uuid4(), foreign):
        async with session_factory() as session:
            with pytest.raises(AchievementNotFoundError):
                await review.owned_achievement(session, achievement_id)
