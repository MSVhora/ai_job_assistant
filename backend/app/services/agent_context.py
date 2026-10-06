import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import MatchNotFoundError
from app.models import JobPosting, Match, Profile
from app.schemas.profile import StructuredProfile
from app.services.agent_retrieval import ContextBlock, clean_excerpt
from app.services.prompts.agent import MAX_JOB_CHARS

MAX_ROLE_BULLETS = 3
MAX_BULLET_CHARS = 400


def _trim(text: str) -> str:
    """Cut at a word boundary, never mid-word."""
    if len(text) <= MAX_BULLET_CHARS:
        return text
    return text[:MAX_BULLET_CHARS].rsplit(" ", 1)[0].rstrip(".,;:") + "…"


def _period(start: str | None, end: str | None, *, current: bool = False) -> str:
    return f"{start or '?'} to {'present' if current else end or '?'}"


def _experience_lines(data: StructuredProfile) -> list[str]:
    lines: list[str] = []
    for job in data.experience:
        period = _period(job.start_date, job.end_date, current=job.is_current)
        lines.append(f"- {job.title or 'Role'} at {job.company or 'an employer'} ({period})")
        lines.extend(f"    * {_trim(bullet)}" for bullet in job.bullets[:MAX_ROLE_BULLETS])
    return lines


def _other_lines(data: StructuredProfile) -> list[str]:
    lines: list[str] = []
    for project in data.projects:
        detail = f": {project.description}" if project.description else ""
        tech = f" [{', '.join(project.technologies)}]" if project.technologies else ""
        lines.append(f"- {project.name}{detail}{tech}")
    for school in data.education:
        field = f", {school.field}" if school.field else ""
        lines.append(f"- {school.degree or 'Studies'}{field} at {school.institution or '?'}")
    return lines


def profile_block(profile: Profile) -> ContextBlock:
    """Identity facts from the stored profile, injected by code and never generated."""
    data = StructuredProfile.model_validate(profile.structured_profile)
    lines = [f"Name: {data.contact.full_name}"]
    if data.headline:
        lines.append(f"Headline: {data.headline}")
    if data.years_of_experience is not None:
        lines.append(f"Years of experience: {data.years_of_experience}")
    if data.summary:
        lines.append(f"Summary: {data.summary}")
    if data.skills:
        lines.append("Skills: " + ", ".join(data.skills))
    if data.experience:
        lines.extend(["Experience:", *_experience_lines(data)])
    if other := _other_lines(data):
        lines.extend(["Projects and education:", *other])
    text = "\n".join(lines)
    return ContextBlock(
        marker="P",
        kind="profile",
        text=text,
        corpus=(text,),
        label="Your profile",
        skills=tuple(data.skills),
        quote=clean_excerpt(data.headline or data.summary or lines[0]),
    )


async def job_block(
    session: AsyncSession, profile_id: uuid.UUID, match_id: uuid.UUID
) -> ContextBlock | None:
    """The matched posting and the match rationale; context about the job, not the candidate."""
    match = await session.get(Match, match_id)
    if match is None or match.profile_id != profile_id:
        raise MatchNotFoundError
    posting = await session.get(JobPosting, match.job_posting_id)
    if posting is None:
        return None
    heading = posting.title + (f" at {posting.company}" if posting.company else "")
    lines = [f"Job: {heading}"]
    if posting.description:
        lines.append(posting.description[:MAX_JOB_CHARS])
    if match.rationale:
        lines.append(f"Why this role was matched: {match.rationale}")
    text = "\n".join(lines)
    return ContextBlock(
        marker="J",
        kind="job",
        text=text,
        corpus=(text,),
        label=heading,
        url=posting.url,
        quote=heading,
    )
