import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.evidence_sources.base import EvidenceSourceError
from app.adapters.evidence_sources.registry import get_source
from app.core.errors import (
    ConflictNotFoundError,
    InvalidResumeDocumentError,
    MatchNotFoundError,
    ProfileNotFoundError,
    ResumeDocumentNotFoundError,
)
from app.core.pagination import DEFAULT_PAGE, Pagination
from app.models import (
    Achievement,
    AchievementStatus,
    Match,
    Profile,
    ResumeDocument,
    ResumeDocumentRevision,
    ResumeDocumentStatus,
)
from app.schemas.profile import StructuredProfile
from app.schemas.resume_document import (
    Conflict,
    ConflictResolution,
    ConflictsResponse,
    Layout,
    ResolveConflictRequest,
    ResumeContent,
    ResumeDocumentCreate,
    ResumeDocumentResponse,
    ResumeDocumentSummary,
    ResumeDocumentUpdate,
)
from app.services.evidence_items import candidate_id_or_none
from app.services.resume_mapping import profile_to_content
from app.services.resume_reconcile import GitHubIdentity, reconcile

logger = logging.getLogger(__name__)

MAX_REVISIONS = 20
NO_GITHUB_NOTE = "GitHub is not configured, so the identity check was skipped."
GITHUB_FAILED_NOTE = "GitHub could not be reached, so the identity check was skipped."


def _response(document: ResumeDocument) -> ResumeDocumentResponse:
    return ResumeDocumentResponse(
        id=document.id,
        profile_id=document.profile_id,
        match_id=document.match_id,
        title=document.title,
        page_target=document.page_target,
        status=document.status.value,
        version=document.version,
        updated_at=document.updated_at,
        jd_weight=document.jd_weight,
        template=document.template,
        content=ResumeContent.model_validate(document.content),
        layout=Layout.model_validate(document.layout),
        comments=document.comments,
        created_at=document.created_at,
    )


async def _owned_profile(session: AsyncSession, profile_id: uuid.UUID) -> Profile:
    candidate_id = await candidate_id_or_none(session)
    profile = await session.get(Profile, profile_id)
    if profile is None or candidate_id is None or profile.candidate_id != candidate_id:
        raise ProfileNotFoundError
    return profile


async def owned_document(session: AsyncSession, document_id: uuid.UUID) -> ResumeDocument:
    candidate_id = await candidate_id_or_none(session)
    document = await session.get(ResumeDocument, document_id)
    if document is None or candidate_id is None or document.candidate_id != candidate_id:
        raise ResumeDocumentNotFoundError
    return document


async def _snapshot(session: AsyncSession, document: ResumeDocument, source: str) -> None:
    session.add(
        ResumeDocumentRevision(
            document_id=document.id,
            version=document.version,
            content=document.content,
            source=source,
        )
    )
    await session.flush()
    keep = (
        select(ResumeDocumentRevision.id)
        .where(ResumeDocumentRevision.document_id == document.id)
        .order_by(ResumeDocumentRevision.version.desc())
        .limit(MAX_REVISIONS)
    )
    await session.execute(
        delete(ResumeDocumentRevision).where(
            ResumeDocumentRevision.document_id == document.id,
            ResumeDocumentRevision.id.not_in(keep),
        )
    )


async def create_document(
    session: AsyncSession, payload: ResumeDocumentCreate
) -> ResumeDocumentResponse:
    profile = await _owned_profile(session, payload.profile_id)
    if payload.match_id is not None:
        match = await session.get(Match, payload.match_id)
        if match is None or match.profile_id != profile.id:
            raise MatchNotFoundError
    structured = StructuredProfile.model_validate(profile.structured_profile)
    document = ResumeDocument(
        candidate_id=profile.candidate_id,
        profile_id=profile.id,
        match_id=payload.match_id,
        title=payload.title or f"{profile.name} resume"[:200],
        page_target=payload.page_target,
        content=profile_to_content(structured).model_dump(mode="json"),
    )
    session.add(document)
    await session.flush()
    await session.refresh(document)
    await _snapshot(session, document, "create")
    return _response(document)


async def get_document(session: AsyncSession, document_id: uuid.UUID) -> ResumeDocumentResponse:
    return _response(await owned_document(session, document_id))


async def count_documents(session: AsyncSession, profile_id: uuid.UUID | None = None) -> int:
    candidate_id = await candidate_id_or_none(session)
    if candidate_id is None:
        return 0
    query = select(func.count()).where(ResumeDocument.candidate_id == candidate_id)
    if profile_id is not None:
        query = query.where(ResumeDocument.profile_id == profile_id)
    return (await session.execute(query)).scalar_one()


async def list_documents(
    session: AsyncSession,
    profile_id: uuid.UUID | None = None,
    page: Pagination = DEFAULT_PAGE,
) -> list[ResumeDocumentSummary]:
    candidate_id = await candidate_id_or_none(session)
    if candidate_id is None:
        return []
    query = select(ResumeDocument).where(ResumeDocument.candidate_id == candidate_id)
    if profile_id is not None:
        query = query.where(ResumeDocument.profile_id == profile_id)
    rows = await session.execute(
        query.order_by(ResumeDocument.updated_at.desc(), ResumeDocument.id)
        .limit(page.limit)
        .offset(page.offset)
    )
    return [
        ResumeDocumentSummary(
            id=row.id,
            profile_id=row.profile_id,
            match_id=row.match_id,
            title=row.title,
            page_target=row.page_target,
            status=row.status.value,
            version=row.version,
            updated_at=row.updated_at,
        )
        for row in rows.scalars()
    ]


async def update_document(
    session: AsyncSession, document_id: uuid.UUID, payload: ResumeDocumentUpdate
) -> ResumeDocumentResponse:
    document = await owned_document(session, document_id)
    fields = payload.model_dump(exclude_unset=True, exclude={"content", "status"})
    if "title" in fields and fields["title"] is None:
        raise InvalidResumeDocumentError
    for name, value in fields.items():
        if value is not None:
            setattr(document, name, value)
    if payload.status is not None:
        document.status = ResumeDocumentStatus(payload.status)
    if payload.content is not None:
        content = payload.content.model_dump(mode="json")
        if content != document.content:
            document.content = content
            document.version += 1
            await session.flush()
            await _snapshot(session, document, "manual_edit")
    await session.flush()
    await session.refresh(document)
    return _response(document)


async def delete_document(session: AsyncSession, document_id: uuid.UUID) -> None:
    document = await owned_document(session, document_id)
    await session.delete(document)
    await session.flush()


async def _approved_achievements(
    session: AsyncSession, candidate_id: uuid.UUID
) -> list[Achievement]:
    rows = await session.execute(
        select(Achievement)
        .where(
            Achievement.candidate_id == candidate_id,
            Achievement.status == AchievementStatus.approved,
        )
        .order_by(Achievement.created_at, Achievement.id)
    )
    return list(rows.scalars())


async def fetch_github_identity() -> tuple[GitHubIdentity | None, str | None]:
    """Name/location/email from GitHub's `/user`, fetched on demand and never stored."""
    source = get_source("github")
    if not source.is_configured():
        return None, NO_GITHUB_NOTE
    try:
        identity = await source.identify()
    except EvidenceSourceError as exc:
        logger.warning("resume.identity failed error=%s", type(exc).__name__)
        return None, GITHUB_FAILED_NOTE
    return GitHubIdentity(identity.name, identity.location, tuple(identity.emails)), None


def _resolutions(document: ResumeDocument) -> dict[str, ConflictResolution]:
    resolutions = (ConflictResolution.model_validate(row) for row in document.conflicts)
    return {resolution.key: resolution for resolution in resolutions}


async def detect_conflicts(
    session: AsyncSession, document: ResumeDocument, *, identity: GitHubIdentity | None = None
) -> list[Conflict]:
    profile = await session.get(Profile, document.profile_id)
    if profile is None:
        raise ProfileNotFoundError
    structured = StructuredProfile.model_validate(profile.structured_profile)
    achievements = await _approved_achievements(session, document.candidate_id)
    return reconcile(structured, achievements, identity)


async def get_conflicts(session: AsyncSession, document_id: uuid.UUID) -> ConflictsResponse:
    document = await owned_document(session, document_id)
    identity, note = await fetch_github_identity()
    detected = await detect_conflicts(session, document, identity=identity)
    resolved_keys = _resolutions(document).keys()
    return ConflictsResponse(
        open=[item for item in detected if item.key not in resolved_keys],
        resolved=[item for item in detected if item.key in resolved_keys],
        github_checked=identity is not None,
        note=note,
    )


async def resolve_conflict(
    session: AsyncSession, document_id: uuid.UUID, key: str, payload: ResolveConflictRequest
) -> ConflictsResponse:
    document = await owned_document(session, document_id)
    resolutions = _resolutions(document)
    if payload.action == "keep_as_is":
        identity, _ = await fetch_github_identity()
        detected = {
            item.key for item in await detect_conflicts(session, document, identity=identity)
        }
        if key not in detected and key not in resolutions:
            raise ConflictNotFoundError
        resolutions[key] = ConflictResolution(key=key, resolved_at=datetime.now(UTC))
    elif resolutions.pop(key, None) is None:
        raise ConflictNotFoundError
    document.conflicts = [item.model_dump(mode="json") for item in resolutions.values()]
    await session.flush()
    return await get_conflicts(session, document_id)


async def resync_identity(session: AsyncSession, document_id: uuid.UUID) -> ResumeDocumentResponse:
    """Re-copy basics, education and each matching employer's identity fields from the profile."""
    document = await owned_document(session, document_id)
    profile = await session.get(Profile, document.profile_id)
    if profile is None:
        raise ProfileNotFoundError
    fresh = profile_to_content(StructuredProfile.model_validate(profile.structured_profile))
    content = ResumeContent.model_validate(document.content)
    summary = content.basics.summary
    content.basics = fresh.basics.model_copy(update={"summary": summary})
    content.education = fresh.education
    by_key = {(job.company, job.start_date): job for job in fresh.work}
    for job in content.work:
        source = by_key.get((job.company, job.start_date))
        if source is not None:
            job.title = source.title
            job.location = source.location
            job.end_date = source.end_date
            job.is_current = source.is_current
    return await update_document(session, document_id, ResumeDocumentUpdate(content=content))
