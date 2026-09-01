from app.adapters.job_sources.base import JobSearchQuery
from app.schemas.job_search import JobSearchRequest, SourceQuerySpec


def build_connector_query(
    source_name: str,
    spec: SourceQuerySpec | None,
    base_query: str | None,
    request: JobSearchRequest,
) -> JobSearchQuery:
    """Map a per-source spec + shared filters into the connector's query object.

    Spec fields are set for every source; each connector consumes only what it
    supports (capability table in docs/plans/v1-llm-source-queries.md).
    """
    effective_query = _effective_query(spec, base_query)
    kwargs: dict[str, object] = {
        "query": effective_query,
        "location": request.location,
        "country": request.country,
        "results_wanted": request.results_wanted,
        "salary_min": request.salary_min,
        "salary_max": request.salary_max,
        "salary_currency": request.salary_currency,
    }
    if spec is not None:
        if spec.title:
            kwargs["title_phrase"] = spec.title
        if spec.skills:
            kwargs["skills_any"] = spec.skills
        if spec.exclude and source_name == "adzuna":
            kwargs["exclude_any"] = spec.exclude
    return JobSearchQuery(**kwargs)  # type: ignore[arg-type]


def _effective_query(spec: SourceQuerySpec | None, base_query: str | None) -> str:
    if spec is not None and spec.query:
        return spec.query
    return base_query or ""
