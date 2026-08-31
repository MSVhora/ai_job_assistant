import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import (
    ProfileNotFoundError,
    ResumeDraftUnavailableError,
    ResumeNotFoundError,
)
from app.models import Candidate, ProfileRevision, Resume, RevisionSource
from app.schemas.profile import (
    ProfileResponse,
    ProfileUpdateRequest,
    RevisionSummary,
    StructuredProfile,
)
from app.schemas.resume import DraftProfileResponse
from app.services.resume_service import get_or_create_candidate

logger = logging.getLogger(__name__)


def _normalized(profile_dict: dict[str, Any]) -> dict[str, Any]:
    try:
        return StructuredProfile.model_validate(profile_dict).model_dump(mode="json")
    except ValidationError:
        logger.warning("profile normalization failed; diffing raw payload")
        return profile_dict


def diff_profiles(
    old: dict[str, Any] | None, new: dict[str, Any]
) -> dict[str, dict[str, Any | None]]:
    diff: dict[str, dict[str, Any | None]] = {}
    _diff_objects(old or {}, new, "", diff)
    return diff


def _diff_objects(
    old: dict[str, Any], new: dict[str, Any], prefix: str, diff: dict[str, dict[str, Any | None]]
) -> None:
    for key in old.keys() | new.keys():
        old_value = old.get(key)
        new_value = new.get(key)
        path = f"{prefix}{key}"
        if isinstance(old_value, dict) or isinstance(new_value, dict):
            _diff_objects(old_value or {}, new_value or {}, f"{path}.", diff)
        elif old_value != new_value:
            diff[path] = {"old": old_value, "new": new_value}


def _next_timestamp(previous: datetime | None) -> datetime:
    timestamp = datetime.now(UTC)
    if previous is not None and timestamp <= previous:
        timestamp = previous + timedelta(microseconds=1)
    return timestamp


async def _latest_revision(
    session: AsyncSession, candidate_id: uuid.UUID
) -> ProfileRevision | None:
    result = await session.execute(
        select(ProfileRevision)
        .where(ProfileRevision.candidate_id == candidate_id)
        .order_by(ProfileRevision.created_at.desc())
        .limit(1)
    )
    return result.scalars().first()


def _revision_summary(revision: ProfileRevision) -> RevisionSummary:
    return RevisionSummary(
        id=revision.id, source=revision.source.value, created_at=revision.created_at
    )


def _profile_response(candidate: Candidate, revision: ProfileRevision | None) -> ProfileResponse:
    structured_profile = StructuredProfile.model_validate(candidate.structured_profile)
    return ProfileResponse(
        candidate_id=candidate.id,
        structured_profile=structured_profile,
        updated_at=candidate.updated_at,
        last_revision=_revision_summary(revision) if revision is not None else None,
    )


async def get_profile(session: AsyncSession) -> ProfileResponse:
    result = await session.execute(select(Candidate).limit(1))
    candidate = result.scalars().first()
    if candidate is None or candidate.structured_profile is None:
        raise ProfileNotFoundError()
    revision = await _latest_revision(session, candidate.id)
    return _profile_response(candidate, revision)


async def save_profile(session: AsyncSession, payload: ProfileUpdateRequest) -> ProfileResponse:
    candidate = await get_or_create_candidate(session)
    new_profile = payload.structured_profile.model_dump(mode="json")

    draft: dict[str, Any] | None = None
    if payload.source_resume_id is not None:
        resume = await session.get(Resume, payload.source_resume_id)
        if resume is None or resume.candidate_id != candidate.id:
            raise ResumeNotFoundError()
        if resume.draft_profile is not None:
            draft = _normalized(resume.draft_profile)

    revisions: list[ProfileRevision] = []
    if candidate.structured_profile is None:
        if draft is not None:
            revisions.append(
                ProfileRevision(
                    candidate_id=candidate.id,
                    source=RevisionSource.ai_extraction,
                    diff=diff_profiles(None, draft),
                    created_at=_next_timestamp(None),
                )
            )
            if new_profile != draft:
                revisions.append(
                    ProfileRevision(
                        candidate_id=candidate.id,
                        source=RevisionSource.manual_edit,
                        diff=diff_profiles(draft, new_profile),
                        created_at=_next_timestamp(revisions[-1].created_at),
                    )
                )
        else:
            revisions.append(
                ProfileRevision(
                    candidate_id=candidate.id,
                    source=RevisionSource.manual_edit,
                    diff=diff_profiles(None, new_profile),
                    created_at=_next_timestamp(None),
                )
            )
    else:
        old_profile = _normalized(candidate.structured_profile)
        source = (
            RevisionSource.reupload_merge
            if payload.source_resume_id is not None
            else RevisionSource.manual_edit
        )
        revisions.append(
            ProfileRevision(
                candidate_id=candidate.id,
                source=source,
                diff=diff_profiles(old_profile, new_profile),
                created_at=_next_timestamp(None),
            )
        )

    candidate.structured_profile = new_profile
    session.add_all(revisions)
    await session.flush()
    await session.refresh(candidate)

    logger.info(
        "profile.save candidate_id=%s revisions=%d diff_fields=%d",
        candidate.id,
        len(revisions),
        sum(len(revision.diff) for revision in revisions),
    )
    return _profile_response(candidate, revisions[-1])


async def get_resume_draft(session: AsyncSession, resume_id: uuid.UUID) -> DraftProfileResponse:
    resume = await session.get(Resume, resume_id)
    if resume is None:
        raise ResumeNotFoundError()
    if resume.draft_profile is None or resume.parse_version is None or resume.parsed_at is None:
        raise ResumeDraftUnavailableError()
    return DraftProfileResponse(
        resume_id=resume.id,
        candidate_id=resume.candidate_id,
        draft_profile=StructuredProfile.model_validate(resume.draft_profile),
        parse_version=resume.parse_version,
        parsed_at=resume.parsed_at,
    )
