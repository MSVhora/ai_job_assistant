import logging
import uuid
from datetime import UTC, datetime

from pydantic import BaseModel, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.llm import LLMError, is_llm_configured, parse_structured
from app.core.config import get_settings
from app.core.errors import (
    LLMQueryGenerationError,
    NoJobSourcesConfiguredError,
    ProfileNotFoundError,
    UnknownJobSourceError,
)
from app.models import Profile
from app.schemas.job_search import (
    SearchQueriesResponse,
    SourceQuerySpec,
    StoredSearchQueries,
)
from app.schemas.profile import StructuredProfile
from app.services import sources as sources_service

logger = logging.getLogger(__name__)

PROMPT_VERSION = "search_query_v1"
GENERATION_TEMPERATURE = 0.8

QUERY_SYSTEM = (
    "You write job-search query specs for a candidate. For every source listed in the "
    "request, produce: title = an exact job-title phrase including seniority when known; "
    "skills = up to 3 short, high-signal skill keywords (single words or short tool names); "
    "exclude = up to 2 terms that would pull in wrong-level results (may be an empty list). "
    "Never include a location or salary in title, skills, or exclude - those travel as "
    "structured filters. Use only the provided candidate context; never invent skills."
)


class _GeneratedQueries(BaseModel):
    queries: dict[str, SourceQuerySpec]


def parse_stored(raw: object) -> StoredSearchQueries | None:
    if not isinstance(raw, dict):
        return None
    try:
        return StoredSearchQueries.model_validate(raw)
    except ValidationError:
        logger.warning("stored search queries failed validation; ignoring")
        return None


def serialize(stored: StoredSearchQueries) -> dict[str, object]:
    return stored.model_dump(mode="json")


def _candidate_context(profile: StructuredProfile) -> str:
    preferences = profile.preferences
    lines: list[str] = []
    if preferences is not None and preferences.target_title:
        lines.append(f"target title: {preferences.target_title}")
    if profile.headline:
        lines.append(f"headline: {profile.headline}")
    if profile.skills:
        lines.append(f"skills: {', '.join(profile.skills[:12])}")
    if preferences is not None and preferences.seniority is not None:
        lines.append(f"seniority: {preferences.seniority}")
    body = "\n".join(lines) if lines else "(no title or skills captured yet)"
    return f"Candidate context:\n{body}"


async def generate_queries(
    profile: StructuredProfile,
    sources: list[str],
    *,
    previous: dict[str, SourceQuerySpec] | None = None,
) -> StoredSearchQueries:
    if not is_llm_configured():
        raise LLMQueryGenerationError("LLM provider is not configured")
    if not sources:
        raise LLMQueryGenerationError("no sources requested")

    context = _candidate_context(profile)
    previous_block = ""
    if previous:
        previous_block = (
            "\n\nThe previously generated queries were:\n"
            + "\n".join(f"- {name}: {spec.model_dump_json()}" for name, spec in previous.items())
            + "\n\nProduce a fresh, equally strong variant for each source. "
            "Do not repeat the previous text verbatim."
        )
    prompt = (
        f"{context}\n\nSources needing a query spec: {', '.join(sources)}{previous_block}\n\n"
        "Write the query spec JSON."
    )

    try:
        result = await parse_structured(
            prompt,
            schema=_GeneratedQueries,
            system=QUERY_SYSTEM,
            temperature=GENERATION_TEMPERATURE,
        )
    except LLMError as exc:
        logger.warning("query generation failed: %s", exc)
        raise LLMQueryGenerationError(str(exc)) from exc

    missing = [name for name in sources if name not in result.data.queries]
    if missing:
        raise LLMQueryGenerationError(f"query generation missing sources: {', '.join(missing)}")

    settings = get_settings()
    return StoredSearchQueries(
        queries={name: result.data.queries[name] for name in sources},
        generated_at=datetime.now(UTC),
        generated_by=settings.llm_model,
        prompt_version=PROMPT_VERSION,
    )


async def regenerate_for_profile(
    session: AsyncSession, profile_id: uuid.UUID, sources: list[str] | None
) -> SearchQueriesResponse:
    profile = await session.get(Profile, profile_id)
    if profile is None:
        raise ProfileNotFoundError()
    structured = StructuredProfile.model_validate(profile.structured_profile)

    enabled = await sources_service.enabled_sources(session)
    if not enabled:
        raise NoJobSourcesConfiguredError()
    known = {source.name for source in enabled}
    names = sources if sources is not None else sorted(known)
    for name in names:
        if name not in known:
            raise UnknownJobSourceError(f"job source is not enabled: {name}")

    stored = parse_stored(profile.search_queries)
    result = await generate_queries(structured, names, previous=stored.queries if stored else None)
    profile.search_queries = serialize(result)
    await session.flush()

    logger.info(
        "queries.regenerated profile_id=%s sources=%s",
        profile_id,
        names,
    )
    return SearchQueriesResponse(
        queries=result.queries,
        generated_at=result.generated_at,
        generated_by=result.generated_by,
    )
