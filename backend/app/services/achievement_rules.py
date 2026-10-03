"""Pure review rules: the state table, field diffs and the approval / bulk-approval gates."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from app.models import Achievement, AchievementStatus

TRANSITIONS: dict[AchievementStatus, frozenset[AchievementStatus]] = {
    AchievementStatus.draft: frozenset({AchievementStatus.approved, AchievementStatus.rejected}),
    AchievementStatus.approved: frozenset({AchievementStatus.draft, AchievementStatus.archived}),
    AchievementStatus.rejected: frozenset({AchievementStatus.draft}),
    AchievementStatus.archived: frozenset(),
}
EDITABLE_FIELDS = (
    "title",
    "situation",
    "task",
    "action",
    "result",
    "skills",
    "impact_type",
    "difficulty",
    "project_key",
    "employer_ref",
    "time_start",
    "time_end",
)
NEEDS_CONFIRMATION = "needs_confirmation"
PLACEHOLDER_FLAG = "contains_redaction_placeholder"


@dataclass(frozen=True)
class Facts:
    status: AchievementStatus
    evidence_count: int
    metrics: Sequence[Mapping[str, Any]]
    review_flags: Sequence[str]
    stale: bool
    private: bool


def can_transition(current: AchievementStatus, target: AchievementStatus) -> bool:
    return target in TRANSITIONS[current]


def pending_metrics(metrics: Sequence[Mapping[str, Any]]) -> int:
    return sum(1 for metric in metrics if metric.get("verified") == NEEDS_CONFIRMATION)


def approval_blockers(facts: Facts) -> list[str]:
    """Why an achievement cannot be approved (hard requirements 1 and 2); empty means it can."""
    blockers: list[str] = []
    if facts.evidence_count < 1:
        blockers.append("it has no evidence link")
    pending = pending_metrics(facts.metrics)
    if pending:
        blockers.append(f"{pending} metric(s) still need confirmation")
    return blockers


def bulk_blockers(facts: Facts) -> list[str]:
    """Extra restrictions for bulk approval: clean, non-private, current items only."""
    blockers = approval_blockers(facts)
    if facts.status is not AchievementStatus.draft:
        blockers.append("it is not a draft")
    if PLACEHOLDER_FLAG in facts.review_flags:
        blockers.append("it contains a redaction placeholder")
    if facts.stale:
        blockers.append("its evidence changed")
    if facts.private:
        blockers.append("it is derived from private data and needs an individual look")
    return blockers


def _jsonable(value: object) -> object:
    if isinstance(value, datetime | date):
        return value.isoformat()
    return value


def snapshot(achievement: Achievement) -> dict[str, object]:
    return {name: _jsonable(getattr(achievement, name)) for name in EDITABLE_FIELDS}


def diff_fields(
    before: Mapping[str, object], after: Mapping[str, object]
) -> dict[str, list[object]]:
    """Field-level `{field: [old, new]}` for the fields that changed (no whole-row snapshots)."""
    return {
        name: [before.get(name), after.get(name)]
        for name in after
        if before.get(name) != after.get(name)
    }
