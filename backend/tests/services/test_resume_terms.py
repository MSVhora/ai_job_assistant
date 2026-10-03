import uuid

from app.schemas.resume_document import JDAnalysis
from app.services.resume_terms import (
    AllowedTerm,
    GapSource,
    allowed_terms,
    gaps_report,
    jd_skill_wordings,
    scan_skills,
)

JD = JDAnalysis(
    must_haves=["5 years of Kubernetes in production", "Snowflake"],
    nice_to_haves=["Kafka"],
    keywords=["Kubernetes", "Snowflake", "stakeholder management"],
)
HELM = "Deployed the services with Helm charts to our cluster"


def wordings(allowed: list[AllowedTerm]) -> list[str]:
    return [term.wording for term in allowed]


def test_a_jd_term_is_allowed_when_the_achievement_is_tagged_with_it() -> None:
    allowed, disallowed = allowed_terms(JD, ["kubernetes"], HELM)

    assert wordings(allowed) == ["Kubernetes"]
    assert "Snowflake" in disallowed


def test_a_jd_term_absent_from_skills_and_evidence_is_not_allowed() -> None:
    allowed, disallowed = allowed_terms(JD, ["Python"], "Wrote a docs generator")

    assert allowed == []
    assert {"Kubernetes", "Snowflake", "Kafka"} <= set(disallowed)


def test_synonyms_from_the_alias_table_are_respected() -> None:
    jd = JDAnalysis(keywords=["K8s"])

    allowed, _ = allowed_terms(jd, ["Kubernetes"], "")

    assert wordings(allowed) == ["K8s"]


def test_a_term_named_in_the_evidence_text_counts_even_without_a_tag() -> None:
    allowed, _ = allowed_terms(JD, [], "Moved the pipeline to Kafka consumers")

    assert wordings(allowed) == ["Kafka"]


def test_a_non_alias_phrase_is_allowed_only_when_the_evidence_contains_it() -> None:
    assert wordings(allowed_terms(JD, [], "Drove stakeholder management for launches")[0]) == [
        "stakeholder management"
    ]
    assert "stakeholder management" in allowed_terms(JD, [], "Wrote code")[1]


def test_no_jd_means_no_terms() -> None:
    assert allowed_terms(None, ["Python"], "x") == ([], [])


def test_scan_ignores_prose_and_finds_canonical_names() -> None:
    assert {key for _, key in scan_skills("the rest of the go-live on K8s and Rust")} == {
        "kubernetes",
        "rust",
    }


def test_jd_wordings_merge_keywords_and_skills_named_in_the_lists() -> None:
    assert set(jd_skill_wordings(JD)) == {
        "kubernetes",
        "snowflake",
        "stakeholder management",
        "kafka",
    }


def test_gaps_list_must_haves_without_evidence_with_the_nearest_match() -> None:
    achievement_id = uuid.uuid4()
    sources = [
        GapSource(achievement_id, "Kubernetes rollout", ("Kubernetes",), HELM),
        GapSource(uuid.uuid4(), "Docs", ("Python",), "Wrote docs"),
    ]
    jd = JDAnalysis(must_haves=["Kubernetes in production", "Snowflake warehouse tuning"])

    gaps = gaps_report(jd, sources)

    assert [g.requirement for g in gaps] == ["Snowflake warehouse tuning"]
    assert gaps[0].action == "add_note"
    assert gaps[0].nearest_achievement_id is None


def test_a_gap_points_at_the_nearest_evidence_when_words_overlap() -> None:
    achievement_id = uuid.uuid4()
    sources = [GapSource(achievement_id, "Warehouse load", ("SQL",), "Tuned the warehouse load")]
    jd = JDAnalysis(must_haves=["Snowflake warehouse tuning"])

    gaps = gaps_report(jd, sources)

    assert gaps[0].nearest_achievement_id == achievement_id
    assert gaps[0].nearest_evidence == "Warehouse load"


def test_no_jd_no_gaps() -> None:
    assert gaps_report(None, []) == []
