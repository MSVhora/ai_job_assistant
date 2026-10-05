import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import MatchNotFoundError
from app.models import JobPosting, Match, Profile
from app.schemas.profile import StructuredProfile
from app.services.agent_retrieval import ContextBlock
from app.services.prompts.agent import MAX_JOB_CHARS


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
    roles = [
        f"{job.title or 'Role'} at {job.company or 'an employer'} "
        f"({job.start_date or '?'} to {'present' if job.is_current else job.end_date or '?'})"
        for job in data.experience
    ]
    if roles:
        lines.append("Roles: " + "; ".join(roles))
    if data.skills:
        lines.append("Skills: " + ", ".join(data.skills))
    text = "\n".join(lines)
    return ContextBlock(
        marker="P",
        kind="profile",
        text=text,
        corpus=(text,),
        skills=tuple(data.skills),
        quote=data.headline or data.summary,
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
        marker="J", kind="job", text=text, corpus=(text,), url=posting.url, quote=heading
    )
