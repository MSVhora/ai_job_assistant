import logging
import uuid
from datetime import UTC, datetime, timedelta

from pydantic import ValidationError
from sqlalchemy import ColumnElement, Select, bindparam, case, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.llm import LLMError, parse_structured
from app.core.config import get_settings
from app.core.errors import ProfileNotEmbeddedError, ProfileNotFoundError
from app.models import JobPosting, Match, Profile
from app.schemas.job_search import JobPostingSummary, JobSearchRequest, MatchingOutcome
from app.schemas.matching import (
    MatchFilters,
    MatchQueryParams,
    MatchResponse,
    RerankItem,
    RerankResult,
)
from app.schemas.profile import StructuredProfile, parse_stored_preferences

logger = logging.getLogger(__name__)

_MAX_RATIONALE_CHARS = 600
_MAX_RERANK_DESCRIPTION_CHARS = 1500
_MAX_DIGEST_SUMMARY_CHARS = 400
_MAX_DIGEST_ROLES = 8
_FIT_SCALE = 10.0
_PRIORITY_EPSILON = 1e-9

_RERANK_SYSTEM = (
    "You score job postings against a candidate profile. "
    "role_fit: how well the role itself matches the candidate's target role, skills, "
    "and seniority (0-10). "
    "company_fit: how well the employer fits the candidate's trajectory, judging the "
    "signals about the employer inside the description (0-10). "
    "rationale: at most 60 words, concrete, stating why the posting matches and what "
    "it is missing. "
    "Respond with a single JSON object conforming to the provided schema and include "
    "every posting id given."
)


def ranked_postings_query(
    profile_embedding: list[float], filters: MatchFilters
) -> Select[tuple[JobPosting, float]]:
    """Hard-filtered, cosine-ranked posting query (#9 building block).

    Postings without an embedding are excluded from vector ranking; the match
    pipeline (#10) consumes the returned select unchanged.
    """
    distance = JobPosting.embedding.cosine_distance(profile_embedding)
    query: Select[tuple[JobPosting, float]] = (
        select(JobPosting, distance.label("vector_distance"))
        .where(JobPosting.embedding.is_not(None))
        .order_by(distance.asc())
    )
    return _apply_posting_filters(query, filters)


def _apply_posting_filters[RowT](query: Select[RowT], filters: MatchFilters) -> Select[RowT]:
    if filters.location is not None:
        escaped = filters.location.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        query = query.where(JobPosting.location.ilike(f"%{escaped}%", escape="\\"))
    if filters.remote_type is not None:
        query = query.where(JobPosting.remote_type == filters.remote_type)
    if filters.job_type is not None:
        query = query.where(JobPosting.job_type == filters.job_type)
    if filters.posted_within_days is not None:
        cutoff = datetime.now(UTC) - timedelta(days=filters.posted_within_days)
        query = query.where(JobPosting.posted_at >= cutoff)
    return query


def vector_score_expression(profile_embedding: list[float]) -> ColumnElement[float]:
    distance = JobPosting.embedding.cosine_distance(profile_embedding)
    return func.least(1.0, func.greatest(1.0 - distance, 0.0))


def priority_weights(priority: float) -> tuple[float, float]:
    """Split the non-vector weight mass: (role_fit weight, company_fit weight).

    The vector weight stays at its Settings value; the remainder splits by the
    slider position, so `priority_weights(default_priority())` reproduces the
    Settings defaults exactly.
    """
    settings = get_settings()
    remaining = 1.0 - settings.match_weight_vector
    clamped = max(0.0, min(1.0, priority))
    return remaining * clamped, remaining * (1.0 - clamped)


def default_priority() -> float:
    """Slider position equivalent to the Settings default weights."""
    settings = get_settings()
    total = settings.match_weight_role_fit + settings.match_weight_company_fit
    if total <= 0.0:
        return 0.5
    return settings.match_weight_role_fit / total


def _priority_sort_expression(priority: float) -> ColumnElement[float]:
    """Read-time blend of stored sub-scores under a custom priority (#11).

    Rows without sub-scores keep their plain vector_score — the slider only
    reorders the re-ranked top N relative to each other and to unranked rows'
    fixed vector scores.
    """
    w_role, w_company = priority_weights(priority)
    settings = get_settings()
    blended = (
        settings.match_weight_vector * Match.vector_score
        + w_role * Match.role_fit / _FIT_SCALE
        + w_company * Match.company_fit / _FIT_SCALE
    )
    return case((Match.role_fit.is_not(None), blended), else_=Match.vector_score)


async def rescore_matches(
    session: AsyncSession, profile: Profile, *, invalidate_rationales: bool
) -> int:
    """Bulk re-score every embeddable posting against the profile (SQL only).

    Writes one `match` row per posting (upsert). Existing re-rank sub-scores are
    blended into the new final_score unless `invalidate_rationales` clears them.
    Returns the number of scored postings; 0 when the profile has no embedding.
    """
    if profile.embedding is None:
        return 0
    score = vector_score_expression(profile.embedding)
    result = await session.execute(
        select(JobPosting.id, score.label("vector_score")).where(JobPosting.embedding.is_not(None))
    )
    rows = [
        {
            "profile_id": profile.id,
            "job_posting_id": posting_id,
            "vector_score": float(vector_score),
            "final_score": float(vector_score),
        }
        for posting_id, vector_score in result.all()
    ]
    if not rows:
        return 0

    settings = get_settings()
    stmt = pg_insert(Match).values(rows)
    set_: dict[str, object] = {
        "vector_score": stmt.excluded.vector_score,
        "updated_at": func.now(),
    }
    if invalidate_rationales:
        set_["final_score"] = stmt.excluded.vector_score
        set_["role_fit"] = None
        set_["company_fit"] = None
        set_["rationale"] = None
    else:
        blended = (
            settings.match_weight_vector * stmt.excluded.vector_score
            + settings.match_weight_role_fit * func.coalesce(Match.role_fit, 0.0) / _FIT_SCALE
            + settings.match_weight_company_fit * func.coalesce(Match.company_fit, 0.0) / _FIT_SCALE
        )
        set_["final_score"] = case(
            (Match.role_fit.is_not(None), blended), else_=stmt.excluded.vector_score
        )
    stmt = stmt.on_conflict_do_update(constraint="uq_match_profile_job_posting", set_=set_)
    await session.execute(stmt)
    return len(rows)


async def refresh_matches_for_profile(
    session: AsyncSession, profile_id: uuid.UUID
) -> MatchingOutcome:
    """Re-score, then re-rank the rationale-less top N (one batched LLM call)."""
    profile = await session.get(Profile, profile_id)
    if profile is None:
        return MatchingOutcome(status="skipped", warning="profile not found")
    if profile.embedding is None:
        return MatchingOutcome(
            status="skipped",
            warning="profile has no embedding; save the profile once the embedding provider works",
        )
    scored = await rescore_matches(session, profile, invalidate_rationales=False)
    return await _rerank_top_matches(session, profile, scored)


async def refresh_matches_for_search(
    session: AsyncSession, payload: JobSearchRequest
) -> MatchingOutcome:
    profile_id = payload.profile_id or await latest_profile_id(session)
    if profile_id is None:
        return MatchingOutcome(status="skipped", warning="no profile available to match against")
    return await refresh_matches_for_profile(session, profile_id)


async def _rerank_top_matches(
    session: AsyncSession, profile: Profile, scored_count: int
) -> MatchingOutcome:
    settings = get_settings()
    query = select(Match, JobPosting).join(JobPosting, Match.job_posting_id == JobPosting.id)
    candidates = (
        await session.execute(
            query.where(Match.profile_id == profile.id, Match.rationale.is_(None))
            .order_by(Match.vector_score.desc())
            .limit(settings.rerank_top_n)
        )
    ).all()
    if not candidates:
        return MatchingOutcome(status="ok", scored_count=scored_count)

    try:
        structured = StructuredProfile.model_validate(profile.structured_profile)
    except ValidationError:
        logger.warning(
            "matching.rerank skipped profile_id=%s (structured profile failed validation)",
            profile.id,
        )
        return MatchingOutcome(
            status="failed",
            scored_count=scored_count,
            warning="structured profile failed validation; re-rank skipped",
        )

    prompt = _rerank_prompt(structured, [posting for _, posting in candidates])
    try:
        result = await parse_structured(prompt, schema=RerankResult, system=_RERANK_SYSTEM)
    except LLMError as exc:
        logger.warning("matching.rerank failed profile_id=%s: %s", profile.id, exc)
        return MatchingOutcome(
            status="failed",
            scored_count=scored_count,
            warning=f"re-rank unavailable: {exc}",
        )

    by_id: dict[uuid.UUID, RerankItem] = {item.posting_id: item for item in result.data.items}
    rows = []
    for match, posting in candidates:
        item = by_id.get(posting.id)
        if item is None:
            continue
        role_fit = _clamp_score(item.role_fit)
        company_fit = _clamp_score(item.company_fit)
        rows.append(
            {
                "id": match.id,
                "role_fit": role_fit,
                "company_fit": company_fit,
                "rationale": item.rationale.strip()[:_MAX_RATIONALE_CHARS] or None,
                "final_score": _final_score(match.vector_score, role_fit, company_fit),
            }
        )
    if rows:
        stmt = update(Match).values(
            role_fit=bindparam("role_fit"),
            company_fit=bindparam("company_fit"),
            rationale=bindparam("rationale"),
            final_score=bindparam("final_score"),
            updated_at=func.now(),
        )
        await session.execute(stmt, rows)

    logger.info(
        "matching.rerank profile_id=%s candidates=%d rationale=%d prompt_tokens=%d "
        "completion_tokens=%d",
        profile.id,
        len(candidates),
        len(rows),
        result.prompt_tokens,
        result.completion_tokens,
    )
    return MatchingOutcome(
        status="ok",
        scored_count=scored_count,
        rationale_count=len(rows),
        rerank_prompt_tokens=result.prompt_tokens,
        rerank_completion_tokens=result.completion_tokens,
    )


def _clamp_score(value: float) -> float:
    return max(0.0, min(_FIT_SCALE, value))


def _final_score(vector_score: float, role_fit: float, company_fit: float) -> float:
    settings = get_settings()
    return (
        settings.match_weight_vector * vector_score
        + settings.match_weight_role_fit * role_fit / _FIT_SCALE
        + settings.match_weight_company_fit * company_fit / _FIT_SCALE
    )


def _profile_digest(profile: StructuredProfile) -> str:
    preferences = profile.preferences
    parts: list[str] = []
    title = (preferences.target_title if preferences else None) or profile.headline
    if title:
        parts.append(f"Target role: {title}")
    if profile.skills:
        parts.append(f"Skills: {', '.join(profile.skills)}")
    if preferences and preferences.seniority:
        parts.append(f"Seniority: {preferences.seniority}")
    if preferences and preferences.target_location:
        parts.append(f"Preferred location: {preferences.target_location}")
    if profile.summary:
        parts.append(f"Summary: {profile.summary[:_MAX_DIGEST_SUMMARY_CHARS]}")
    roles = [
        f"{item.title} at {item.company}" if item.company else item.title
        for item in profile.experience
        if item.title
    ][:_MAX_DIGEST_ROLES]
    if roles:
        parts.append(f"Experience: {'; '.join(roles)}")
    return "\n".join(parts)


def _rerank_prompt(profile: StructuredProfile, postings: list[JobPosting]) -> str:
    blocks = [_profile_digest(profile)]
    for posting in postings:
        description = (posting.description or "").strip()[:_MAX_RERANK_DESCRIPTION_CHARS]
        company = posting.company or "unknown company"
        location = posting.location or "unknown location"
        blocks.append(
            f"### Posting\nid: {posting.id}\ntitle: {posting.title}\ncompany: {company}\n"
            f"location: {location}\ndescription: {description}"
        )
    return "\n\n".join(blocks)


async def latest_profile_id(session: AsyncSession) -> uuid.UUID | None:
    result = await session.execute(select(Profile.id).order_by(Profile.updated_at.desc()).limit(1))
    return result.scalars().first()


_SORT_ORDERS = {
    "final_score": (Match.final_score.desc(), JobPosting.posted_at.desc().nulls_last()),
    "vector_score": (Match.vector_score.desc(), JobPosting.posted_at.desc().nulls_last()),
    "posted_at": (JobPosting.posted_at.desc().nulls_last(), Match.final_score.desc()),
}


async def list_matches(session: AsyncSession, params: MatchQueryParams) -> list[MatchResponse]:
    profile = await session.get(Profile, params.profile_id)
    if profile is None:
        raise ProfileNotFoundError()
    if profile.embedding is None:
        raise ProfileNotEmbeddedError()

    stored = parse_stored_preferences(profile.preferences)
    priority = (
        params.priority if params.priority is not None else (stored.priority if stored else None)
    )
    custom = (
        params.sort == "final_score"
        and priority is not None
        and abs(priority - default_priority()) > _PRIORITY_EPSILON
    )
    effective = _priority_sort_expression(priority) if custom else Match.final_score

    query: Select[tuple[Match, JobPosting, float]] = (
        select(Match, JobPosting, effective.label("effective_score"))
        .join(JobPosting, Match.job_posting_id == JobPosting.id)
        .where(Match.profile_id == params.profile_id)
    )
    query = _apply_posting_filters(query, params)
    if custom:
        query = query.order_by(effective.desc(), JobPosting.posted_at.desc().nulls_last())
    else:
        query = query.order_by(*_SORT_ORDERS[params.sort])
    query = query.limit(params.limit).offset(params.offset)
    rows = (await session.execute(query)).all()
    return [
        MatchResponse(
            id=match.id,
            job_posting=JobPostingSummary.from_posting(posting),
            vector_score=match.vector_score,
            role_fit=match.role_fit,
            company_fit=match.company_fit,
            final_score=effective_score,
            rationale=match.rationale,
            created_at=match.created_at,
            updated_at=match.updated_at,
        )
        for match, posting, effective_score in rows
    ]
