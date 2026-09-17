from app.adapters.job_sources.base import JobSearchQuery, TermPlan, date_posted_bucket
from app.schemas.job_search import JobSearchRequest, SourceQuerySpec


def build_connector_query(
    source_name: str,
    spec: SourceQuerySpec | None,
    base_query: str | None,
    request: JobSearchRequest,
) -> JobSearchQuery:
    """Map a per-source spec + shared filters into the connector's query object.

    Sources with a dialect get a per-source ``TermPlan``; the precedence rules
    live here (see the connector docstrings for the tables). Sources without
    a dialect keep the generic free-text pass-through.
    """
    effective_query = _effective_query(spec, base_query)
    kwargs: dict[str, object] = {
        "location": request.location,
        "country": request.country,
        "results_wanted": request.results_wanted,
        "max_days_old": request.max_days_old,
        "salary_min": request.salary_min,
        "salary_max": request.salary_max,
        "salary_currency": request.salary_currency,
    }
    plan = _render_term_plan(source_name, spec, base_query, effective_query, request)
    if plan is not None:
        kwargs["term_plan"] = plan
    else:
        kwargs["query"] = effective_query
    return JobSearchQuery(**kwargs)  # type: ignore[arg-type]


def _render_term_plan(
    source_name: str,
    spec: SourceQuerySpec | None,
    base_query: str | None,
    effective_query: str,
    request: JobSearchRequest,
) -> TermPlan | None:
    if source_name == "adzuna":
        return _render_adzuna_plan(spec, base_query, effective_query)
    if source_name.startswith("apify_"):
        return _render_linkedin_plan(spec, base_query, request)
    return None


def _render_adzuna_plan(
    spec: SourceQuerySpec | None,
    base_query: str | None,
    effective_query: str,
) -> TermPlan:
    # Precedence: what_phrase + what_and/what_or combined; what only when no
    # phrase. A spec under a title never carries its query to the API.
    # skills_all (must-have stack) -> what_and; skills (nice-to-haves) ->
    # what_or; legacy specs without skills_all render what_and=[].
    title = spec.title if spec is not None else None
    return TermPlan(
        what_phrase=title,
        what_and=(spec.skills_all or []) if spec is not None else [],
        what_or=(spec.skills or []) if spec is not None else [],
        what_exclude=(spec.exclude or []) if spec is not None else [],
        what=effective_query if not title else None,
    )


def _render_linkedin_plan(
    spec: SourceQuerySpec | None,
    base_query: str | None,
    request: JobSearchRequest,
) -> TermPlan:
    # Precedence: a user-typed request query overrides the synthesized NL
    # brief; spec.query only carries through when there is no title to
    # synthesize from. NL exclusions ("not …") are the post-Aug-2026 LinkedIn
    # exclusion channel and are appended to whichever keywords won; there is
    # no salary text in keywords (issue #35).
    keywords = (
        base_query or _natural_keywords(spec, request) or (spec.query if spec is not None else None)
    )
    if keywords is not None:
        keywords = _with_exclusion_note(keywords, spec)
    return TermPlan(
        keywords=keywords,
        location=request.location,
        date_posted=date_posted_bucket(request.max_days_old),
    )


def _with_exclusion_note(keywords: str, spec: SourceQuerySpec | None) -> str:
    exclude = (spec.exclude or []) if spec is not None else []
    if not exclude:
        return keywords
    return f"{keywords} not {' and '.join(exclude)}"


def _natural_keywords(spec: SourceQuerySpec | None, request: JobSearchRequest) -> str | None:
    """LinkedIn AI-search semantic brief from a structured spec (issue #35).

    Grammar: ``"{title} with {skills}, {seniority} level"`` — skills from the
    spec (up to 3 validated terms), seniority from the profile via the
    request. The level phrase is omitted when no seniority is available.
    """
    title = spec.title if spec is not None else None
    if not title:
        return None
    keywords = title
    skills = (spec.skills or []) if spec is not None else []
    if skills:
        keywords += f" with {' and '.join(skills)}"
    if request.seniority:
        keywords += f", {request.seniority} level"
    return keywords


def _effective_query(spec: SourceQuerySpec | None, base_query: str | None) -> str:
    if spec is not None and spec.query:
        return spec.query
    return base_query or ""
