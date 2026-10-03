from pathlib import Path
from typing import Any

import pytest
import yaml

from app.schemas.evidence import EvidenceItemData
from app.services.evidence_pipeline.noise import RULES, classify

BOTS = ["dependabot", "renovate", "github-actions", "snyk-bot"]
CASES: list[dict[str, Any]] = yaml.safe_load(
    (Path(__file__).resolve().parents[1] / "fixtures" / "evidence_noise_cases.yaml").read_text()
)


def _item(case: dict[str, Any]) -> EvidenceItemData:
    return EvidenceItemData(
        kind=case["kind"],
        external_id=case["name"],
        title=case.get("title"),
        body=case.get("body", ""),
        meta=case.get("meta", {}),
    )


@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_classify_matches_labelled_verdict(case: dict[str, Any]) -> None:
    verdict = classify(_item(case), BOTS)

    expected = case["expect"]
    assert verdict.kept is (expected == "kept")
    assert verdict.reason == (None if expected == "kept" else expected)


def test_classify_cases_cover_every_rule_and_stay_labelled() -> None:
    reasons = {c["expect"] for c in CASES}

    assert {reason for reason, _ in RULES} <= reasons
    assert "kept" in reasons
    assert len(CASES) >= 40


def test_classify_rule_order_is_fixed() -> None:
    assert [reason for reason, _ in RULES] == [
        "merge_commit",
        "bot_author",
        "dependency_bump",
        "lockfile_only",
        "trivial_message",
        "generated_or_vendored",
    ]


def test_classify_is_deterministic() -> None:
    items = [_item(c) for c in CASES]

    assert [classify(i, BOTS) for i in items] == [classify(i, BOTS) for i in items]


def test_classify_uses_configured_bot_list() -> None:
    item = EvidenceItemData(
        kind="commit",
        external_id="x",
        title="Refactor billing client",
        body="",
        meta={"author_login": "ci-robot", "additions": 50, "deletions": 5},
    )

    assert classify(item, BOTS).kept is True
    assert classify(item, [*BOTS, "CI-Robot"]).reason == "bot_author"
