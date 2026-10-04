import logging
import uuid
from collections.abc import Mapping
from datetime import UTC, datetime

from sqlalchemy import delete, exists, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.llm import LLMError, is_llm_configured
from app.core.errors import (
    AchievementConflictError,
    AchievementNotFoundError,
    EvidenceItemNotFoundError,
    InvalidAchievementInputError,
)
from app.core.pagination import DEFAULT_PAGE, Pagination
from app.models import (
    Achievement,
    AchievementEvidence,
    AchievementRevision,
    AchievementRevisionSource,
    AchievementStatus,
    EvidenceItem,
    EvidenceScope,
    EvidenceSourceAccount,
)
from app.schemas.achievement import (
    AchievementResponse,
    AchievementUpdate,
    BulkApproveResponse,
    BulkEligibleItem,
    BulkEligibleResponse,
    BulkSkipped,
    ConfirmMetricRequest,
    EvidenceLinkCreate,
    RevisionResponse,
)
from app.services.achievement_rules import (
    EDITABLE_FIELDS,
    Facts,
    approval_blockers,
    bulk_blockers,
    can_transition,
    diff_fields,
    snapshot,
)
from app.services.achievements import build_responses
from app.services.embedding import embed_texts
from app.services.employer_mapping import load_profile_facts, normalize_employer_ref
from app.services.evidence_items import candidate_id_or_none
from app.services.skill_canon import canonicalize

logger = logging.getLogger(__name__)

__all__ = ["EDITABLE_FIELDS", "owned_achievement"]


SCOPE_SOURCE = "scope"
USER_SOURCE = "user"


def _set_by_user(employer_ref: dict[str, object] | None) -> bool:
    return employer_ref is not None and employer_ref.get("source") == USER_SOURCE


async def owned_achievement(session: AsyncSession, achievement_id: uuid.UUID) -> Achievement:
    candidate_id = await candidate_id_or_none(session)
    row = await session.get(Achievement, achievement_id)
    if row is None or candidate_id is None or row.candidate_id != candidate_id:
        raise AchievementNotFoundError
    return row


def add_revision(
    session: AsyncSession,
    achievement_id: uuid.UUID,
    source: AchievementRevisionSource,
    diff: Mapping[str, object],
) -> None:
    session.add(AchievementRevision(achievement_id=achievement_id, source=source, diff=dict(diff)))


async def links_of(session: AsyncSession, achievement_id: uuid.UUID) -> list[AchievementEvidence]:
    return list(
        (
            await session.execute(
                select(AchievementEvidence)
                .where(AchievementEvidence.achievement_id == achievement_id)
                .order_by(AchievementEvidence.role.desc(), AchievementEvidence.id)
            )
        ).scalars()
    )


async def recompute_private(session: AsyncSession, achievement: Achievement) -> None:
    flagged = (
        await session.execute(
            select(func.count())
            .select_from(AchievementEvidence)
            .join(EvidenceItem, EvidenceItem.id == AchievementEvidence.item_id)
            .where(
                AchievementEvidence.achievement_id == achievement.id,
                EvidenceItem.is_private.is_(True),
            )
        )
    ).scalar_one()
    achievement.derived_from_private = flagged > 0


def embedding_text(achievement: Achievement) -> str:
    parts = [
        achievement.title,
        achievement.situation or "",
        achievement.task or "",
        achievement.action or "",
        achievement.result or "",
    ]
    if achievement.skills:
        parts.append(f"Skills: {', '.join(achievement.skills)}")
    return "\n".join(part for part in parts if part)


async def refresh_embedding(achievement: Achievement) -> bool:
    """Re-embed after a content change; a provider failure leaves the old vector in place."""
    if not is_llm_configured():
        return False
    try:
        achievement.embedding = (await embed_texts([embedding_text(achievement)]))[0]
    except LLMError as exc:
        logger.warning("achievements.embedding failed error=%s", exc)
        return False
    return True


async def respond(session: AsyncSession, achievement: Achievement) -> AchievementResponse:
    await session.flush()
    await session.refresh(achievement)
    return (await build_responses(session, [achievement]))[0]


async def get_achievement(session: AsyncSession, achievement_id: uuid.UUID) -> AchievementResponse:
    return await respond(session, await owned_achievement(session, achievement_id))


async def _facts(session: AsyncSession, achievement: Achievement) -> Facts:
    count = (
        await session.execute(
            select(func.count())
            .select_from(AchievementEvidence)
            .where(AchievementEvidence.achievement_id == achievement.id)
        )
    ).scalar_one()
    return Facts(
        status=achievement.status,
        evidence_count=count,
        metrics=achievement.metrics,
        review_flags=achievement.review_flags,
        stale=achievement.evidence_stale_at is not None,
        private=achievement.derived_from_private,
    )


async def _repository_employer(
    session: AsyncSession, candidate_id: uuid.UUID, project_key: str | None
) -> dict[str, object] | None:
    """The employer of the achievement's repository, or None: what clearing an override means."""
    if not project_key:
        return None
    mapped = (
        await session.execute(
            select(EvidenceScope.employer_ref)
            .join(EvidenceSourceAccount, EvidenceSourceAccount.id == EvidenceScope.source_id)
            .where(
                EvidenceSourceAccount.candidate_id == candidate_id,
                EvidenceScope.ref == project_key,
            )
        )
    ).scalar_one_or_none()
    return {**mapped, "source": SCOPE_SOURCE} if mapped else None


async def edit(
    session: AsyncSession, achievement_id: uuid.UUID, payload: AchievementUpdate
) -> AchievementResponse:
    achievement = await owned_achievement(session, achievement_id)
    before = snapshot(achievement)
    data = payload.model_dump(exclude_unset=True)
    if "skills" in data:
        data["skills"] = canonicalize(data["skills"] or [])
    if "employer_ref" in data:
        if data["employer_ref"] is None:
            repository = data.get("project_key", achievement.project_key)
            data["employer_ref"] = await _repository_employer(
                session, achievement.candidate_id, repository
            )
        else:
            facts = await load_profile_facts(session, achievement.candidate_id)
            try:
                data["employer_ref"] = normalize_employer_ref(data["employer_ref"], facts.groups)
            except ValueError as exc:
                raise InvalidAchievementInputError(str(exc)) from exc
    for name, value in data.items():
        setattr(achievement, name, value)
    start, end = achievement.time_start, achievement.time_end
    if start is not None and end is not None and end < start:
        raise InvalidAchievementInputError
    changes = diff_fields(before, snapshot(achievement))
    if changes:
        achievement.edited_by_user = True
        add_revision(session, achievement.id, AchievementRevisionSource.manual_edit, changes)
        if achievement.status is AchievementStatus.approved:
            await recompute_private(session, achievement)
            await refresh_embedding(achievement)
    return await respond(session, achievement)


async def transition(
    session: AsyncSession,
    achievement_id: uuid.UUID,
    target: AchievementStatus,
    *,
    bulk: bool = False,
) -> AchievementResponse:
    achievement = await owned_achievement(session, achievement_id)
    current = achievement.status
    if not can_transition(current, target):
        msg = f"an achievement cannot move from {current.value} to {target.value}"
        raise AchievementConflictError(msg)
    if target is AchievementStatus.approved:
        blockers = approval_blockers(await _facts(session, achievement))
        if blockers:
            raise AchievementConflictError("cannot approve: " + "; ".join(blockers))
        if achievement.embedding is None:
            await refresh_embedding(achievement)
    diff: dict[str, object] = {"status": [current.value, target.value]}
    if bulk:
        diff["bulk"] = True
    if current is AchievementStatus.approved:
        achievement.evidence_stale_at = None
    achievement.status = target
    add_revision(session, achievement.id, AchievementRevisionSource.status_change, diff)
    return await respond(session, achievement)


async def confirm_metric(
    session: AsyncSession, achievement_id: uuid.UUID, payload: ConfirmMetricRequest
) -> AchievementResponse:
    achievement = await owned_achievement(session, achievement_id)
    metrics = [dict(metric) for metric in achievement.metrics]
    if payload.index >= len(metrics):
        msg = "there is no metric at that position"
        raise InvalidAchievementInputError(msg)
    metric = metrics[payload.index]
    before = {"text": metric.get("text"), "verified": metric.get("verified")}
    if payload.mode == "edit" and payload.text is not None:
        metric["text"] = payload.text
    metric["verified"] = "user"
    achievement.metrics = metrics
    achievement.edited_by_user = True
    add_revision(
        session,
        achievement.id,
        AchievementRevisionSource.metric_confirmation,
        {
            "index": payload.index,
            "mode": payload.mode,
            "before": before,
            "after": {"text": metric.get("text"), "verified": "user"},
            "confirmed_at": datetime.now(UTC).isoformat(),
        },
    )
    return await respond(session, achievement)


async def link_evidence(
    session: AsyncSession, achievement_id: uuid.UUID, payload: EvidenceLinkCreate
) -> AchievementResponse:
    achievement = await owned_achievement(session, achievement_id)
    item = await session.get(EvidenceItem, payload.item_id)
    if item is None or item.candidate_id != achievement.candidate_id:
        raise EvidenceItemNotFoundError
    links = await links_of(session, achievement.id)
    if any(link.item_id == item.id for link in links):
        msg = "that evidence is already linked"
        raise AchievementConflictError(msg)
    has_primary = any(link.role == "primary" for link in links)
    role = "supporting" if has_primary and payload.role == "primary" else payload.role
    session.add(
        AchievementEvidence(
            achievement_id=achievement.id,
            item_id=item.id,
            role="primary" if not links else role,
            quote=payload.quote,
        )
    )
    await session.flush()
    await recompute_private(session, achievement)
    add_revision(
        session,
        achievement.id,
        AchievementRevisionSource.manual_edit,
        {"evidence": {"added": [str(item.id)]}},
    )
    return await respond(session, achievement)


async def unlink_evidence(
    session: AsyncSession, achievement_id: uuid.UUID, item_id: uuid.UUID
) -> AchievementResponse:
    achievement = await owned_achievement(session, achievement_id)
    links = await links_of(session, achievement.id)
    target = next((link for link in links if link.item_id == item_id), None)
    if target is None:
        raise EvidenceItemNotFoundError
    if achievement.status is AchievementStatus.approved and len(links) == 1:
        msg = "an approved achievement must keep at least one evidence link"
        raise AchievementConflictError(msg)
    remaining = [link for link in links if link.item_id != item_id]
    await session.execute(delete(AchievementEvidence).where(AchievementEvidence.id == target.id))
    if target.role == "primary" and remaining:
        remaining[0].role = "primary"
    await session.flush()
    await recompute_private(session, achievement)
    add_revision(
        session,
        achievement.id,
        AchievementRevisionSource.manual_edit,
        {"evidence": {"removed": [str(item_id)]}},
    )
    return await respond(session, achievement)


async def acknowledge(session: AsyncSession, achievement_id: uuid.UUID) -> AchievementResponse:
    """Re-review after changed evidence: clears the flag and resets the staleness baseline."""
    achievement = await owned_achievement(session, achievement_id)
    stale_at = achievement.evidence_stale_at
    if stale_at is not None:
        achievement.evidence_stale_at = None
        add_revision(
            session,
            achievement.id,
            AchievementRevisionSource.status_change,
            {"evidence_stale_at": [stale_at.isoformat(), None], "reviewed": True},
        )
    return await respond(session, achievement)


async def list_revisions(
    session: AsyncSession, achievement_id: uuid.UUID, page: Pagination = DEFAULT_PAGE
) -> tuple[list[RevisionResponse], int]:
    await owned_achievement(session, achievement_id)
    total = (
        await session.execute(
            select(func.count())
            .select_from(AchievementRevision)
            .where(AchievementRevision.achievement_id == achievement_id)
        )
    ).scalar_one()
    rows = (
        (
            await session.execute(
                select(AchievementRevision)
                .where(AchievementRevision.achievement_id == achievement_id)
                .order_by(AchievementRevision.created_at.desc(), AchievementRevision.id)
                .limit(page.limit)
                .offset(page.offset)
            )
        )
        .scalars()
        .all()
    )
    return (
        [
            RevisionResponse(
                id=row.id, source=row.source.value, diff=row.diff, created_at=row.created_at
            )
            for row in rows
        ],
        total,
    )


async def bulk_eligible(session: AsyncSession) -> BulkEligibleResponse:
    candidate_id = await candidate_id_or_none(session)
    if candidate_id is None:
        return BulkEligibleResponse(count=0, items=[])
    drafts = (
        (
            await session.execute(
                select(Achievement)
                .where(
                    Achievement.candidate_id == candidate_id,
                    Achievement.status == AchievementStatus.draft,
                )
                .order_by(Achievement.created_at, Achievement.id)
            )
        )
        .scalars()
        .all()
    )
    items: list[BulkEligibleItem] = []
    for draft in drafts:
        facts = await _facts(session, draft)
        if not bulk_blockers(facts):
            items.append(
                BulkEligibleItem(
                    id=draft.id, title=draft.title, evidence_count=facts.evidence_count
                )
            )
    return BulkEligibleResponse(count=len(items), items=items)


async def bulk_approve(session: AsyncSession, ids: list[uuid.UUID]) -> BulkApproveResponse:
    approved: list[uuid.UUID] = []
    skipped: list[BulkSkipped] = []
    for achievement_id in dict.fromkeys(ids):
        try:
            achievement = await owned_achievement(session, achievement_id)
        except AchievementNotFoundError:
            skipped.append(BulkSkipped(id=achievement_id, reasons=["not found"]))
            continue
        blockers = bulk_blockers(await _facts(session, achievement))
        if blockers:
            skipped.append(BulkSkipped(id=achievement_id, reasons=blockers))
            continue
        await transition(session, achievement_id, AchievementStatus.approved, bulk=True)
        approved.append(achievement_id)
    return BulkApproveResponse(approved=approved, skipped=skipped)


async def mark_stale_after_sync(session: AsyncSession, candidate_id: uuid.UUID) -> int:
    """Flag approved achievements whose evidence changed after their last review event."""
    last_seen = (
        select(func.coalesce(func.max(AchievementRevision.created_at), Achievement.created_at))
        .where(AchievementRevision.achievement_id == Achievement.id)
        .correlate(Achievement)
        .scalar_subquery()
    )
    changed = exists().where(
        AchievementEvidence.achievement_id == Achievement.id,
        EvidenceItem.id == AchievementEvidence.item_id,
        EvidenceItem.updated_at > last_seen,
    )
    result = await session.execute(
        update(Achievement)
        .where(
            Achievement.candidate_id == candidate_id,
            Achievement.status == AchievementStatus.approved,
            Achievement.evidence_stale_at.is_(None),
            changed,
        )
        .values(evidence_stale_at=func.now())
        .returning(Achievement.id)
    )
    return len(result.all())


async def apply_scope_employer(
    session: AsyncSession,
    candidate_id: uuid.UUID,
    project_key: str,
    employer_ref: dict[str, object] | None,
) -> int:
    """A confirmed repo mapping applies to that repo's existing achievements, except the ones
    whose employer the user chose individually: that choice outranks the repository default."""
    stored = {**employer_ref, "source": SCOPE_SOURCE} if employer_ref else None
    rows = (
        (
            await session.execute(
                select(Achievement).where(
                    Achievement.candidate_id == candidate_id,
                    Achievement.project_key == project_key,
                    Achievement.status != AchievementStatus.archived,
                )
            )
        )
        .scalars()
        .all()
    )
    changed = 0
    for row in rows:
        if row.employer_ref == stored or _set_by_user(row.employer_ref):
            continue
        add_revision(
            session,
            row.id,
            AchievementRevisionSource.manual_edit,
            {"employer_ref": [row.employer_ref, stored]},
        )
        row.employer_ref = stored
        changed += 1
    return changed
