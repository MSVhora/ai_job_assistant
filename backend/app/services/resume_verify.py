import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from app.services.resume_terms import canon, scan_skills, skill_keys

MAX_WORDS = 28
MIN_WORDS = 3
CONFIRMED = ("evidence", "user")
MULTIPLIERS = {"k": Decimal(1000), "million": Decimal(1_000_000), "billion": Decimal(10**9)}
NUMBER = re.compile(
    r"(?<![\w.])(?P<num>\d[\d,]*(?:\.\d+)?)"
    r"(?:\s?(?P<mult>k|million|billion)\b)?"
    r"(?:\s?(?:%|percent\b|x\b))?(?![A-Za-z0-9_])",
    re.IGNORECASE,
)
VERSION = re.compile(
    r"(?<![\w.])(?:v\d+(?:\.\d+)*|v?\d+(?:\.\d+){2,})(?![\w])",
    re.IGNORECASE,
)
BANNED_PHRASES = (
    "successfully",
    "robust",
    "responsible for",
    "various",
    "world-class",
    "cutting-edge",
    "passionate",
    "synergy",
)
IRREGULAR_PAST = frozenset(
    [
        "led",
        "built",
        "ran",
        "wrote",
        "made",
        "won",
        "drove",
        "took",
        "gave",
        "found",
        "began",
        "chose",
        "grew",
        "held",
        "kept",
        "knew",
        "left",
        "lost",
        "met",
        "paid",
        "sent",
        "sold",
        "spoke",
        "spent",
        "stood",
        "taught",
        "thought",
        "told",
        "understood",
        "wrought",
        "overhauled",
        "shipped",
        "fed",
        "flew",
        "froze",
        "got",
        "hid",
        "saw",
        "shook",
        "sang",
        "sank",
        "slid",
        "swept",
        "swung",
        "threw",
        "wove",
    ]
)
SAME_TENSE = frozenset(
    [
        "cut",
        "set",
        "put",
        "read",
        "hit",
        "shut",
        "spread",
        "cost",
        "let",
        "quit",
        "split",
        "bid",
        "upset",
    ]
)
NOT_PAST_ED = frozenset(
    ["embed", "speed", "need", "feed", "proceed", "succeed", "bleed", "breed", "exceed", "seed"]
)
OWNERSHIP_FAMILIES = (
    r"\b(led|lead|leads|leading|leader)\b",
    r"\b(own|owns|owned|owning|owner|ownership)\b",
    r"\barchitect(ed|s|ing|ure)?\b",
    r"\bdirect(ed|s|ing|or)?\b",
    r"\bspearhead(ed|s|ing)?\b",
    r"\bmanag(e|ed|es|ing|er|ement)\b",
    r"\bhead(ed|s|ing)?\b",
    r"\bfound(ed|s|ing|er)\b",
    r"\bpioneer(ed|s|ing)?\b",
)


@dataclass(frozen=True)
class Source:
    """What a bullet may claim: the cited evidence text, its tool names and its numbers."""

    corpus: str
    skills: frozenset[str]
    numbers: frozenset[Decimal]


def _value(match: re.Match[str]) -> Decimal | None:
    try:
        value = Decimal(match.group("num").replace(",", "").rstrip("."))
    except InvalidOperation:
        return None
    multiplier = match.group("mult")
    return (value * MULTIPLIERS[multiplier.lower()] if multiplier else value).normalize()


def numbers_in(text: str) -> set[Decimal]:
    """Numeric values in `text`; `40%` and `40 percent` agree, `10k` equals `10,000`."""
    stripped = VERSION.sub(" ", text)
    values = (_value(match) for match in NUMBER.finditer(stripped))
    return {value for value in values if value is not None}


def build_source(
    parts: Iterable[str], skills: Iterable[str] = (), years: Iterable[int] = ()
) -> Source:
    corpus = "\n".join(part for part in parts if part)
    return Source(
        corpus=corpus,
        skills=frozenset({canon(skill) for skill in skills if skill.strip()} | skill_keys(corpus)),
        numbers=frozenset(numbers_in(corpus) | {Decimal(year) for year in years}),
    )


def merge_sources(sources: Iterable[Source]) -> Source:
    items = list(sources)
    skills: set[str] = set()
    numbers: set[Decimal] = set()
    for item in items:
        skills |= item.skills
        numbers |= item.numbers
    return Source(
        corpus="\n".join(item.corpus for item in items),
        skills=frozenset(skills),
        numbers=frozenset(numbers),
    )


def _version_in(version: str, corpus: str) -> bool:
    bare = re.escape(version.lower().lstrip("v"))
    return re.search(rf"(?<![\w.])v?{bare}(?![\w])", corpus.casefold()) is not None


def check_claims(text: str, source: Source, extra_terms: Iterable[str] = ()) -> list[str]:
    """Deterministic claim check: every number, version, year and tool must be in the evidence."""
    violations: list[str] = []
    violations.extend(
        f"the figure {value:f} does not appear in the evidence"
        for value in sorted(numbers_in(text))
        if value not in source.numbers
    )
    violations.extend(
        f"the version {match.group(0)} does not appear in the evidence"
        for match in VERSION.finditer(text)
        if not _version_in(match.group(0), source.corpus)
    )
    seen: set[str] = set()
    for wording, key in scan_skills(text):
        if key not in source.skills and key not in seen:
            seen.add(key)
            violations.append(f"the tool {wording} does not appear in the evidence")
    lowered = source.corpus.casefold()
    for term in extra_terms:
        wording = term.strip()
        pattern = rf"(?<![A-Za-z0-9]){re.escape(wording)}(?![A-Za-z0-9])"
        if (
            wording
            and canon(wording) not in seen
            and re.search(pattern, text, re.IGNORECASE)
            and wording.casefold() not in lowered
            and canon(wording) not in source.skills
        ):
            seen.add(canon(wording))
            violations.append(f"'{wording}' comes from the job description, not the evidence")
    return violations


def _is_past(word: str) -> bool:
    return word in IRREGULAR_PAST or (word.endswith("ed") and word not in NOT_PAST_ED)


def _lint_tense(first: str, *, current: bool) -> str | None:
    if first in SAME_TENSE:
        return None
    if current and _is_past(first):
        return "a current role is written in the present tense"
    if not current and not _is_past(first):
        return "a past role starts with a past-tense action verb"
    return None


def lint_bullet(text: str, *, current: bool, evidence_corpus: str) -> list[str]:
    """Style and honesty rules that need no model: length, tense, filler, ownership verbs."""
    words = text.split()
    violations: list[str] = []
    if len(words) > MAX_WORDS:
        violations.append(f"longer than {MAX_WORDS} words")
    if len(words) < MIN_WORDS:
        violations.append(f"shorter than {MIN_WORDS} words")
    lowered = text.casefold()
    violations.extend(f"uses the filler '{p}'" for p in BANNED_PHRASES if p in lowered)
    if words:
        first = re.sub(r"[^a-z]", "", words[0].casefold())
        if (problem := _lint_tense(first, current=current)) is not None:
            violations.append(problem)
        evidence = evidence_corpus.casefold()
        for family in OWNERSHIP_FAMILIES:
            used = re.search(family, lowered)
            if used and not re.search(family, evidence):
                message = f"'{used.group(0)}' claims more ownership than the evidence shows"
                violations.append(message)
                break
    return violations


def confirmed_metrics(metrics: Iterable[Mapping[str, object]]) -> list[tuple[str, str]]:
    """(metric id, text) of the metrics the user or the evidence confirmed."""
    return [
        (str(metric.get("id") or f"m{index}"), str(metric.get("text") or ""))
        for index, metric in enumerate(metrics)
        if metric.get("verified") in CONFIRMED
    ]


def metric_ids_used(text: str, metrics: Iterable[Mapping[str, object]]) -> list[str]:
    used = numbers_in(text)
    return [
        metric_id
        for metric_id, metric_text in confirmed_metrics(metrics)
        if (values := numbers_in(metric_text)) and values <= used
    ]


def unconfirmed_figures(text: str, metrics: Iterable[Mapping[str, object]]) -> list[str]:
    """Figures that come only from a metric nobody has confirmed."""
    confirmed: set[Decimal] = set()
    for _, metric_text in confirmed_metrics(metrics):
        confirmed |= numbers_in(metric_text)
    used = numbers_in(text)
    violations: list[str] = []
    for index, metric in enumerate(metrics):
        if metric.get("verified") in CONFIRMED:
            continue
        unconfirmed = numbers_in(str(metric.get("text") or "")) & used - confirmed
        violations.extend(
            f"the figure {value:f} is an unconfirmed metric (m{index})"
            for value in sorted(unconfirmed)
        )
    return violations
