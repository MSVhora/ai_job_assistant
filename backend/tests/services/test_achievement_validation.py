import pytest

from app.schemas.achievement import ExtractedAchievement, MetricClaim
from app.services.achievement_validation import (
    METRIC_UNVERIFIED_FLAG,
    PLACEHOLDER_FLAG,
    RESULT_REMOVED_FLAG,
    Rejection,
    ValidatedAchievement,
    validate,
)

TEXT = (
    "Cut the nightly import from 42 minutes to 9 minutes by batching writes. "
    "Reviewers confirmed the 78% drop in lock waits. Contact <EMAIL_1> for details."
)
LABELS = {"E1", "E2"}


def extracted(**overrides: object) -> ExtractedAchievement:
    base: dict[str, object] = {
        "title": "Faster nightly import",
        "situation": "The nightly import was slow.",
        "task": "Reduce its runtime.",
        "action": "Batched the writes.",
        "result": "Runtime fell from 42 to 9 minutes.",
        "result_quote": "from 42 minutes to 9 minutes",
        "metrics": [
            {
                "text": "42 minutes to 9 minutes",
                "source_quote": "from 42 minutes to 9 minutes",
                "evidence_ids": ["E1"],
            }
        ],
        "skills": ["python"],
        "impact_type": "performance",
        "difficulty": 3,
        "evidence_ids": ["E1"],
    }
    return ExtractedAchievement.model_validate({**base, **overrides})


def ok(outcome: ValidatedAchievement | Rejection) -> ValidatedAchievement:
    assert isinstance(outcome, ValidatedAchievement), outcome
    return outcome


def test_a_supported_achievement_passes_with_an_evidence_verified_metric() -> None:
    item = ok(validate(extracted(), chunk_text=TEXT, labels=LABELS))

    assert item.metrics[0]["verified"] == "evidence"
    assert item.result == "Runtime fell from 42 to 9 minutes."
    assert item.review_flags == []
    assert item.evidence_labels == ["E1"]


@pytest.mark.parametrize(
    ("evidence_ids", "reason"),
    [
        ([], "no_evidence"),
        (["E9"], "evidence_outside_chunk"),
        (["E1", "E9"], "evidence_outside_chunk"),
    ],
)
def test_empty_or_foreign_evidence_is_rejected(evidence_ids: list[str], reason: str) -> None:
    outcome = validate(extracted(evidence_ids=evidence_ids), chunk_text=TEXT, labels=LABELS)

    assert outcome == Rejection(reason)


def test_a_fabricated_number_moves_the_metric_to_needs_confirmation() -> None:
    fabricated = {
        "text": "99% faster",
        "source_quote": "from 42 minutes to 9 minutes",
        "evidence_ids": ["E1"],
    }

    item = ok(validate(extracted(metrics=[fabricated]), chunk_text=TEXT, labels=LABELS))

    assert item.metrics[0]["verified"] == "needs_confirmation"
    assert METRIC_UNVERIFIED_FLAG in item.review_flags


def test_a_quote_that_is_not_in_the_evidence_is_not_verified() -> None:
    invented = {"text": "78%", "source_quote": "a 78% win nobody wrote", "evidence_ids": ["E1"]}

    item = ok(validate(extracted(metrics=[invented]), chunk_text=TEXT, labels=LABELS))

    assert item.metrics[0]["verified"] == "needs_confirmation"


def test_metric_without_numbers_or_with_foreign_evidence_needs_confirmation() -> None:
    claims = [
        MetricClaim(text="much faster", source_quote="batching writes", evidence_ids=["E1"]),
        MetricClaim(text="9 minutes", source_quote="to 9 minutes", evidence_ids=["E7"]),
        MetricClaim(text="9 minutes", source_quote="to 9 minutes", evidence_ids=[]),
    ]

    item = ok(
        validate(
            extracted(metrics=[claim.model_dump() for claim in claims]),
            chunk_text=TEXT,
            labels=LABELS,
        )
    )

    assert [m["verified"] for m in item.metrics] == ["needs_confirmation"] * 3


def test_number_matching_ignores_case_and_whitespace_differences() -> None:
    claim = {
        "text": "78%",
        "source_quote": "the  78% DROP in lock waits",
        "evidence_ids": ["E1"],
    }

    item = ok(validate(extracted(metrics=[claim]), chunk_text=TEXT, labels=LABELS))

    assert item.metrics[0]["verified"] == "evidence"


def test_result_without_a_supporting_quote_is_dropped() -> None:
    item = ok(
        validate(
            extracted(result="Saved the company a lot of money", result_quote=None),
            chunk_text=TEXT,
            labels=LABELS,
        )
    )

    assert item.result is None
    assert item.result_quote is None
    assert RESULT_REMOVED_FLAG in item.review_flags


def test_result_with_an_invented_quote_is_dropped() -> None:
    item = ok(
        validate(
            extracted(result="Revenue grew", result_quote="revenue grew 5x"),
            chunk_text=TEXT,
            labels=LABELS,
        )
    )

    assert item.result is None


def test_no_result_stays_null_without_a_flag() -> None:
    item = ok(
        validate(
            extracted(result=None, result_quote=None, metrics=[]), chunk_text=TEXT, labels=LABELS
        )
    )

    assert (item.result, item.metrics, item.review_flags) == (None, [], [])


def test_redaction_placeholders_flag_the_draft() -> None:
    item = ok(
        validate(
            extracted(action="Emailed <EMAIL_1> about the batching."),
            chunk_text=TEXT,
            labels=LABELS,
        )
    )

    assert PLACEHOLDER_FLAG in item.review_flags


def test_title_is_trimmed_and_difficulty_clamped() -> None:
    item = ok(validate(extracted(title="T" * 200, difficulty=9), chunk_text=TEXT, labels=LABELS))
    low = ok(validate(extracted(difficulty=-3), chunk_text=TEXT, labels=LABELS))

    assert len(item.title) == 80
    assert (item.difficulty, low.difficulty) == (5, 1)


def test_dates_parse_or_become_none_and_duplicate_labels_collapse() -> None:
    item = ok(
        validate(
            extracted(time_start="2024-03-01", time_end="soon", evidence_ids=["E1", "E1", "E2"]),
            chunk_text=TEXT,
            labels=LABELS,
        )
    )

    assert (item.time_start.isoformat(), item.time_end) == ("2024-03-01", None)  # type: ignore[union-attr]
    assert item.evidence_labels == ["E1", "E2"]
