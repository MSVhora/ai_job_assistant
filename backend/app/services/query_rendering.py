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
    title = spec.title if spec is not None else None
    return TermPlan(
        what_phrase=title,
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
    # string; spec.query only carries through when there is no title to
    # synthesize the keywords from.
    keywords = (
        base_query or _natural_keywords(spec, request) or (spec.query if spec is not None else None)
    )
    return TermPlan(
        keywords=keywords,
        location=request.location,
        date_posted=date_posted_bucket(request.max_days_old),
    )


def _format_amount(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return f"{value:f}".rstrip("0").rstrip(".")


def _natural_keywords(spec: SourceQuerySpec | None, request: JobSearchRequest) -> str | None:
    """LinkedIn AI-search natural-language keywords from a structured spec.

    Exclusions are dropped: the actor input has no exclusion field and
    LinkedIn's AI search has no exclusion filter (composition content is
    reworked in the LinkedIn-dialect issue, not here).
    """
    title = spec.title if spec is not None else None
    if not title:
        return None
    keywords = title
    skills = (spec.skills or []) if spec is not None else []
    if skills:
        keywords += f" with {' and '.join(skills)}"
    if request.salary_min is not None:
        currency = f" {request.salary_currency}" if request.salary_currency else ""
        keywords += f", offering{currency} {_format_amount(request.salary_min)} or more"
    return keywords


def _effective_query(spec: SourceQuerySpec | None, base_query: str | None) -> str:
    if spec is not None and spec.query:
        return spec.query
    return base_query or ""
