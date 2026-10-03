import uuid

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.job_sources.base import json_array
from app.core.errors import InvalidEvidenceInputError, ProfileNotFoundError
from app.models import EvidenceItem, EvidenceItemStatus, EvidenceKind, Profile
from app.schemas.evidence import ResumeIngestResponse
from app.schemas.profile import StructuredProfile
from app.services.evidence_pipeline.dedupe import digest
from app.services.resume_service import get_or_create_candidate

PROFILE_IDS = "profile_ids"


def _entries(profile: StructuredProfile) -> list[tuple[str, str, str, str]]:
    """(section, project_key, title, bullet) for every resume bullet."""
    lines: list[tuple[str, str, str, str]] = []
    for job in profile.experience:
        owner = job.company or job.title
        if not owner:
            continue
        title = f"{job.title} at {job.company}" if job.title and job.company else owner
        lines.extend(
            ("experience", f"resume:{owner}", title, bullet.strip())
            for bullet in job.bullets
            if bullet.strip()
        )
    for project in profile.projects:
        extra = [project.description] if project.description else []
        lines.extend(
            ("projects", f"resume:{project.name}", project.name, bullet.strip())
            for bullet in [*extra, *project.bullets]
            if bullet.strip()
        )
    return lines


def _with_profile(meta: dict[str, object], profile_id: str) -> dict[str, object]:
    ids = [value for value in _profile_ids(meta) if value != profile_id]
    return {**meta, PROFILE_IDS: [*ids, profile_id]}


def _profile_ids(meta: dict[str, object]) -> list[str]:
    return [value for value in json_array(meta.get(PROFILE_IDS)) or [] if isinstance(value, str)]


async def ingest_profile(session: AsyncSession, profile_id: uuid.UUID) -> ResumeIngestResponse:
    """One `resume_line` item per bullet of a profile; identical bullets across profiles dedupe."""
    candidate = await get_or_create_candidate(session)
    profile = await session.get(Profile, profile_id)
    if profile is None or profile.candidate_id != candidate.id:
        raise ProfileNotFoundError
    try:
        structured = StructuredProfile.model_validate(profile.structured_profile)
    except ValidationError as exc:
        raise InvalidEvidenceInputError from exc
    pid = str(profile_id)
    wanted: dict[str, tuple[str, str, str, str]] = {}
    for section, project_key, title, bullet in _entries(structured):
        wanted[digest(project_key, title, bullet)] = (section, project_key, title, bullet)
    existing = {
        item.external_id: item
        for item in (
            await session.execute(
                select(EvidenceItem).where(
                    EvidenceItem.candidate_id == candidate.id,
                    EvidenceItem.kind == EvidenceKind.resume_line,
                )
            )
        )
        .scalars()
        .all()
    }
    result = ResumeIngestResponse(created=0, unchanged=0, excluded=0)
    for external_id, (section, project_key, title, bullet) in wanted.items():
        item = existing.get(external_id)
        if item is None:
            session.add(
                EvidenceItem(
                    candidate_id=candidate.id,
                    kind=EvidenceKind.resume_line,
                    external_id=external_id,
                    project_key=project_key,
                    title=title,
                    body=bullet,
                    status=EvidenceItemStatus.kept,
                    meta={"section": section, PROFILE_IDS: [pid]},
                    content_hash=external_id,
                )
            )
            result.created += 1
            continue
        if pid in _profile_ids(item.meta) and item.status is EvidenceItemStatus.kept:
            result.unchanged += 1
            continue
        item.meta = _with_profile(item.meta, pid)
        if item.status is EvidenceItemStatus.excluded:
            item.status = EvidenceItemStatus.kept
            result.created += 1
        else:
            result.unchanged += 1
    for external_id, item in existing.items():
        ids = _profile_ids(item.meta)
        if external_id in wanted or pid not in ids:
            continue
        remaining = [value for value in ids if value != pid]
        item.meta = {**item.meta, PROFILE_IDS: remaining}
        if not remaining and item.status is EvidenceItemStatus.kept:
            item.status = EvidenceItemStatus.excluded
            result.excluded += 1
    await session.flush()
    return result
