import re
from dataclasses import dataclass, field
from datetime import date

from app.schemas.achievement import ExtractedAchievement, ImpactType, MetricClaim

PLACEHOLDER_FLAG = "contains_redaction_placeholder"
RESULT_REMOVED_FLAG = "result_removed_unsupported"
METRIC_UNVERIFIED_FLAG = "metric_needs_confirmation"
TITLE_MAX = 80
DIFFICULTY_MIN = 1
DIFFICULTY_MAX = 5
_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?%?")
_PLACEHOLDER = re.compile(r"<[A-Z_]+_\d+>")


@dataclass(frozen=True)
class Rejection:
    reason: str


@dataclass(frozen=True)
class ValidatedAchievement:
    title: str
    situation: str
    task: str
    action: str
    result: str | None
    result_quote: str | None
    metrics: list[dict[str, object]]
    skills: list[str]
    impact_type: ImpactType
    difficulty: int
    evidence_labels: list[str]
    time_start: date | None
    time_end: date | None
    review_flags: list[str] = field(default_factory=list[str])


def _norm(text: str) -> str:
    return " ".join(text.split()).casefold()


def _contains(haystack: str, needle: str) -> bool:
    cleaned = _norm(needle)
    return bool(cleaned) and cleaned in _norm(haystack)


def _parse_date(value: str | None) -> date | None:
    try:
        return date.fromisoformat(value.strip()) if value else None
    except ValueError:
        return None


def _metric(metric: MetricClaim, chunk_text: str, labels: set[str]) -> dict[str, object]:
    numbers = _NUMBER.findall(metric.text)
    cited = [label for label in metric.evidence_ids if label in labels]
    verified = (
        bool(numbers)
        and _contains(chunk_text, metric.source_quote)
        and all(_contains(metric.source_quote, number) for number in numbers)
        and bool(cited)
        and len(cited) == len(metric.evidence_ids)
    )
    return {
        "text": metric.text,
        "source_quote": metric.source_quote,
        "evidence_ids": cited,
        "verified": "evidence" if verified else "needs_confirmation",
    }


def validate(
    extracted: ExtractedAchievement, *, chunk_text: str, labels: set[str]
) -> ValidatedAchievement | Rejection:
    """Enforce after parsing what the prompt only asks for (no invented evidence or numbers)."""
    cited = list(dict.fromkeys(extracted.evidence_ids))
    if not cited:
        return Rejection("no_evidence")
    if any(label not in labels for label in cited):
        return Rejection("evidence_outside_chunk")
    flags: list[str] = []
    metrics = [_metric(metric, chunk_text, labels) for metric in extracted.metrics]
    if any(metric["verified"] != "evidence" for metric in metrics):
        flags.append(METRIC_UNVERIFIED_FLAG)
    result = extracted.result.strip() if extracted.result else None
    result_quote = extracted.result_quote.strip() if extracted.result_quote else None
    if result and not (result_quote and _contains(chunk_text, result_quote)):
        result, result_quote = None, None
        flags.append(RESULT_REMOVED_FLAG)
    if not result:
        result_quote = None
    title = extracted.title.strip()[:TITLE_MAX].rstrip()
    visible = " ".join(
        [title, extracted.situation, extracted.task, extracted.action, result or ""]
        + [str(metric["text"]) for metric in metrics]
    )
    if _PLACEHOLDER.search(visible):
        flags.append(PLACEHOLDER_FLAG)
    return ValidatedAchievement(
        title=title,
        situation=extracted.situation.strip(),
        task=extracted.task.strip(),
        action=extracted.action.strip(),
        result=result,
        result_quote=result_quote,
        metrics=metrics,
        skills=[skill for skill in extracted.skills if skill.strip()],
        impact_type=extracted.impact_type,
        difficulty=min(DIFFICULTY_MAX, max(DIFFICULTY_MIN, extracted.difficulty)),
        evidence_labels=cited,
        time_start=_parse_date(extracted.time_start),
        time_end=_parse_date(extracted.time_end),
        review_flags=flags,
    )
