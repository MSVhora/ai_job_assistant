import hashlib
import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.llm import LLMTask, parse_structured
from app.core.errors import InvalidResumeDocumentError, MatchNotFoundError
from app.models import JobPosting, Match
from app.schemas.resume_document import JDAnalysis
from app.services.llm_cache import cached_parse_structured
from app.services.prompts.jd import JD_PROMPT_VERSION, SYSTEM_PROMPT, build_prompt

logger = logging.getLogger(__name__)

EXPECTED_COMPLETION_TOKENS = 500


def jd_hash(text: str) -> str:
    return hashlib.sha256(" ".join(text.split()).encode()).hexdigest()


async def analyze_jd(session: AsyncSession, text: str) -> JDAnalysis:
    """Structured JD analysis on the cheap model; cached by the JD text."""
    result = await cached_parse_structured(
        session,
        task=LLMTask.classify,
        prompt_version=JD_PROMPT_VERSION,
        key_parts={"jd": " ".join(text.split())},
        schema=JDAnalysis,
        call=lambda: parse_structured(
            build_prompt(text),
            schema=JDAnalysis,
            system=SYSTEM_PROMPT,
            temperature=0.0,
            task=LLMTask.classify,
        ),
    )
    return result.data


async def jd_from_match(session: AsyncSession, profile_id: uuid.UUID, match_id: uuid.UUID) -> str:
    """The match's posting text plus the match rationale; the match must belong to the profile."""
    match = await session.get(Match, match_id)
    if match is None or match.profile_id != profile_id:
        raise MatchNotFoundError
    posting = await session.get(JobPosting, match.job_posting_id)
    description = (posting.description or "").strip() if posting else ""
    if posting is None or not description:
        msg = "the match's posting has no job description to tailor to"
        raise InvalidResumeDocumentError(msg)
    parts = [
        f"{posting.title}" + (f" at {posting.company}" if posting.company else ""),
        description,
    ]
    if match.rationale:
        parts.append(f"Why this role was matched: {match.rationale}")
    return "\n\n".join(parts)
