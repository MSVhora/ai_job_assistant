"""On-demand tune-my-queries (#39).

Aggregates engagement-signal buckets from stored matches (nothing new is
tracked here — this consumes only what /signals and /apply recorded), feeds
the aggregates plus the profile digest to one LLM call, and rewrites the
profile's per-source query specs. The stored `queries_input_hash` is then
overwritten with the hash of the *current* inputs so `ensure_queries_fresh`
sees a hit and cannot silently revert the tuned queries behind the user's
back.

Manual, confirm-gated, synchronous (one parse_structured call) like the hot
regen endpoint. Never automatic: tuning only runs because the user asked.
"""

import logging
import re
import uuid
from datetime import UTC, datetime

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.llm import LLMError, is_llm_configured, parse_structured
from app.core.config import get_settings
from app.core.errors import (
    LLMQueryGenerationError,
    NoJobSourcesConfiguredError,
    NoTunableSignalsError,
    ProfileNotFoundError,
)
from app.models import JobPosting, Match, Profile
from app.schemas.job_search import SearchQueriesResponse, StoredSearchQueries
from app.schemas.profile import StructuredProfile
from app.services import sources as sources_service
from app.services.matching import signal_skills
from app.services.query_builder import (
    PROMPT_VERSION,
    _GeneratedQueries,
    _options_block,
    _strip_undeclared_options,
    compute_queries_input_hash,
    parse_stored,
)

logger = logging.getLogger(__name__)

TUNE_TEMPERATURE = 0.2
_BUCKET_LABELS = {"positive": "clicked or saved", "negative": "dismissed", "weak": "never opened"}

_TUNE_SYSTEM = (
    "You tune a candidate's job-search query specs from observed engagement. "
    "For every source listed in the request, produce: title = an exact job-title "
    "phrase including seniority when known; skills_all = up to 3 short must-have "
    "stack keywords (single words or short tool names; omit or leave empty when no "
    "clear must-have core exists); skills = up to 3 short nice-to-have or adjacent "
    "skill keywords; exclude = up to 2 terms that would pull in wrong-level results "
    "(may be an empty list). Never include a location or salary in the spec fields - "
    "those travel as structured filters. Weight the evidence: terms under 'positive' "
    "(clicked or saved) belong in the specs; terms under 'weak' never got opened, so "
    "keep them only where the candidate context supports them; terms under "
    "'negative' (dismissed) must stop being attracted by the specs. Use only the "
    "provided candidate context and the aggregate counts; never invent skills. Fill "
    "the per-source options dict only with advanced filter keys the source declares "
    "(and only with the allowed values for select fields); omit options entirely "
    "rather than inventing keys."
)

# Dismissal outranks save/apply for bucketing — the later, stronger act.
_BUCKET_PREDICATES = {
    "positive": and_(
        or_(Match.clicked_apply_at.is_not(None), Match.saved_at.is_not(None)),
        Match.dismissed_at.is_(None),
    ),
    "negative": Match.dismissed_at.is_not(None),
    "weak": and_(
        Match.clicked_apply_at.is_(None),
        Match.saved_at.is_(None),
        Match.dismissed_at.is_(None),
    ),
}


async def aggregate_signal_buckets(
    session: AsyncSession, profile_id: uuid.UUID, skills: list[str]
) -> dict[str, dict[str, dict[str, int]]]:
    """Bucketed term counts — aggregates only, never raw posting text tails.

    Returns `{bucket: {"titles": {...}, "companies": {...}, "skills": {...}}}`
    with counts descending. Skill hits use the #37 word-boundary/regex rules
    (`\\m<term>\\M`, case-insensitive) so counts match the stored skill signal's
    semantics.
    """
    top_n = get_settings().tune_query_top_terms
    buckets: dict[str, dict[str, dict[str, int]]] = {}
    for bucket, predicate in _BUCKET_PREDICATES.items():
        sub = (
            select(
                func.lower(func.btrim(func.coalesce(JobPosting.title, ""))).label("title_key"),
                func.lower(func.btrim(func.coalesce(JobPosting.company, ""))).label("company_key"),
                func.concat(
                    func.coalesce(JobPosting.title, ""),
                    " ",
                    func.coalesce(JobPosting.description, ""),
                ).label("hay"),
            )
            .select_from(Match)
            .join(JobPosting, Match.job_posting_id == JobPosting.id)
            .where(Match.profile_id == profile_id, predicate)
            .subquery()
        )
        title_counts: dict[str, int] = {}
        company_counts: dict[str, int] = {}
        for key_column, target in (("title_key", title_counts), ("company_key", company_counts)):
            rows = (
                await session.execute(
                    select(sub.c[key_column], func.count())
                    .where(sub.c[key_column] != "")
                    .group_by(sub.c[key_column])
                    .order_by(func.count().desc(), sub.c[key_column])
                    .limit(top_n)
                )
            ).all()
            target.update({term: int(count) for term, count in rows})
        skill_counts: dict[str, int] = {}
        if skills:
            hit_sums = [
                func.sum(case((sub.c.hay.op("~*")(f"\\m{re.escape(skill)}\\M"), 1.0), else_=0.0))
                for skill in skills
            ]
            totals = (await session.execute(select(*hit_sums).select_from(sub))).one()
            skill_counts = {
                skill: int(total or 0)
                for skill, total in zip(skills, totals, strict=True)
                if int(total or 0) > 0
            }
        buckets[bucket] = {
            "titles": title_counts,
            "companies": company_counts,
            "skills": skill_counts,
        }
    return buckets


def _bucket_block(buckets: dict[str, dict[str, dict[str, int]]]) -> str:
    lines = ["Engagement signals (aggregate counts from your match list):"]
    for bucket in ("positive", "negative", "weak"):
        data = buckets[bucket]
        lines.append(f"{bucket} ({_BUCKET_LABELS[bucket]}):")
        for label, key in (
            ("titles", "titles"),
            ("companies", "companies"),
            ("skills", "skills"),
        ):
            counts = data[key]
            rendered = ", ".join(f"{term} ({count})" for term, count in counts.items())
            lines.append(f"- {label}: {rendered or 'none'}")
    return "\n".join(lines)


async def tune_for_profile(session: AsyncSession, profile_id: uuid.UUID) -> SearchQueriesResponse:
    """Rewrite the profile's stored query specs from engagement signals."""
    profile = await session.get(Profile, profile_id)
    if profile is None:
        raise ProfileNotFoundError()
    if not is_llm_configured():
        raise LLMQueryGenerationError("LLM provider is not configured")

    enabled = await sources_service.enabled_sources(session)
    if not enabled:
        raise NoJobSourcesConfiguredError()
    names = sorted(source.name for source in enabled)
    declaration_map = {source.name: source.filters() for source in enabled}

    structured = StructuredProfile.model_validate(profile.structured_profile)
    engaged = await session.scalar(
        select(func.count())
        .select_from(Match)
        .where(
            Match.profile_id == profile_id,
            or_(_BUCKET_PREDICATES["positive"], Match.dismissed_at.is_not(None)),
        )
    )
    if not engaged:
        raise NoTunableSignalsError()

    buckets = await aggregate_signal_buckets(session, profile_id, signal_skills(structured))

    stored = parse_stored(profile.search_queries)
    from app.services.embedding import profile_digest_parts

    digest = "\n".join(profile_digest_parts(structured))
    previous_block = ""
    if stored:
        previous_block = "\n\nThe currently stored query specs are:\n" + "\n".join(
            f"- {name}: {spec.model_dump_json()}" for name, spec in stored.queries.items()
        )
    prompt_parts = [f"Candidate context:\n{digest}"]
    if options_block := _options_block(declaration_map):
        prompt_parts.append(options_block)
    prompt_parts.append(_bucket_block(buckets))
    if previous_block:
        prompt_parts.append(previous_block.strip("\n"))
    prompt_parts.append(
        f"Sources needing a tuned query spec: {', '.join(names)}\n\nWrite the query spec JSON."
    )
    prompt = "\n\n".join(prompt_parts)

    try:
        result = await parse_structured(
            prompt,
            schema=_GeneratedQueries,
            system=_TUNE_SYSTEM,
            temperature=TUNE_TEMPERATURE,
        )
    except LLMError as exc:
        logger.warning("queries.tune failed profile_id=%s: %s (kept stored specs)", profile_id, exc)
        raise LLMQueryGenerationError(str(exc)) from exc

    missing = [name for name in names if name not in result.data.queries]
    if missing:
        raise LLMQueryGenerationError(f"query tuning missing sources: {', '.join(missing)}")

    tuned = StoredSearchQueries(
        queries=_strip_undeclared_options(
            {name: result.data.queries[name] for name in names}, declaration_map
        ),
        generated_at=datetime.now(UTC),
        generated_by=f"tuned:{get_settings().llm_model}",
        prompt_version=PROMPT_VERSION,
    )
    profile.search_queries = tuned.model_dump(mode="json")
    profile.queries_input_hash = compute_queries_input_hash(structured, names, declaration_map)
    await session.flush()

    logger.info(
        "queries.tuned profile_id=%s engaged=%s sources=%s prompt_tokens=%s completion_tokens=%s",
        profile_id,
        engaged,
        names,
        result.prompt_tokens,
        result.completion_tokens,
    )
    return SearchQueriesResponse(
        queries=tuned.queries,
        generated_at=tuned.generated_at,
        generated_by=tuned.generated_by,
    )
