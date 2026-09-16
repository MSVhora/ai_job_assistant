from app.schemas.job_search import JobSearchRequest, SourceQuerySpec
from app.services.query_rendering import build_connector_query


def request(**overrides: object) -> JobSearchRequest:
    defaults: dict[str, object] = {"country": "in", "source": "adzuna"}
    return JobSearchRequest(**{**defaults, **overrides})  # type: ignore[arg-type]


def test_adzuna_title_with_query_combines_terms_but_drops_what() -> None:
    spec = SourceQuerySpec(
        title="Senior Android Engineer", skills=["Kotlin", "Java"], exclude=["intern"]
    )

    query = build_connector_query("adzuna", spec, "mobile kotlin", request())

    plan = query.term_plan
    assert plan is not None
    assert plan.what_phrase == "Senior Android Engineer"
    assert plan.what_or == ["Kotlin", "Java"]
    assert plan.what_exclude == ["intern"]
    assert plan.what is None
    assert plan.what_and == []


def test_adzuna_title_only_keeps_terms_without_what() -> None:
    query = build_connector_query(
        "adzuna", SourceQuerySpec(title="Senior Android Engineer"), None, request()
    )

    plan = query.term_plan
    assert plan is not None
    assert plan.what_phrase == "Senior Android Engineer"
    assert plan.what_or == []
    assert plan.what is None


def test_adzuna_query_only_uses_what() -> None:
    spec = SourceQuerySpec(query="mobile engineer kotlin")

    query = build_connector_query("adzuna", spec, "android developer", request())

    plan = query.term_plan
    assert plan is not None
    assert plan.what == "mobile engineer kotlin"
    assert plan.what_phrase is None


def test_adzuna_query_only_falls_back_to_base_query() -> None:
    query = build_connector_query("adzuna", SourceQuerySpec(), "base", request())

    plan = query.term_plan
    assert plan is not None
    assert plan.what == "base"


def test_adzuna_no_terms_renders_empty_plan() -> None:
    query = build_connector_query("adzuna", SourceQuerySpec(), None, request())

    assert query.term_plan is not None
    assert query.query == ""


def test_linkedin_user_query_overrides_synthesized_keywords() -> None:
    spec = SourceQuerySpec(title="Senior Android Engineer", skills=["Kotlin", "Java"])

    query = build_connector_query("apify_linkedin", spec, "mobile kotlin", request())

    plan = query.term_plan
    assert plan is not None
    assert plan.keywords == "mobile kotlin"


def test_linkedin_title_only_composes_nl_keywords() -> None:
    query = build_connector_query(
        "apify_linkedin",
        SourceQuerySpec(title="Senior Android Engineer", skills=["Kotlin", "Java"]),
        None,
        request(),
    )

    plan = query.term_plan
    assert plan is not None
    assert plan.keywords == "Senior Android Engineer with Kotlin and Java"


def test_linkedin_nl_keywords_appends_salary() -> None:
    query = build_connector_query(
        "apify_linkedin",
        SourceQuerySpec(title="Senior Android Engineer"),
        None,
        request(salary_min=5000000, salary_currency="inr"),
    )

    plan = query.term_plan
    assert plan is not None
    assert plan.keywords == "Senior Android Engineer, offering INR 5000000 or more"


def test_linkedin_query_only_passes_user_query_through() -> None:
    query = build_connector_query("apify_linkedin", None, "mobile kotlin", request())

    plan = query.term_plan
    assert plan is not None
    assert plan.keywords == "mobile kotlin"


def test_linkedin_spec_query_only_carries_through_without_title() -> None:
    spec = SourceQuerySpec(query="mobile engineer kotlin")

    query = build_connector_query("apify_linkedin", spec, None, request())

    plan = query.term_plan
    assert plan is not None
    assert plan.keywords == "mobile engineer kotlin"


def test_linkedin_date_posted_bucket_rendered() -> None:
    spec = SourceQuerySpec(title="Senior Android Engineer")

    query = build_connector_query(
        "apify_linkedin", spec, None, request(max_days_old=7, location="Bangalore")
    )

    plan = query.term_plan
    assert plan is not None
    assert plan.date_posted == "pastWeek"
    assert plan.location == "Bangalore"


def test_linkedin_no_terms_leaves_keywords_none() -> None:
    query = build_connector_query("apify_linkedin", SourceQuerySpec(), None, request())

    plan = query.term_plan
    assert plan is not None
    assert plan.keywords is None


def test_unknown_source_keeps_free_text_pass_through() -> None:
    query = build_connector_query("mystery", None, "android developer", request())

    assert query.term_plan is None
    assert query.query == "android developer"
