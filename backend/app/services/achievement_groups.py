import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Achievement, AchievementStatus
from app.schemas.achievement import AchievementGroupsResponse, EmployerGroup, RepositoryGroup
from app.services.achievement_rules import Facts, bulk_blockers
from app.services.achievements import evidence_counts
from app.services.evidence_items import candidate_id_or_none

Kind = Literal["employer", "personal", "unassigned"]
PERSONAL_LABEL = "Personal"
UNASSIGNED_LABEL = "No employer"


@dataclass
class _Counts:
    draft_ids: list[uuid.UUID] = field(default_factory=list[uuid.UUID])
    eligible_ids: list[uuid.UUID] = field(default_factory=list[uuid.UUID])

    @property
    def total(self) -> int:
        return len(self.draft_ids)

    @property
    def eligible(self) -> int:
        return len(self.eligible_ids)

    def add(self, achievement_id: uuid.UUID, *, eligible: bool) -> None:
        self.draft_ids.append(achievement_id)
        if eligible:
            self.eligible_ids.append(achievement_id)


@dataclass
class _Employer:
    kind: Kind
    label: str
    counts: _Counts = field(default_factory=_Counts)
    repositories: dict[str | None, _Counts] = field(default_factory=dict[str | None, _Counts])


def _employer_key(ref: Mapping[str, object] | None) -> tuple[Kind, str]:
    if ref is None:
        return "unassigned", UNASSIGNED_LABEL
    if ref.get("kind") == "personal":
        return "personal", PERSONAL_LABEL
    company = ref.get("company")
    if isinstance(company, str) and company:
        return "employer", company
    return "unassigned", UNASSIGNED_LABEL


async def draft_groups(session: AsyncSession) -> AchievementGroupsResponse:
    """Drafts grouped by employer then repository, each with how many a bulk approve could take."""
    candidate_id = await candidate_id_or_none(session)
    if candidate_id is None:
        return AchievementGroupsResponse(groups=[])
    drafts = (
        (
            await session.execute(
                select(Achievement).where(
                    Achievement.candidate_id == candidate_id,
                    Achievement.status == AchievementStatus.draft,
                )
            )
        )
        .scalars()
        .all()
    )
    counts = await evidence_counts(session, [draft.id for draft in drafts])
    employers: dict[tuple[Kind, str], _Employer] = {}
    for draft in drafts:
        kind, label = _employer_key(draft.employer_ref)
        facts = Facts(
            status=draft.status,
            evidence_count=counts.get(draft.id, 0),
            metrics=draft.metrics,
            review_flags=draft.review_flags,
            stale=draft.evidence_stale_at is not None,
            private=draft.derived_from_private,
        )
        eligible = not bulk_blockers(facts)
        group = employers.setdefault((kind, label), _Employer(kind=kind, label=label))
        group.counts.add(draft.id, eligible=eligible)
        group.repositories.setdefault(draft.project_key, _Counts()).add(draft.id, eligible=eligible)
    ordered = sorted(employers.values(), key=lambda group: (-group.counts.total, group.label))
    return AchievementGroupsResponse(
        groups=[
            EmployerGroup(
                kind=group.kind,
                label=group.label,
                total=group.counts.total,
                eligible=group.counts.eligible,
                repositories=[
                    RepositoryGroup(
                        project_key=key,
                        total=value.total,
                        eligible=value.eligible,
                        draft_ids=value.draft_ids,
                        eligible_ids=value.eligible_ids,
                    )
                    for key, value in sorted(
                        group.repositories.items(), key=lambda pair: (-pair[1].total, pair[0] or "")
                    )
                ],
            )
            for group in ordered
        ]
    )


__all__ = ["draft_groups"]
