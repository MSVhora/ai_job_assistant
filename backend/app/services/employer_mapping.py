import uuid
from dataclasses import dataclass, field
from datetime import date

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Profile
from app.schemas.profile import StructuredProfile
from app.services.profile_derivation import resolve_date

NON_REPO_PREFIXES = ("resume:", "note:", "link:")
PERSONAL_KIND = "personal"
SPAN_OVERLAP_SHARE = 0.5


@dataclass(frozen=True)
class Experience:
    company: str
    start_raw: str | None
    start: date | None
    end: date | None


@dataclass(frozen=True)
class ProfileFacts:
    skills: list[str] = field(default_factory=list[str])
    experiences: list[Experience] = field(default_factory=list[Experience])


def experiences_of(structured: StructuredProfile) -> list[Experience]:
    """One profile's employment entries with their parsed windows (company-less rows skipped)."""
    result: list[Experience] = []
    for job in structured.experience:
        if not job.company:
            continue
        start = resolve_date(job.start_date)
        end = resolve_date(job.end_date)
        if end is None and job.is_current:
            end = date.today()  # noqa: DTZ011
        result.append(
            Experience(
                job.company, job.start_date, start, max(start, end) if start and end else end
            )
        )
    return result


async def load_profile_facts(session: AsyncSession, candidate_id: uuid.UUID) -> ProfileFacts:
    """Skills and employment entries across all of the candidate's profiles (de-duplicated)."""
    skills: list[str] = []
    experiences: dict[tuple[str, str | None], Experience] = {}
    profiles = (
        (await session.execute(select(Profile).where(Profile.candidate_id == candidate_id)))
        .scalars()
        .all()
    )
    for profile in profiles:
        try:
            structured = StructuredProfile.model_validate(profile.structured_profile)
        except ValidationError:
            continue
        skills.extend(structured.skills)
        for experience in experiences_of(structured):
            experiences.setdefault((experience.company, experience.start_raw), experience)
    return ProfileFacts(skills=skills, experiences=list(experiences.values()))


def _overlap_days(start: date, end: date, experience: Experience) -> int:
    if experience.start is None:
        return 0
    experience_end = experience.end or experience.start
    return (min(end, experience_end) - max(start, experience.start)).days + 1


def suggest_employer(
    project_key: str | None, start: date | None, end: date | None, experiences: list[Experience]
) -> dict[str, object] | None:
    """Best date-overlap employer for a repository chunk (a suggestion until the user confirms)."""
    if project_key is None or project_key.startswith(NON_REPO_PREFIXES) or start is None:
        return None
    span_end = end or start
    best: tuple[int, Experience] | None = None
    for experience in experiences:
        overlap = _overlap_days(start, span_end, experience)
        if overlap > 0 and (best is None or overlap > best[0]):
            best = (overlap, experience)
    if best is None:
        return None
    return {"company": best[1].company, "start_date": best[1].start_raw, "source": "suggested"}


def suggest_for_scope(
    start: date | None, end: date | None, experiences: list[Experience]
) -> dict[str, object] | None:
    """Suggest an employer only when exactly one employment overlaps > 50 % of the repo's span."""
    if start is None:
        return None
    span_end = max(end or start, start)
    span_days = (span_end - start).days + 1
    matches = [
        experience
        for experience in experiences
        if _overlap_days(start, span_end, experience) > span_days * SPAN_OVERLAP_SHARE
    ]
    if len(matches) != 1:
        return None
    return {
        "company": matches[0].company,
        "start_date": matches[0].start_raw,
        "source": "suggested",
    }


def normalize_employer_ref(
    ref: dict[str, object] | None, experiences: list[Experience]
) -> dict[str, object] | None:
    """Validate a user-chosen mapping; returns the stored shape or raises ValueError."""
    if ref is None:
        return None
    if ref.get("kind") == PERSONAL_KIND:
        return {"kind": PERSONAL_KIND, "source": "user"}
    company = ref.get("company")
    start_date = ref.get("start_date")
    for experience in experiences:
        if experience.company == company and experience.start_raw == start_date:
            return {"company": company, "start_date": start_date, "source": "user"}
    msg = "employer must be one of your profile's experience entries or personal"
    raise ValueError(msg)
