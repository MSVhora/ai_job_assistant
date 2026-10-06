import logging
import time
import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.llm import LLMError, is_llm_configured, parse_structured
from app.core.errors import (
    LLMNotConfiguredError,
    LLMScoringError,
    ProfileNotFoundError,
    ResumeNotFoundError,
    ResumeTextUnavailableError,
)
from app.models import Profile, Resume
from app.schemas.ats import AtsScoreRequest, AtsScoreResponse
from app.schemas.profile import StructuredProfile

logger = logging.getLogger(__name__)

ATS_PROMPT_VERSION = "ats_prompt_v1"

SCORING_SYSTEM = (
    "You are an ATS (applicant tracking system) scoring engine and career coach. "
    "You are given a resume (extracted text or a structured candidate profile) and one "
    "job description. Grade how well a machine parser would rank this resume for that "
    "specific job. Rules:\n"
    "- Be concrete: judge only what the resume contains versus what the job asks for.\n"
    "- Score categories 0-100 where 100 means fully aligned; weights must reflect how "
    "ATS systems behave (keyword match and role alignment matter most; formatting less).\n"
    "- overall_score is the weighted mean of the category scores.\n"
    "- Extract hard-skill, tool, and qualification keywords from the job description; mark "
    "them critical/important/nice_to_have. Only list a keyword as matched when a human "
    "reading the resume would agree it is genuinely evidenced, not dreamed up.\n"
    "- Suggestions must be actionable and specific to this resume + job: say what to add "
    "or rewrite, where, and give a short rewrite example when useful. Never fabricate "
    "experience the candidate does not have; suggest honest ways to surface it instead. "
    "area must be exactly one of: keywords, format, summary, skills, experience, other. "
    "Keyword priority must be exactly one of: critical, important, nice_to_have. "
    "Suggestion priority must be exactly one of: high, medium, low.\n"
    "- Write in plain, encouraging, second-person language ('you')."
)


def _summarize_profile_value(label: str, value: str | None) -> list[str]:
    if not value or not value.strip():
        return []
    return [f"{label}: {value.strip()}"]


def _profile_to_text(profile: StructuredProfile) -> str:
    lines: list[str] = []
    contact = profile.contact
    lines.append(f"CONTACT: {contact.full_name}")
    lines.extend(_summarize_profile_value("email", contact.email))
    lines.extend(_summarize_profile_value("phone", contact.phone))
    lines.extend(_summarize_profile_value("location", contact.location))
    for link in contact.links:
        lines.append(f"link: {link.label or 'website'}: {link.url}")
    lines.extend(_summarize_profile_value("HEADLINE", profile.headline))
    lines.extend(_summarize_profile_value("SUMMARY", profile.summary))
    if profile.skills:
        lines.append(f"SKILLS: {', '.join(profile.skills)}")
    if profile.experience:
        lines.append("EXPERIENCE:")
        for item in profile.experience:
            dates = " - ".join(part for part in (item.start_date, item.end_date) if part)
            header = f"  {item.title} at {item.company} ({dates})".strip()
            lines.append(header)
            lines.extend(f"    - {bullet}" for bullet in item.bullets)
    if profile.projects:
        lines.append("PROJECTS:")
        for item in profile.projects:
            header = f"  {item.name} ({item.role})" if item.role else f"  {item.name}"
            lines.append(header)
            if item.description:
                lines.append(f"    {item.description}")
            lines.extend(f"    - {bullet}" for bullet in item.bullets)
            if item.technologies:
                lines.append(f"    tech: {', '.join(item.technologies)}")
    if profile.education:
        lines.append("EDUCATION:")
        for item in profile.education:
            lines.append(f"  {item.degree} in {item.field}, {item.institution} ({item.end_date})")
    if profile.certifications:
        lines.append("CERTIFICATIONS:")
        lines.extend(
            f"  {item.name} - {item.issuer or 'unknown issuer'}" for item in profile.certifications
        )
    if profile.awards:
        lines.append("AWARDS:")
        lines.extend(f"  {item.title} - {item.issuer or ''}" for item in profile.awards)
    if profile.extra_sections:
        lines.append("OTHER SECTIONS:")
        for section in profile.extra_sections:
            lines.append(f"  {section.title}:")
            lines.extend(f"    - {entry}" for entry in section.entries)
    return "\n".join(lines)


MAX_RESUME_CHARS = 20000
MAX_JD_CHARS = 15000


async def _load_resume_source_text(
    session: AsyncSession, resume_id: uuid.UUID
) -> tuple[str, uuid.UUID | None, uuid.UUID | None]:
    resume = await session.get(Resume, resume_id)
    if resume is None:
        raise ResumeNotFoundError()
    if not (resume.extracted_text or "").strip():
        raise ResumeTextUnavailableError()
    return resume.extracted_text or "", resume.id, None


async def _load_profile_source_text(
    session: AsyncSession, profile_id: uuid.UUID
) -> tuple[str, uuid.UUID | None, uuid.UUID | None]:
    profile = await session.get(Profile, profile_id)
    if profile is None:
        raise ProfileNotFoundError()
    return (
        _profile_to_text(StructuredProfile.model_validate(profile.structured_profile)),
        None,
        profile.id,
    )


def _build_prompt(resume_text: str, job_description: str) -> str:
    return (
        f"RESUME:\n\n{resume_text[:MAX_RESUME_CHARS]}\n\n"
        f"JOB DESCRIPTION:\n\n{job_description[:MAX_JD_CHARS]}\n\n"
        "Produce the ATS score report JSON."
    )


def _validate_overall_score(report: AtsScoreResponse) -> AtsScoreResponse:
    weighted = sum(item.score * item.weight for item in report.categories)
    total_weight = sum(item.weight for item in report.categories)
    if total_weight > 0 and report.categories:
        rebuilt = report.model_copy(update={"overall_score": round(weighted / total_weight, 1)})
        return rebuilt
    return report


async def score_ats(session: AsyncSession, payload: AtsScoreRequest) -> AtsScoreResponse:
    started = time.monotonic()
    if not is_llm_configured():
        raise LLMNotConfiguredError()

    resume_id: uuid.UUID | None
    profile_id: uuid.UUID | None
    if payload.resume_id is not None:
        source_text, resume_id, profile_id = await _load_resume_source_text(
            session, payload.resume_id
        )
    elif payload.profile_id is not None:
        source_text, resume_id, profile_id = await _load_profile_source_text(
            session, payload.profile_id
        )
    else:
        raise ProfileNotFoundError()

    prompt = _build_prompt(source_text, payload.job_description)
    try:
        result = await parse_structured(prompt, schema=AtsScoreResponse, system=SCORING_SYSTEM)
    except LLMError as exc:
        logger.warning("ats.score failed: %s", exc)
        raise LLMScoringError(str(exc)) from exc

    report = result.data.model_copy(
        update={
            "source_resume_id": resume_id,
            "source_profile_id": profile_id,
            "prompt_version": ATS_PROMPT_VERSION,
            "generated_at": datetime.now(UTC),
        }
    )
    report = _validate_overall_score(report)

    logger.info(
        "ats.score resume_id=%s profile_id=%s duration_ms=%.0f prompt_tokens=%d "
        "completion_tokens=%d overall_score=%.1f",
        resume_id,
        profile_id,
        (time.monotonic() - started) * 1000,
        result.prompt_tokens,
        result.completion_tokens,
        report.overall_score,
    )
    return report
