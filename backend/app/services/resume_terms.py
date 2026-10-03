import re
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from functools import lru_cache

from app.schemas.resume_document import GapItem, JDAnalysis
from app.services.skill_canon import load_aliases

# Aliases that are ordinary English words (or too short to trust): matched only in their
# canonical spelling, or not at all, so prose like "the rest of the team" is never a tool.
CASE_SENSITIVE_ALIASES = {
    "go": "Go",
    "rest": "REST",
    "swift": "Swift",
    "rust": "Rust",
    "ci": "CI",
    "ml": "ML",
}
DROPPED_ALIASES = frozenset({"next", "containers", "torch", "tf", "tf2", "py", "node"})
WORDS = re.compile(r"[a-z][a-z0-9+#.]{2,}")
STOPWORDS = frozenset(
    {
        "and",
        "the",
        "for",
        "with",
        "years",
        "year",
        "experience",
        "strong",
        "knowledge",
        "ability",
        "using",
        "work",
        "working",
        "skills",
        "have",
        "you",
        "our",
        "are",
        "will",
    }
)
GAP_OVERLAP_SHARE = 0.5
MAX_EVIDENCE_PREVIEW = 160


def canon(term: str) -> str:
    cleaned = term.strip()
    return load_aliases().get(cleaned.lower(), cleaned).lower()


@lru_cache(maxsize=1)
def _skill_pattern() -> re.Pattern[str]:
    aliases = load_aliases()
    names = sorted(
        (
            alias
            for alias in aliases
            if alias not in DROPPED_ALIASES and alias not in CASE_SENSITIVE_ALIASES
        ),
        key=len,
        reverse=True,
    )
    return re.compile(
        r"(?<![A-Za-z0-9])(" + "|".join(re.escape(name) for name in names) + r")(?![A-Za-z0-9])",
        re.IGNORECASE,
    )


@lru_cache(maxsize=1)
def _case_sensitive_pattern() -> re.Pattern[str]:
    spellings = sorted(set(CASE_SENSITIVE_ALIASES.values()), key=len, reverse=True)
    return re.compile(
        r"(?<![A-Za-z0-9])(" + "|".join(re.escape(name) for name in spellings) + r")(?![A-Za-z0-9])"
    )


def scan_skills(text: str) -> list[tuple[str, str]]:
    """(matched wording, canonical lowercase key) for every recognised tool in `text`."""
    found = [(m.group(1), canon(m.group(1))) for m in _skill_pattern().finditer(text)]
    found.extend((m.group(1), canon(m.group(1))) for m in _case_sensitive_pattern().finditer(text))
    return found


def skill_keys(text: str) -> set[str]:
    return {key for _, key in scan_skills(text)}


@dataclass(frozen=True)
class AllowedTerm:
    wording: str
    canonical: str


def jd_skill_wordings(jd: JDAnalysis) -> dict[str, str]:
    """canonical key -> the JD's own wording, from keywords and the skills named in the lists."""
    wordings: dict[str, str] = {}
    for keyword in jd.keywords:
        if keyword.strip():
            wordings.setdefault(canon(keyword), keyword.strip())
    for line in [*jd.must_haves, *jd.nice_to_haves]:
        for wording, key in scan_skills(line):
            wordings.setdefault(key, wording)
    return wordings


def allowed_terms(
    jd: JDAnalysis | None, achievement_skills: Iterable[str], corpus: str
) -> tuple[list[AllowedTerm], list[str]]:
    """(allowed, disallowed JD wordings) for one achievement.

    allowed = (JD terms + their synonyms) ∩ (achievement skills ∪ terms in its evidence).
    """
    if jd is None:
        return [], []
    lowered = corpus.casefold()
    supported = {canon(skill) for skill in achievement_skills} | skill_keys(corpus)
    allowed: list[AllowedTerm] = []
    disallowed: list[str] = []
    for key, wording in jd_skill_wordings(jd).items():
        if key in supported or wording.casefold() in lowered:
            allowed.append(AllowedTerm(wording, key))
        else:
            disallowed.append(wording)
    return allowed, disallowed


@dataclass(frozen=True)
class GapSource:
    achievement_id: uuid.UUID
    title: str
    skills: tuple[str, ...]
    corpus: str


def _content_words(text: str) -> set[str]:
    return {word for word in WORDS.findall(text.casefold()) if word not in STOPWORDS}


def _is_supported(requirement: str, supported: set[str], words: set[str]) -> bool:
    named = skill_keys(requirement)
    if named:
        return named <= supported
    needed = _content_words(requirement)
    return bool(needed) and len(needed & words) / len(needed) >= GAP_OVERLAP_SHARE


def gaps_report(jd: JDAnalysis | None, sources: list[GapSource]) -> list[GapItem]:
    """Each JD must-have with no supporting evidence, with the nearest achievement if any."""
    if jd is None:
        return []
    supported: set[str] = set()
    words: set[str] = set()
    for source in sources:
        supported |= {canon(skill) for skill in source.skills} | skill_keys(source.corpus)
        words |= _content_words(source.corpus)
    gaps: list[GapItem] = []
    for requirement in jd.must_haves:
        if not requirement.strip() or _is_supported(requirement, supported, words):
            continue
        needed = _content_words(requirement)
        best = max(
            sources,
            key=lambda source: len(needed & _content_words(source.corpus)),
            default=None,
        )
        overlap = len(needed & _content_words(best.corpus)) if best else 0
        gaps.append(
            GapItem(
                requirement=requirement.strip(),
                nearest_evidence=best.title[:MAX_EVIDENCE_PREVIEW] if best and overlap else None,
                nearest_achievement_id=best.achievement_id if best and overlap else None,
            )
        )
    return gaps
