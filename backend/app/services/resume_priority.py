import math
import uuid
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, replace
from datetime import date

from app.core.config import Settings
from app.models import Achievement
from app.schemas.resume_document import TailoringStrength, WorkEntry
from app.services.company_names import normalize_company
from app.services.profile_derivation import resolve_date
from app.services.resume_terms import canon

BUDGET_SEEDS = {1: 15, 2: 28, 3: 40, 4: 52}
IMPACT_TYPE_WEIGHT = {
    "revenue": 1.0,
    "cost": 1.0,
    "performance": 0.9,
    "reliability": 0.8,
    "scale": 0.8,
    "security": 0.8,
    "quality": 0.7,
    "velocity": 0.7,
    "leadership": 0.7,
    "ux": 0.6,
    "other": 0.4,
}
CONFIRMED_METRICS = ("evidence", "user")
METRIC_SHARE = 0.4
RECENCY_HALF_LIFE_YEARS = 3.0
NEUTRAL_RECENCY = 0.5
MMR_LAMBDA = 0.7
VECTOR_SHARE = 0.6
TERM_HITS_SATURATION = 2
LIGHT_FACTOR = 0.5
MAX_JD_WEIGHT = 0.5
ROLE_TOP_N = 3
ROLE_WEIGHTS = (1.0, 0.6, 0.4)
ROLE_RECENCY_SHARE = 0.1
DAYS_PER_YEAR = 365.25


@dataclass(frozen=True)
class Candidate:
    achievement_id: uuid.UUID
    title: str
    block_id: str
    base: float
    alignment: float
    priority: float
    skills: frozenset[str]
    embedding: tuple[float, ...] | None
    from_private: bool


def tailoring_weight(strength: TailoringStrength, settings: Settings, *, has_jd: bool) -> float:
    """w in `priority = (1 - w) * base + w * alignment`; 0 without a JD."""
    if not has_jd:
        return 0.0
    if strength == "light":
        return settings.resume_jd_weight * LIGHT_FACTOR
    if strength == "strong":
        return MAX_JD_WEIGHT
    return settings.resume_jd_weight


def recency_factor(end: date | None, start: date | None, today: date) -> float:
    anchor = end or start
    if anchor is None:
        return NEUTRAL_RECENCY
    years = max(0.0, (today - anchor).days / DAYS_PER_YEAR)
    return 0.5 ** (years / RECENCY_HALF_LIFE_YEARS)


def base_priority(achievement: Achievement, today: date, settings: Settings) -> float:
    """JD-independent priority: impact (type + a confirmed metric), difficulty and recency."""
    has_metric = any(metric.get("verified") in CONFIRMED_METRICS for metric in achievement.metrics)
    type_weight = IMPACT_TYPE_WEIGHT.get(achievement.impact_type, IMPACT_TYPE_WEIGHT["other"])
    impact = (1 - METRIC_SHARE) * type_weight + METRIC_SHARE * (1.0 if has_metric else 0.0)
    difficulty = (min(5, max(1, achievement.difficulty)) - 1) / 4
    recency = recency_factor(achievement.time_end, achievement.time_start, today)
    return (
        settings.resume_weight_impact * impact
        + settings.resume_weight_difficulty * difficulty
        + settings.resume_weight_recency * recency
    )


def cosine(first: Sequence[float], second: Sequence[float]) -> float:
    dot = sum(a * b for a, b in zip(first, second, strict=False))
    norm = math.sqrt(sum(a * a for a in first)) * math.sqrt(sum(b * b for b in second))
    return dot / norm if norm else 0.0


def alignment(
    skills: Iterable[str],
    embedding: Sequence[float] | None,
    terms: set[str],
    jd_vector: Sequence[float] | None,
) -> float:
    """[0, 1]: JD-vector cosine blended with JD-term hits (two hits count as fully aligned)."""
    own = {canon(skill) for skill in skills}
    overlap = min(1.0, len(own & terms) / TERM_HITS_SATURATION) if terms else 0.0
    if jd_vector is None or embedding is None:
        return overlap
    similarity = max(0.0, cosine(jd_vector, embedding))
    return VECTOR_SHARE * similarity + (1 - VECTOR_SHARE) * overlap


def blended(base: float, aligned: float, weight: float) -> float:
    return (1 - weight) * base + weight * aligned


def _similarity(first: Candidate, second: Candidate) -> float:
    if first.embedding is not None and second.embedding is not None:
        return max(0.0, cosine(first.embedding, second.embedding))
    union = first.skills | second.skills
    return len(first.skills & second.skills) / len(union) if union else 0.0


def mmr_order(candidates: Sequence[Candidate], lam: float = MMR_LAMBDA) -> list[Candidate]:
    """Greedy maximal-marginal-relevance order: priority, minus similarity to what is chosen."""
    remaining = sorted(candidates, key=lambda item: (-item.priority, str(item.achievement_id)))
    chosen: list[Candidate] = []
    while remaining:
        best = max(
            remaining,
            key=lambda item: (
                lam * item.priority
                - (1 - lam) * max((_similarity(item, other) for other in chosen), default=0.0),
                item.priority,
                str(item.achievement_id),
            ),
        )
        chosen.append(best)
        remaining.remove(best)
    return chosen


def role_priority(priorities: Sequence[float], recency: float) -> float:
    """Relevance-weighted mean of a role's top-3 achievement priorities, plus a recency term."""
    top = sorted(priorities, reverse=True)[:ROLE_TOP_N]
    weights = ROLE_WEIGHTS[: len(top)]
    weighted = sum(w * p for w, p in zip(weights, top, strict=False)) / sum(ROLE_WEIGHTS)
    return (1 - ROLE_RECENCY_SHARE) * weighted + ROLE_RECENCY_SHARE * recency


def candidate_pool_size(page_target: int, oversample: float) -> int:
    return math.ceil(BUDGET_SEEDS[page_target] * oversample)


def select_for_writing(
    ordered: Sequence[Candidate], page_target: int, oversample: float
) -> list[Candidate]:
    """Top `ceil(budget x oversample)` candidates, always including each block's best one."""
    size = candidate_pool_size(page_target, oversample)
    anchors: dict[str, Candidate] = {}
    for candidate in ordered:
        anchors.setdefault(candidate.block_id, candidate)
    picked = list(anchors.values())
    chosen_ids = {item.achievement_id for item in picked}
    for candidate in ordered:
        if len(picked) >= max(size, len(anchors)):
            break
        if candidate.achievement_id not in chosen_ids:
            picked.append(candidate)
            chosen_ids.add(candidate.achievement_id)
    rank = {item.achievement_id: index for index, item in enumerate(ordered)}
    return sorted(picked, key=lambda item: rank[item.achievement_id])


@dataclass(frozen=True)
class RoleSpan:
    block_id: str
    company: str | None
    title: str | None
    start: date | None
    end: date | None
    priority: float


def role_span(entry: WorkEntry, priority: float, today: date) -> RoleSpan:
    """The role's window, parsed like the reconciliation detector; current roles end today."""
    start = resolve_date(entry.start_date)
    end = resolve_date(entry.end_date)
    if end is None and entry.is_current:
        end = today
    if start is not None and end is not None:
        end = max(start, end)
    return RoleSpan(entry.id, entry.company, entry.title, start, end, priority)


def overlap_days(first: RoleSpan, second: RoleSpan) -> int:
    if first.start is None or second.start is None:
        return 0
    first_end = first.end or first.start
    second_end = second.end or second.start
    return (min(first_end, second_end) - max(first.start, second.start)).days + 1


@dataclass(frozen=True)
class Omission:
    role: RoleSpan
    blocker: RoleSpan


def resolve_overlaps(
    roles: Sequence[RoleSpan],
    min_days: int,
    forced: frozenset[str] = frozenset(),
    company_key: Callable[[str | None], str] = normalize_company,
) -> tuple[list[RoleSpan], list[Omission]]:
    """Keep the higher-priority role of any overlapping pair (tie: the more recent).

    Roles in `forced` ("include anyway") are always kept and neither block nor are blocked by
    other roles. Unparsable dates never overlap. Roles at the same employer never block each
    other (concurrent stints at one company are not a conflict). Results keep the input order.
    """

    def same_employer(first: RoleSpan, second: RoleSpan) -> bool:
        key = company_key(first.company)
        return key != "" and key == company_key(second.company)

    def order(role: RoleSpan) -> tuple[float, int, str]:
        anchor = role.end or role.start
        return (-role.priority, -anchor.toordinal() if anchor else 0, role.block_id)

    blockers: list[RoleSpan] = []
    omitted: list[Omission] = []
    for role in sorted((item for item in roles if item.block_id not in forced), key=order):
        blocker = next(
            (
                item
                for item in blockers
                if overlap_days(role, item) >= min_days and not same_employer(role, item)
            ),
            None,
        )
        if blocker is None:
            blockers.append(role)
        else:
            omitted.append(Omission(role, blocker))
    dropped = {item.role.block_id for item in omitted}
    position = {role.block_id: index for index, role in enumerate(roles)}
    kept = [role for role in roles if role.block_id not in dropped]
    omitted.sort(key=lambda item: position[item.role.block_id])
    return kept, omitted


def with_priority(candidate: Candidate, priority: float) -> Candidate:
    return replace(candidate, priority=priority)
