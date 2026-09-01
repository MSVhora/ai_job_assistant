import logging
import time
import uuid
from datetime import UTC, datetime
from urllib.parse import urlparse

from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.llm import LLMError, is_llm_configured, parse_structured
from app.core.config import get_settings
from app.core.errors import (
    LLMExtractionError,
    LLMNotConfiguredError,
    ResumeNotFoundError,
    ResumeTextUnavailableError,
)
from app.models import Resume
from app.schemas.profile import StructuredProfile
from app.schemas.resume import DraftProfileResponse

logger = logging.getLogger(__name__)

PROFILE_PROMPT_VERSION = "profile_prompt_v5"

EXTRACTION_SYSTEM = (
    "You extract structured data from resumes. Rules: "
    "extract only information explicitly present in the text; use null for anything missing; "
    "never invent employers, titles, dates, skills, certifications, or numbers; "
    "copy dates verbatim as written (e.g. 'Mar 2021', '2019 - Present'); "
    "set is_current only for the candidate's present role; "
    "deduplicate skills case-insensitively keeping the first written form; "
    "set contact.country to the ISO 3166-1 alpha-2 code (lowercase, e.g. 'de', 'in', 'us') "
    "of the candidate's location only when the text makes it unambiguous; "
    "map each resume section to its matching schema field (Experience, Education, Skills, "
    "Certifications, Awards, Projects) and put every other section - Publications, Languages, "
    "Volunteer work, Interests, Patents, Courses, References, or anything else - into "
    "extra_sections keeping the original section title and one entry per bullet or line; "
    "when a link has no label on the resume, infer it from the domain "
    "(e.g. LinkedIn, GitHub)."
)

_KNOWN_LINK_LABELS: tuple[tuple[str, str], ...] = (
    ("linkedin.com", "LinkedIn"),
    ("github.com", "GitHub"),
    ("gitlab.com", "GitLab"),
    ("x.com", "X"),
    ("twitter.com", "Twitter"),
    ("medium.com", "Medium"),
    ("stackoverflow.com", "Stack Overflow"),
    ("kaggle.com", "Kaggle"),
    ("dribbble.com", "Dribbble"),
    ("behance.net", "Behance"),
    ("scholar.google.com", "Google Scholar"),
    ("researchgate.net", "ResearchGate"),
    ("orcid.org", "ORCID"),
)


def _label_from_url(url: str) -> str:
    host = urlparse(url).netloc.removeprefix("www.").lower()
    for domain, label in _KNOWN_LINK_LABELS:
        if host == domain or host.endswith(f".{domain}"):
            return label
    return "Website"


def _enrich_link_labels(profile: StructuredProfile) -> StructuredProfile:
    for link in profile.contact.links:
        if not (link.label or "").strip():
            link.label = _label_from_url(link.url)
    return profile


def _build_prompt(resume_text: str, max_chars: int) -> str:
    text = resume_text[:max_chars]
    return f"Resume text:\n\n{text}\n\nExtract the structured profile JSON."


async def extract_resume_profile(
    session: AsyncSession, resume_id: uuid.UUID
) -> DraftProfileResponse:
    started = time.monotonic()
    settings = get_settings()
    if not is_llm_configured():
        raise LLMNotConfiguredError()

    resume = await session.get(Resume, resume_id)
    if resume is None:
        raise ResumeNotFoundError()
    if not (resume.extracted_text or "").strip():
        raise ResumeTextUnavailableError()

    prompt = _build_prompt(resume.extracted_text or "", settings.extraction_max_chars)
    try:
        result = await parse_structured(prompt, schema=StructuredProfile, system=EXTRACTION_SYSTEM)
    except LLMError as exc:
        logger.warning("profile.extract failed for resume %s: %s", resume_id, exc)
        raise LLMExtractionError(str(exc)) from exc

    profile = _enrich_link_labels(result.data)
    parsed_at = datetime.now(UTC)
    resume.draft_profile = profile.model_dump(mode="json")
    resume.parse_version = f"{settings.llm_model}+{PROFILE_PROMPT_VERSION}"
    resume.parsed_at = parsed_at
    await session.flush()

    logger.info(
        "profile.extract resume_id=%s duration_ms=%.0f prompt_tokens=%d completion_tokens=%d",
        resume_id,
        (time.monotonic() - started) * 1000,
        result.prompt_tokens,
        result.completion_tokens,
    )
    return DraftProfileResponse(
        resume_id=resume.id,
        candidate_id=resume.candidate_id,
        draft_profile=profile,
        parse_version=resume.parse_version,
        parsed_at=parsed_at,
    )
