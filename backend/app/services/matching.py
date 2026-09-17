import logging
import re
import uuid
from datetime import UTC, datetime, timedelta

from pydantic import ValidationError
from sqlalchemy import (
    ColumnElement,
    Select,
    and_,
    bindparam,
    case,
    delete,
    exists,
    func,
    literal,
    or_,
    select,
    update,
)
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.llm import LLMError, parse_structured
from app.core.config import get_settings
from app.core.errors import ProfileNotEmbeddedError, ProfileNotFoundError
from app.models import JobPosting, JobSearch, Match, Profile, SearchPosting
from app.schemas.job_search import JobPostingSummary, MatchingOutcome
from app.schemas.matching import (
    MatchFilters,
    MatchQueryParams,
    MatchResponse,
    RerankItem,
    RerankResult,
)
from app.schemas.profile import StructuredProfile, parse_stored_preferences
from app.services.embedding import profile_digest_parts

logger = logging.getLogger(__name__)

_MAX_RATIONALE_CHARS = 600
_MAX_RERANK_DESCRIPTION_CHARS = 1500
_MAX_DIGEST_SUMMARY_CHARS = 400
_MAX_DIGEST_ROLES = 8
_FIT_SCALE = 10.0
_PRIORITY_EPSILON = 1e-9
_UNKNOWN_DATE_SCORE = 0.5
_NO_PREFERENCE_SCORE = 0.5

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


def freshness_condition() -> ColumnElement[bool]:
    """D4 read-side freshness: closed or expired postings never surface.

    A source-reported expiry is authoritative (the grace window does not
    apply); without one, a posting is stale once `posted_at` breaches the
    `STALE_POSTING_DAYS` window. Unknown dates keep the posting visible.
    """
    settings = get_settings()
    stale_cutoff = datetime.now(UTC) - timedelta(days=settings.stale_posting_days)
    not_stale = JobPosting.posted_at.is_(None) | (JobPosting.posted_at >= stale_cutoff)
    return and_(
        JobPosting.is_closed.is_(False),
        or_(JobPosting.expires_at >= func.now(), and_(JobPosting.expires_at.is_(None), not_stale)),
    )


def _apply_posting_filters[RowT](query: Select[RowT], filters: MatchFilters) -> Select[RowT]:
    query = query.where(freshness_condition())
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


def skill_hit_terms(title: str | None, description: str | None, skills: list[str]) -> list[str]:
    """Python twin of the SQL skill-hit pass (test-pinned in test_matching).

    The rerank prompt (Python) and the stored `skill_score` (SQL) describe the
    same overlap; this helper keeps their match rules in lockstep.
    """
    hay = f"{title or ''} {description or ''}"
    return [
        skill
        for skill in skills
        if skill and re.search(rf"\b{re.escape(skill)}\b", hay, re.IGNORECASE)
    ]


def _skill_score_expression(skills: list[str]) -> ColumnElement:
    """Top-skill word-boundary hit fraction over `title + description` (#37).

    Each top skill contributes one `CASE … ~ '\m<skill>\M'` (word-anchored,
    case-insensitive regex); the sum normalizes by the skill count. Word
    anchors mirror `\\b` in the Python twin (`\\m`/`\\M` in PG; terms ending
    in non-word chars fail identically on both sides). No pg_trgm — that
    extension is deferred to #38's dedupe.
    """
    if not skills:
        return literal(0.0)
    hay = func.concat(
        func.coalesce(JobPosting.title, ""), " ", func.coalesce(JobPosting.description, "")
    )
    hits = sum(
        case((hay.op("~*")(f"\\m{re.escape(skill)}\\M"), 1.0), else_=0.0) for skill in skills
    )
    return func.least(1.0, hits / float(len(skills)))


def _recency_expression() -> ColumnElement:
    """`exp(-days/<decay>)` on posted_at; unknown dates stay neutral (#37)."""
    days = func.greatest(0.0, func.extract("epoch", func.now() - JobPosting.posted_at) / 86400.0)
    decay = float(get_settings().match_recency_decay_days)
    return case(
        (JobPosting.posted_at.is_(None), _UNKNOWN_DATE_SCORE),
        else_=func.exp(-days / decay),
    )


def salary_fit_score(
    posting_min: float | None,
    posting_max: float | None,
    posting_currency: str | None,
    pref_min: float | None,
    pref_max: float | None,
    pref_currency: str | None,
) -> float:
    """Python twin of the SQL salary-fit CASE (test-pinned in test_matching).

    Unknown posting band, or a posting currency that can't be compared
    against the preference → 1.0; no preference band → 0.5; overlapping
    bands → 1.0, else a linear decay in multiples of the band width.
    """
    if pref_min is None and pref_max is None:
        return _NO_PREFERENCE_SCORE
    posting_cur = posting_currency.lower() if posting_currency is not None else None
    pref_cur = pref_currency.lower() if pref_currency is not None else ""
    if posting_cur is not None and posting_cur != pref_cur:
        return 1.0
    if posting_min is None and posting_max is None:
        return 1.0
    post_lo = float(posting_min) if posting_min is not None else float("-inf")
    post_hi = float(posting_max) if posting_max is not None else float("inf")
    lo = float(pref_min) if pref_min is not None else float("-inf")
    hi = float(pref_max) if pref_max is not None else float("inf")
    if max(post_lo, lo) <= min(post_hi, hi):
        return 1.0
    if post_hi < lo:
        gap = lo - post_hi
    else:
        gap = post_lo - hi
    if pref_min is not None and pref_max is not None:
        width = max(hi - lo, 1.0)
    elif pref_max is None:
        width = max(lo, 1.0)
    else:
        width = max(hi, 1.0)
    return max(0.0, 1.0 - gap / width)


def _salary_score_expression(
    pref_min: float | None, pref_max: float | None, pref_currency: str | None
) -> ColumnElement:
    """SQL mirror of `salary_fit_score` (above) — the same branches in CASE.

    The preference band is static per profile, so the preference side is
    resolved in Python and only the posting side stays in SQL.
    """
    if pref_min is None and pref_max is None:
        return literal(_NO_PREFERENCE_SCORE)
    posting_min, posting_max = JobPosting.salary_min, JobPosting.salary_max
    pref_cur = pref_currency.lower() if pref_currency is not None else ""
    mismatch = and_(
        JobPosting.currency.is_not(None),
        func.lower(JobPosting.currency) != pref_cur,
    )
    unknown_band = and_(posting_min.is_(None), posting_max.is_(None))
    if pref_min is None:
        overlap = or_(posting_min.is_(None), posting_min <= float(pref_max))
        gap = case(
            (posting_min.is_(None), 0.0),
            (posting_min <= float(pref_max), 0.0),
            else_=posting_min - float(pref_max),
        )
        width_col = func.greatest(float(pref_max), 1.0)
    elif pref_max is None:
        overlap = or_(posting_max.is_(None), posting_max >= float(pref_min))
        gap = case(
            (posting_max.is_(None), 0.0),
            (posting_max < float(pref_min), float(pref_min) - posting_max),
            else_=0.0,
        )
        width_col = func.greatest(float(pref_min), 1.0)
    else:
        overlap = or_(
            posting_min.is_(None),
            posting_max.is_(None),
            and_(posting_max >= float(pref_min), posting_min <= float(pref_max)),
        )
        gap = case(
            (posting_max < float(pref_min), float(pref_min) - posting_max),
            else_=posting_min - float(pref_max),
        )
        width_col = func.greatest(float(pref_max) - float(pref_min), 1.0)
    return case(
        (mismatch, 1.0),
        (unknown_band, 1.0),
        (overlap, 1.0),
        else_=func.greatest(0.0, 1.0 - gap / width_col),
    )


def priority_weights(priority: float) -> tuple[float, float]:
    """Split the judgment mass by the slider: (role_fit weight, company_fit).

    The judgment mass is the role+company Settings weights (default
    0.15 + 0.05 = 0.20 — one knob, "employer vs role", unchanged semantics);
    skill/recency/salary stay fixed from Settings.
    """
    settings = get_settings()
    mass = settings.match_weight_role_fit + settings.match_weight_company_fit
    clamped = max(0.0, min(1.0, priority))
    return mass * clamped, mass * (1.0 - clamped)


def default_priority() -> float:
    """Slider position equivalent to the Settings default weights."""
    settings = get_settings()
    total = settings.match_weight_role_fit + settings.match_weight_company_fit
    if total <= 0.0:
        return 0.5
    return settings.match_weight_role_fit / total


def _priority_sort_expression(priority: float) -> ColumnElement:
    """Read-time blend of stored sub-scores under a custom priority (#11, #37).

    Rows without re-rank verdicts keep their stored final_score (fallback
    renormalization included); skill/recency/salary stay at Settings values
    while only the judgment mass redistributes.
    """
    w_role, w_company = priority_weights(priority)
    settings = get_settings()
    blended = (
        settings.match_weight_vector * func.coalesce(Match.vector_score, 0.0)
        + settings.match_weight_skill * func.coalesce(Match.skill_score, 0.0)
        + settings.match_weight_recency * func.coalesce(Match.recency_score, 0.0)
        + settings.match_weight_salary * func.coalesce(Match.salary_score, 0.0)
        + w_role * func.coalesce(Match.role_fit, 0.0) / _FIT_SCALE
        + w_company * func.coalesce(Match.company_fit, 0.0) / _FIT_SCALE
    )
    return case((Match.role_fit.is_not(None), blended), else_=Match.final_score)


def _final_score(
    vector_score: float | None,
    skill_score: float,
    recency_score: float,
    salary_score: float,
    role_fit: float | None = None,
    company_fit: float | None = None,
) -> float:
    """Config-weighted final over the SQL signals + LLM verdicts (#37).

    Embedded rows sum the present weights (the v1 "two scales between
    re-ranked and un-ranked rows" caveat carries over). Un-embedded rows
    renormalize over their three available signals.
    """
    settings = get_settings()
    w_skill = settings.match_weight_skill
    w_recency = settings.match_weight_recency
    w_salary = settings.match_weight_salary
    if vector_score is None:
        denom = w_skill + w_recency + w_salary
        weighted = w_skill * skill_score + w_recency * recency_score + w_salary * salary_score
        total = 0.0 if denom <= 0.0 else weighted / denom
    else:
        total = (
            settings.match_weight_vector * vector_score
            + w_skill * skill_score
            + w_recency * recency_score
            + w_salary * salary_score
        )
    if role_fit is not None:
        total += settings.match_weight_role_fit * role_fit / _FIT_SCALE
    if company_fit is not None:
        total += settings.match_weight_company_fit * company_fit / _FIT_SCALE
    return max(0.0, min(1.0, total))


def _hybrid_blend_expression() -> ColumnElement:
    """Stored-columns hybrid, coalesced — rerank-pool ordering (#37).

    NULL sub-scores coalesce to 0 so legacy rows never crash the pool query;
    un-embedded postings rank on their SQL signals instead of being hidden.
    """
    settings = get_settings()
    return (
        settings.match_weight_vector * func.coalesce(Match.vector_score, 0.0)
        + settings.match_weight_skill * func.coalesce(Match.skill_score, 0.0)
        + settings.match_weight_recency * func.coalesce(Match.recency_score, 0.0)
        + settings.match_weight_salary * func.coalesce(Match.salary_score, 0.0)
    )


def scoped_corpus_exists(profile_id: uuid.UUID) -> ColumnElement[bool]:
    """Postings found by this profile's own searches (v3 §2 D1 corpus).

    EXISTS avoids DISTINCT over the append-only many-to-many: a posting
    re-found by several of the profile's searches is scored once.
    """
    return exists(
        select(SearchPosting.posting_id)
        .select_from(SearchPosting)
        .join(JobSearch, JobSearch.id == SearchPosting.search_id)
        .where(SearchPosting.posting_id == JobPosting.id, JobSearch.profile_id == profile_id)
    )


def _parse_profile(profile: Profile) -> StructuredProfile | None:
    try:
        return StructuredProfile.model_validate(profile.structured_profile)
    except ValidationError:
        logger.warning(
            "matching.rescore signal parsing skipped profile_id=%s (structured profile "
            "failed validation); scoring proceeds on recency/salary only",
            profile.id,
        )
        return None


def _signal_skills(structured: StructuredProfile | None) -> list[str]:
    if structured is None:
        return []
    ordered: dict[str, None] = {}
    for skill in structured.skills:
        trimmed = skill.strip()
        if trimmed:
            ordered.setdefault(trimmed, None)
    return list(ordered)[: get_settings().match_skill_signal_skills]


def _salary_preferences(
    structured: StructuredProfile | None,
) -> tuple[float | None, float | None, str | None]:
    preferences = structured.preferences if structured is not None else None
    if preferences is None:
        return None, None, None
    return preferences.salary_min, preferences.salary_max, preferences.currency


async def rescore_matches(
    session: AsyncSession, profile: Profile, *, invalidate_rationales: bool
) -> int:
    """Re-score the profile's scoped corpus against the profile (SQL only).

    The corpus is only the postings found by the profile's own searches
    (`search_posting → job_search.profile_id`) — never the global corpus —
    and since #37 it includes un-embedded postings (`vector_score` stays
    None; final_score renormalizes over skill + recency + salary). One bulk
    SQL pass computes all signals; one upsert writes `match`. Existing
    re-rank verdicts are blended into the fresh final_score unless
    `invalidate_rationales` clears them. Returns the number of scored
    postings; 0 when the profile has no embedding.
    """
    if profile.embedding is None:
        return 0
    settings = get_settings()
    structured = _parse_profile(profile)
    skills = _signal_skills(structured)
    pref_min, pref_max, pref_currency = _salary_preferences(structured)
    vector_value = case(
        (JobPosting.embedding.is_(None), None),
        else_=func.least(
            1.0, func.greatest(0.0, 1.0 - JobPosting.embedding.cosine_distance(profile.embedding))
        ),
    )
    result = await session.execute(
        select(
            JobPosting.id,
            vector_value.label("vector_score"),
            _skill_score_expression(skills).label("skill_score"),
            _recency_expression().label("recency_score"),
            _salary_score_expression(pref_min, pref_max, pref_currency).label("salary_score"),
        ).where(scoped_corpus_exists(profile.id))
    )
    rows = []
    fallback_count = 0
    for posting_id, vector_score, skill_score, recency_score, salary_score in result.all():
        vector = float(vector_score) if vector_score is not None else None
        skill = float(skill_score or 0.0)
        recency = float(recency_score or 0.0)
        salary = float(salary_score or 0.0)
        if vector is None:
            fallback_count += 1
        rows.append(
            {
                "profile_id": profile.id,
                "job_posting_id": posting_id,
                "vector_score": vector,
                "skill_score": skill,
                "recency_score": recency,
                "salary_score": salary,
                "final_score": _final_score(vector, skill, recency, salary),
            }
        )
    if not rows:
        return 0

    stmt = pg_insert(Match).values(rows)
    set_: dict[str, object] = {
        "vector_score": stmt.excluded.vector_score,
        "skill_score": stmt.excluded.skill_score,
        "recency_score": stmt.excluded.recency_score,
        "salary_score": stmt.excluded.salary_score,
        "updated_at": func.now(),
    }
    if invalidate_rationales:
        set_["final_score"] = stmt.excluded.final_score
        set_["role_fit"] = None
        set_["company_fit"] = None
        set_["rationale"] = None
    else:
        set_["final_score"] = case(
            (
                Match.role_fit.is_not(None),
                func.least(
                    1.0,
                    stmt.excluded.final_score
                    + settings.match_weight_role_fit
                    * func.coalesce(Match.role_fit, 0.0)
                    / _FIT_SCALE
                    + settings.match_weight_company_fit
                    * func.coalesce(Match.company_fit, 0.0)
                    / _FIT_SCALE,
                ),
            ),
            else_=stmt.excluded.final_score,
        )
    stmt = stmt.on_conflict_do_update(constraint="uq_match_profile_job_posting", set_=set_)
    await session.execute(stmt)
    logger.info(
        "matching.rescore profile_id=%s scored=%d fallback=%d",
        profile.id,
        len(rows),
        fallback_count,
    )
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
    return await rescore_and_rerank(session, profile)


async def rescore_and_rerank(session: AsyncSession, profile: Profile) -> MatchingOutcome:
    """Scoped rescore + re-rank of the rationale-less top N."""
    scored = await rescore_matches(session, profile, invalidate_rationales=False)
    return await _rerank_top_matches(session, profile, scored)


async def count_corpus_postings(session: AsyncSession, profile_id: uuid.UUID) -> int:
    """Size of the profile's scoped corpus: postings found by its own searches."""
    return int(
        (
            await session.execute(
                select(func.count()).select_from(JobPosting).where(scoped_corpus_exists(profile_id))
            )
        ).scalar_one()
    )


def _corpus_ids_subquery(profile_id: uuid.UUID) -> Select[tuple[uuid.UUID]]:
    return (
        select(JobPosting.id)
        .join(SearchPosting, SearchPosting.posting_id == JobPosting.id)
        .join(JobSearch, JobSearch.id == SearchPosting.search_id)
        .where(JobSearch.profile_id == profile_id)
    )


async def count_out_of_corpus_matches(session: AsyncSession, profile_id: uuid.UUID) -> int:
    """Stored matches for this profile whose posting is outside its scoped corpus."""
    return int(
        (
            await session.execute(
                select(func.count())
                .select_from(Match)
                .where(
                    Match.profile_id == profile_id,
                    Match.job_posting_id.not_in(_corpus_ids_subquery(profile_id)),
                )
            )
        ).scalar_one()
    )


async def delete_out_of_corpus_matches(session: AsyncSession, profile_id: uuid.UUID) -> int:
    """Drop matches whose posting is no longer in the profile's scoped corpus.

    Only called on an explicit rebuild (D7): stale rows from the pre-#25
    global corpus are removed the moment the user opts back in per profile.
    """
    result = await session.execute(
        delete(Match).where(
            Match.profile_id == profile_id,
            Match.job_posting_id.not_in(_corpus_ids_subquery(profile_id)),
        )
    )
    return int(result.rowcount or 0)


async def _rerank_top_matches(
    session: AsyncSession, profile: Profile, scored_count: int
) -> MatchingOutcome:
    settings = get_settings()
    query = select(Match, JobPosting).join(JobPosting, Match.job_posting_id == JobPosting.id)
    candidates = (
        await session.execute(
            query.where(Match.profile_id == profile.id, Match.rationale.is_(None))
            .order_by(_hybrid_blend_expression().desc(), JobPosting.posted_at.desc().nulls_last())
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
    signal_skills = _signal_skills(structured)

    prompt = _rerank_prompt(structured, [posting for _, posting in candidates], signal_skills)
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
                "final_score": _final_score(
                    match.vector_score,
                    match.skill_score or 0.0,
                    match.recency_score or 0.0,
                    match.salary_score or 0.0,
                    role_fit,
                    company_fit,
                ),
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


def _profile_digest(structured: StructuredProfile) -> str:
    """Shared digest + rerank-only preference lines (#37).

    The shared parts come from `embedding.profile_digest_parts` (its
    byte-stability note forbids display-only edits there): appending the
    salary band and remote preference here makes the rerank see the
    profile's projector preferences without touching embedding inputs.
    """
    parts = profile_digest_parts(structured)
    preferences = structured.preferences
    if preferences and (preferences.salary_min is not None or preferences.salary_max is not None):
        lo = preferences.salary_min
        hi = preferences.salary_max
        band = (str(lo) if lo is not None else "any") + "–" + (str(hi) if hi is not None else "any")
        if preferences.currency:
            band = f"{band} {preferences.currency}"
        parts.append(f"Salary preference: {band}")
    if preferences and preferences.remote_preference:
        parts.append(f"Remote preference: {preferences.remote_preference}")
    return "\n".join(parts)


def _rerank_prompt(
    profile: StructuredProfile, postings: list[JobPosting], signal_skills: list[str]
) -> str:
    blocks = [_profile_digest(profile)]
    for posting in postings:
        description = (posting.description or "").strip()[:_MAX_RERANK_DESCRIPTION_CHARS]
        company = posting.company or "unknown company"
        location = posting.location or "unknown location"
        overlap = skill_hit_terms(posting.title, posting.description, signal_skills)
        overlap_text = ", ".join(overlap) if overlap else "none"
        blocks.append(
            f"### Posting\nid: {posting.id}\ntitle: {posting.title}\ncompany: {company}\n"
            f"location: {location}\nskills overlap: {overlap_text}\ndescription: {description}"
        )
    return "\n\n".join(blocks)


_SORT_ORDERS = {
    "final_score": (Match.final_score.desc(), JobPosting.posted_at.desc().nulls_last()),
    "vector_score": (
        Match.vector_score.desc().nulls_last(),
        JobPosting.posted_at.desc().nulls_last(),
    ),
    "posted_at": (JobPosting.posted_at.desc().nulls_last(), Match.final_score.desc()),
}


async def count_matches(session: AsyncSession, params: MatchQueryParams) -> int:
    profile = await session.get(Profile, params.profile_id)
    if profile is None:
        raise ProfileNotFoundError()
    if profile.embedding is None:
        raise ProfileNotEmbeddedError()
    query: Select[tuple[int]] = (
        select(func.count())
        .select_from(Match)
        .join(JobPosting, Match.job_posting_id == JobPosting.id)
        .where(Match.profile_id == params.profile_id)
    )
    query = _apply_posting_filters(query, params)
    return int((await session.execute(query)).scalar_one())


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
            skill_score=match.skill_score,
            recency_score=match.recency_score,
            salary_score=match.salary_score,
            role_fit=match.role_fit,
            company_fit=match.company_fit,
            final_score=effective_score,
            rationale=match.rationale,
            created_at=match.created_at,
            updated_at=match.updated_at,
        )
        for match, posting, effective_score in rows
    ]
