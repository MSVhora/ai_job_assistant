import logging

from pydantic import ValidationError

from app.adapters.job_sources.base import JobPostingData
from app.adapters.llm import LLMError, embed
from app.core.config import get_settings
from app.models import Profile
from app.schemas.profile import StructuredProfile

logger = logging.getLogger(__name__)

MAX_EMBED_CHARS = 6000


def job_embed_text(title: str, description: str | None) -> str | None:
    body = (description or "").strip()
    if not body:
        return None
    return f"{title.strip()}\n{body}"[:MAX_EMBED_CHARS]


def profile_embed_text(profile: StructuredProfile) -> str:
    preferences = profile.preferences
    parts: list[str] = []
    target_title = preferences.target_title if preferences else None
    title = target_title or profile.headline
    if title:
        parts.append(f"Target role: {title}")
    if profile.skills:
        parts.append(f"Skills: {', '.join(profile.skills)}")
    if preferences and preferences.seniority:
        parts.append(f"Seniority: {preferences.seniority}")
    if profile.summary:
        parts.append(f"Summary: {profile.summary}")
    roles = [
        f"{item.title} at {item.company}" if item.company else item.title
        for item in profile.experience
        if item.title
    ]
    if roles:
        parts.append(f"Experience: {'; '.join(roles)}")
    if preferences and preferences.target_location:
        parts.append(f"Preferred location: {preferences.target_location}")
    if preferences and preferences.work_authorization:
        parts.append(f"Work authorization: {preferences.work_authorization}")
    return "\n".join(parts)[:MAX_EMBED_CHARS]


async def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    result = await embed(texts)
    expected_dim = get_settings().embedding_dimensions
    for vector in result.vectors:
        if len(vector) != expected_dim:
            raise LLMError(
                f"embedding dimension mismatch: got {len(vector)}, expected {expected_dim} "
                f"(embedding_model changed without a column migration?)"
            )
    return result.vectors


async def embed_postings(postings: list[JobPostingData]) -> list[list[float] | None]:
    texts = [job_embed_text(posting.title, posting.description) for posting in postings]
    embeddable = [(index, text) for index, text in enumerate(texts) if text is not None]
    vectors: list[list[float] | None] = [None] * len(postings)
    if not embeddable:
        return vectors
    result = await embed_texts([text for _, text in embeddable])
    for (index, _), vector in zip(embeddable, result, strict=True):
        vectors[index] = vector
    return vectors


async def refresh_profile_embedding(profile: Profile) -> bool:
    try:
        structured = StructuredProfile.model_validate(profile.structured_profile)
    except ValidationError:
        logger.warning(
            "profile.embedding skipped profile_id=%s (structured profile failed validation)",
            profile.id,
        )
        return False
    text = profile_embed_text(structured)
    if not text:
        profile.embedding = None
        return True
    try:
        vector = (await embed_texts([text]))[0]
    except LLMError as exc:
        logger.warning("profile.embedding failed profile_id=%s: %s", profile.id, exc)
        return False
    profile.embedding = vector
    return True
