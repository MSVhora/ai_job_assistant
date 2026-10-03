from decimal import Decimal

import pytest

from app.services.resume_verify import (
    build_source,
    check_claims,
    lint_bullet,
    metric_ids_used,
    numbers_in,
    unconfirmed_figures,
)

EVIDENCE = (
    "Cut the nightly import from 42 minutes to 9 minutes by batching writes in Python "
    "against PostgreSQL. Served 10,000 users on v2.1 in 2021."
)
SOURCE = build_source([EVIDENCE], ["Python"], [2021])


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Cut latency by 40%", {Decimal(40)}),
        ("Cut latency by 40 percent", {Decimal(40)}),
        ("Handled 10k requests", {Decimal(10000)}),
        ("Handled 10,000 requests", {Decimal(10000)}),
        ("Grew revenue 3x", {Decimal(3)}),
        ("Saved 1.5 million dollars", {Decimal(1500000)}),
        ("Used S3 and the 3rd runner", set()),
        ("Upgraded to v2.1.4", set()),
    ],
)
def test_numbers_normalise_formatting_variants(text: str, expected: set[Decimal]) -> None:
    assert numbers_in(text) == expected


def test_a_bullet_that_stays_inside_the_evidence_passes() -> None:
    text = "Cut the nightly import from 42 minutes to 9 minutes by batching Python writes"

    assert check_claims(text, SOURCE) == []


def test_an_invented_number_is_caught() -> None:
    violations = check_claims("Cut the nightly import by 78%", SOURCE)

    assert violations == ["the figure 78 does not appear in the evidence"]


def test_a_computed_total_is_caught_even_when_the_inputs_are_in_the_evidence() -> None:
    assert check_claims("Reduced import time by 33 minutes", SOURCE)


def test_formatting_variants_of_evidence_numbers_pass() -> None:
    assert check_claims("Served 10k users", SOURCE) == []


def test_an_added_tool_is_caught_and_a_listed_one_passes() -> None:
    assert check_claims("Batched writes in Python", SOURCE) == []
    assert check_claims("Batched writes with Kafka and Python", SOURCE) == [
        "the tool Kafka does not appear in the evidence"
    ]


def test_ordinary_words_that_are_also_tool_aliases_are_not_tools() -> None:
    text = "Moved the rest of the team to the next release and go-to-market work"

    assert check_claims(text, SOURCE) == []


def test_a_synonym_of_an_evidenced_tool_passes() -> None:
    source = build_source(["Deployed with k8s manifests"], [], [])

    assert check_claims("Deployed services on Kubernetes", source) == []


def test_a_year_outside_the_evidence_dates_is_caught() -> None:
    assert check_claims("Shipped the import in 2021", SOURCE) == []
    assert check_claims("Shipped the import in 2019", SOURCE) == [
        "the figure 2019 does not appear in the evidence"
    ]


def test_a_version_must_appear_verbatim() -> None:
    assert check_claims("Upgraded to v2.1", SOURCE) == []
    assert check_claims("Upgraded to v3.4", SOURCE) == [
        "the version v3.4 does not appear in the evidence"
    ]


def test_a_jd_keyword_absent_from_the_evidence_is_caught() -> None:
    text = "Batched writes into Snowflake"

    assert check_claims(text, SOURCE, extra_terms=["Snowflake"]) == [
        "'Snowflake' comes from the job description, not the evidence"
    ]
    assert check_claims(text, SOURCE) == []


def test_lint_flags_length_filler_tense_and_ownership() -> None:
    long_text = "Built " + "very " * 30 + "fast imports"

    assert lint_bullet(long_text, current=False, evidence_corpus="")[0].startswith("longer than")
    assert "uses the filler 'successfully'" in lint_bullet(
        "Successfully built the importer", current=False, evidence_corpus=""
    )
    assert lint_bullet("Build the importer for reports", current=False, evidence_corpus="") == [
        "a past role starts with a past-tense action verb"
    ]
    assert lint_bullet("Built the importer for reports", current=True, evidence_corpus="") == [
        "a current role is written in the present tense"
    ]
    assert lint_bullet("Cut the import time for reports", current=False, evidence_corpus="") == []
    assert lint_bullet("Cut the import time for reports", current=True, evidence_corpus="") == []


def test_an_ownership_upgrade_is_caught_unless_the_evidence_says_so() -> None:
    contributed = "Contributed a retry budget to the loader"
    bullet = "Led the retry budget for the loader"

    assert lint_bullet(bullet, current=False, evidence_corpus=contributed) == [
        "'led' claims more ownership than the evidence shows"
    ]
    assert lint_bullet(bullet, current=False, evidence_corpus="She led the retry work") == []


METRICS = [
    {"id": "a", "text": "42 minutes to 9 minutes", "verified": "evidence"},
    {"text": "saved 30% of cost", "verified": "needs_confirmation"},
]


def test_metric_ids_record_which_confirmed_metrics_a_bullet_uses() -> None:
    assert metric_ids_used("Cut the import from 42 to 9 minutes", METRICS) == ["a"]
    assert metric_ids_used("Cut the import time", METRICS) == []


def test_a_figure_from_an_unconfirmed_metric_is_flagged() -> None:
    assert unconfirmed_figures("Saved 30% of cost", METRICS) == [
        "the figure 30 is an unconfirmed metric (m1)"
    ]
    assert unconfirmed_figures("Saved cost", METRICS) == []
