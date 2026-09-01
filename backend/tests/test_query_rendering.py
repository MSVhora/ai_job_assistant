from app.schemas.job_search import JobSearchRequest, SourceQuerySpec
from app.services.query_rendering import build_connector_query


def request(**overrides: object) -> JobSearchRequest:
    defaults: dict[str, object] = {"country": "in"}
    return JobSearchRequest(**{**defaults, **overrides})  # type: ignore[arg-type]


def test_spec_sets_structured_fields_for_adzuna() -> None:
    spec = SourceQuerySpec(
        title="Senior Android Engineer", skills=["Kotlin", "Java"], exclude=["intern"]
    )

    query = build_connector_query("adzuna", spec, None, request())

    assert query.title_phrase == "Senior Android Engineer"
    assert query.skills_any == ["Kotlin", "Java"]
    assert query.exclude_any == ["intern"]
    assert query.query == ""
    assert query.country == "in"


def test_spec_drops_exclude_for_sources_without_support() -> None:
    spec = SourceQuerySpec(title="Senior Android Engineer", skills=["Kotlin"], exclude=["intern"])

    query = build_connector_query("apify_linkedin", spec, None, request())

    assert query.title_phrase == "Senior Android Engineer"
    assert query.exclude_any == []


def test_no_spec_falls_back_to_base_query() -> None:
    query = build_connector_query("adzuna", None, "android developer", request())

    assert query.query == "android developer"
    assert query.title_phrase is None


def test_spec_query_overrides_base() -> None:
    spec = SourceQuerySpec(query="mobile engineer kotlin")

    query = build_connector_query("adzuna", spec, "android developer", request())

    assert query.query == "mobile engineer kotlin"


def test_shared_filters_pass_through() -> None:
    spec = SourceQuerySpec(title="Senior Android Engineer")

    query = build_connector_query(
        "adzuna",
        spec,
        None,
        request(location="Bangalore", salary_min=5000000, salary_currency="inr"),
    )

    assert query.location == "Bangalore"
    assert query.salary_min == 5000000
    assert query.salary_currency == "INR"


def test_spec_query_is_used_for_fallback_when_no_title() -> None:
    assert build_connector_query("adzuna", SourceQuerySpec(), "base", request()).query == "base"
