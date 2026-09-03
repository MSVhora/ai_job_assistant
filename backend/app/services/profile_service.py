import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import ValidationError
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import (
    ProfileNotFoundError,
    ResumeDraftUnavailableError,
    ResumeNotFoundError,
)
from app.models import Profile, ProfileRevision, Resume, RevisionSource
from app.schemas.profile import (
    ProfileCreate,
    ProfileResponse,
    ProfileSummary,
    ProfileUpdate,
    RevisionSummary,
    StoredPreferences,
    StructuredProfile,
    parse_stored_preferences,
)
from app.schemas.resume import DraftProfileResponse
from app.services import embedding, matching, query_builder
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


async def _latest_revision(session: AsyncSession, profile_id: uuid.UUID) -> ProfileRevision | None:
    result = await session.execute(
        select(ProfileRevision)
        .where(ProfileRevision.profile_id == profile_id)
        .order_by(ProfileRevision.created_at.desc())
        .limit(1)
    )
    return result.scalars().first()


async def _resume_filename(session: AsyncSession, resume_id: uuid.UUID | None) -> str | None:
    if resume_id is None:
        return None
    resume = await session.get(Resume, resume_id)
    return resume.original_filename if resume else None


def _revision_summary(revision: ProfileRevision) -> RevisionSummary:
    return RevisionSummary(
        id=revision.id, source=revision.source.value, created_at=revision.created_at
    )


def _profile_response(
    profile: Profile,
    source_resume_filename: str | None,
    revision: ProfileRevision | None,
) -> ProfileResponse:
    return ProfileResponse(
        profile_id=profile.id,
        name=profile.name,
        structured_profile=StructuredProfile.model_validate(profile.structured_profile),
        search_queries=query_builder.parse_stored(profile.search_queries),
        preferences=parse_stored_preferences(profile.preferences),
        source_resume_id=profile.source_resume_id,
        source_resume_filename=source_resume_filename,
        updated_at=profile.updated_at,
        last_revision=_revision_summary(revision) if revision is not None else None,
    )


async def list_profiles(session: AsyncSession) -> list[ProfileSummary]:
    result = await session.execute(select(Profile).order_by(Profile.created_at))
    summaries: list[ProfileSummary] = []
    for profile in result.scalars().all():
        filename = await _resume_filename(session, profile.source_resume_id)
        summaries.append(
            ProfileSummary(
                profile_id=profile.id,
                name=profile.name,
                source_resume_filename=filename,
                created_at=profile.created_at,
                updated_at=profile.updated_at,
            )
        )
    return summaries


async def get_profile(session: AsyncSession, profile_id: uuid.UUID) -> ProfileResponse:
    profile = await session.get(Profile, profile_id)
    if profile is None:
        raise ProfileNotFoundError()
    filename = await _resume_filename(session, profile.source_resume_id)
    revision = await _latest_revision(session, profile.id)
    return _profile_response(profile, filename, revision)


def _first_save_revisions(
    profile_id: uuid.UUID,
    draft: dict[str, Any] | None,
    new_profile: dict[str, Any],
) -> list[ProfileRevision]:
    if draft is not None:
        revisions = [
            ProfileRevision(
                profile_id=profile_id,
                source=RevisionSource.ai_extraction,
                diff=diff_profiles(None, draft),
                created_at=_next_timestamp(None),
            )
        ]
        if new_profile != draft:
            revisions.append(
                ProfileRevision(
                    profile_id=profile_id,
                    source=RevisionSource.manual_edit,
                    diff=diff_profiles(draft, new_profile),
                    created_at=_next_timestamp(revisions[-1].created_at),
                )
            )
        return revisions
    return [
        ProfileRevision(
            profile_id=profile_id,
            source=RevisionSource.manual_edit,
            diff=diff_profiles(None, new_profile),
            created_at=_next_timestamp(None),
        )
    ]


async def create_profile(session: AsyncSession, payload: ProfileCreate) -> ProfileResponse:
    candidate = await get_or_create_candidate(session)
    new_profile = payload.structured_profile.model_dump(mode="json")
    draft = None
    draft_queries: dict[str, Any] | None = None
    if payload.source_resume_id is not None:
        resume = await session.get(Resume, payload.source_resume_id)
        if resume is None or resume.candidate_id != candidate.id:
            raise ResumeNotFoundError()
        if resume.draft_profile is not None:
            draft = _normalized(resume.draft_profile)
        draft_queries = resume.search_queries

    profile = Profile(
        candidate_id=candidate.id,
        name=payload.name.strip(),
        structured_profile=new_profile,
        search_queries=draft_queries,
        source_resume_id=payload.source_resume_id,
    )
    session.add(profile)
    await session.flush()

    revisions = _first_save_revisions(profile.id, draft, new_profile)
    session.add_all(revisions)
    await session.flush()
    await embedding.refresh_profile_embedding(profile)
    await session.flush()
    await matching.rescore_matches(session, profile, invalidate_rationales=True)
    await session.flush()
    await session.refresh(profile)

    filename = await _resume_filename(session, profile.source_resume_id)
    logger.info("profile.created profile_id=%s revisions=%d", profile.id, len(revisions))
    return _profile_response(profile, filename, revisions[-1])


async def save_profile(
    session: AsyncSession, profile_id: uuid.UUID, payload: ProfileUpdate
) -> ProfileResponse:
    profile = await session.get(Profile, profile_id)
    if profile is None:
        raise ProfileNotFoundError()

    renamed = payload.name is not None and payload.name.strip() != profile.name
    if renamed:
        profile.name = payload.name.strip()

    last_revision: ProfileRevision | None = None
    if payload.structured_profile is not None:
        new_profile = payload.structured_profile.model_dump(mode="json")
        if payload.source_resume_id is not None:
            resume = await session.get(Resume, payload.source_resume_id)
            if resume is None or resume.candidate_id != profile.candidate_id:
                raise ResumeNotFoundError()
            profile.source_resume_id = resume.id

        source = (
            RevisionSource.reupload_merge
            if payload.source_resume_id is not None
            else RevisionSource.manual_edit
        )
        last_revision = ProfileRevision(
            profile_id=profile.id,
            source=source,
            diff=diff_profiles(_normalized(profile.structured_profile), new_profile),
            created_at=_next_timestamp(None),
        )
        profile.structured_profile = new_profile
        session.add(last_revision)

    await session.flush()
    if payload.structured_profile is not None:
        await embedding.refresh_profile_embedding(profile)
        await session.flush()
        await matching.rescore_matches(session, profile, invalidate_rationales=True)
        await session.flush()
    await session.refresh(profile)

    logger.info(
        "profile.saved profile_id=%s renamed=%s content=%s diff_fields=%s",
        profile.id,
        renamed,
        payload.structured_profile is not None,
        len(last_revision.diff) if last_revision else None,
    )
    filename = await _resume_filename(session, profile.source_resume_id)
    return _profile_response(profile, filename, last_revision)


async def update_preferences(
    session: AsyncSession, profile_id: uuid.UUID, payload: StoredPreferences
) -> StoredPreferences:
    """Persist the dashboard view preference (issue #11).

    Deliberately revision-free: a slider wiggle is a view preference, not
    profile content — no revision row, no embedding refresh, no match
    re-scoring. Matches re-order at read time instead.
    """
    profile = await session.get(Profile, profile_id)
    if profile is None:
        raise ProfileNotFoundError()
    profile.preferences = payload.model_dump(mode="json")
    await session.flush()
    await session.refresh(profile)
    logger.info(
        "profile.preferences_updated profile_id=%s priority=%.3f", profile.id, payload.priority
    )
    return parse_stored_preferences(profile.preferences) or payload


async def delete_profile(session: AsyncSession, profile_id: uuid.UUID) -> None:
    profile = await session.get(Profile, profile_id)
    if profile is None:
        raise ProfileNotFoundError()
    await session.execute(delete(ProfileRevision).where(ProfileRevision.profile_id == profile.id))
    await session.delete(profile)
    await session.flush()
    logger.info("profile.deleted profile_id=%s", profile_id)


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
        search_queries=query_builder.parse_stored(resume.search_queries),
    )
