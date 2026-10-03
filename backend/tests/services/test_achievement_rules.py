from datetime import date

import pytest

from app.models import Achievement, AchievementStatus
from app.services.achievement_rules import (
    PLACEHOLDER_FLAG,
    TRANSITIONS,
    Facts,
    approval_blockers,
    bulk_blockers,
    can_transition,
    diff_fields,
    pending_metrics,
    snapshot,
)

D = AchievementStatus


def facts(**overrides: object) -> Facts:
    base: dict[str, object] = {
        "status": D.draft,
        "evidence_count": 2,
        "metrics": [],
        "review_flags": [],
        "stale": False,
        "private": False,
    }
    return Facts(**{**base, **overrides})  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("current", "target", "allowed"),
    [
        (D.draft, D.approved, True),
        (D.draft, D.rejected, True),
        (D.approved, D.draft, True),
        (D.approved, D.archived, True),
        (D.rejected, D.draft, True),
        (D.draft, D.archived, False),
        (D.rejected, D.approved, False),
        (D.approved, D.rejected, False),
        (D.archived, D.draft, False),
        (D.archived, D.approved, False),
        (D.draft, D.draft, False),
    ],
)
def test_the_state_table(current: D, target: D, allowed: bool) -> None:
    assert can_transition(current, target) is allowed


def test_archived_is_terminal() -> None:
    assert TRANSITIONS[D.archived] == frozenset()


def test_approval_needs_evidence_and_confirmed_metrics() -> None:
    assert approval_blockers(facts()) == []
    assert approval_blockers(facts(evidence_count=0)) == ["it has no evidence link"]
    pending = [{"verified": "needs_confirmation"}, {"verified": "evidence"}, {"verified": "user"}]
    assert approval_blockers(facts(metrics=pending)) == ["1 metric(s) still need confirmation"]
    assert pending_metrics(pending) == 1


def test_confirmed_metrics_do_not_block() -> None:
    assert approval_blockers(facts(metrics=[{"verified": "user"}, {"verified": "evidence"}])) == []


@pytest.mark.parametrize(
    ("override", "reason"),
    [
        ({"evidence_count": 0}, "no evidence link"),
        ({"metrics": [{"verified": "needs_confirmation"}]}, "need confirmation"),
        ({"status": D.approved}, "not a draft"),
        ({"review_flags": [PLACEHOLDER_FLAG]}, "redaction placeholder"),
        ({"stale": True}, "evidence changed"),
        ({"private": True}, "private data"),
    ],
)
def test_bulk_approval_excludes_each_unsafe_case(override: dict[str, object], reason: str) -> None:
    blockers = bulk_blockers(facts(**override))

    assert any(reason in blocker for blocker in blockers)


def test_a_clean_draft_is_bulk_eligible() -> None:
    assert bulk_blockers(facts()) == []


def test_diff_fields_reports_only_changed_fields_as_old_new_pairs() -> None:
    before = {"title": "A", "difficulty": 3, "skills": ["Go"], "result": None}
    after = {"title": "B", "difficulty": 3, "skills": ["Go", "Rust"], "result": None}

    assert diff_fields(before, after) == {"title": ["A", "B"], "skills": [["Go"], ["Go", "Rust"]]}
    assert diff_fields(before, before) == {}


def test_snapshot_serializes_dates_and_covers_the_editable_fields() -> None:
    achievement = Achievement(
        title="T",
        impact_type="other",
        difficulty=2,
        skills=["Go"],
        time_start=date(2024, 1, 2),
    )

    shot = snapshot(achievement)

    assert shot["time_start"] == "2024-01-02"
    assert shot["time_end"] is None
    assert shot["skills"] == ["Go"]
    assert set(shot) >= {"title", "result", "difficulty", "employer_ref", "project_key"}
