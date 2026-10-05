import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.llm import LLMError
from app.core.config import Settings, get_settings
from app.models import (
    Achievement,
    AchievementEvidence,
    AchievementStatus,
    EvidenceChunk,
    EvidenceChunkItem,
    EvidenceItem,
)
from app.schemas.agent import CitationKind
from app.services.embedding import embed_texts
from app.services.redaction import redact
from app.services.resume_priority import (
    CONFIRMED_METRICS,
    IMPACT_TYPE_WEIGHT,
    METRIC_SHARE,
    recency_factor,
)
from app.services.resume_terms import canon, skill_keys

logger = logging.getLogger(__name__)

TOP_ACHIEVEMENTS = 6
INTRO_ACHIEVEMENTS = 3
CHUNKS_PER_ACHIEVEMENT = 2
ITEMS_PER_ACHIEVEMENT = 3
ITEM_CHARS = 500
CHUNK_CHARS = 900
MIN_NAME_CHARS = 3
INTRO_IMPACT_SHARE = 0.6


@dataclass(frozen=True)
class ContextBlock:
    """One citable piece of context. `corpus` is what a sentence citing the marker may rest on."""

    marker: str
    kind: CitationKind
    text: str
    corpus: tuple[str, ...]
    skills: tuple[str, ...] = ()
    achievement_id: uuid.UUID | None = None
    evidence_item_id: uuid.UUID | None = None
    url: str | None = None
    quote: str | None = None
    private: bool = False


@dataclass
class Retrieval:
    approved: int = 0
    best_score: float = 0.0
    blocks: list[ContextBlock] = field(default_factory=list[ContextBlock])
    achievement_ids: list[uuid.UUID] = field(default_factory=list[uuid.UUID])


def impact_score(achievement: Achievement) -> float:
    has_metric = any(metric.get("verified") in CONFIRMED_METRICS for metric in achievement.metrics)
    type_weight = IMPACT_TYPE_WEIGHT.get(achievement.impact_type, IMPACT_TYPE_WEIGHT["other"])
    return (1 - METRIC_SHARE) * type_weight + METRIC_SHARE * (1.0 if has_metric else 0.0)


def skill_overlap(query_keys: set[str], achievement: Achievement) -> float:
    if not query_keys:
        return 0.0
    keys = {canon(skill) for skill in achievement.skills} | skill_keys(achievement.title)
    return len(query_keys & keys) / len(query_keys)


def hybrid_score(
    *, cosine: float, overlap: float, achievement: Achievement, today: date, settings: Settings
) -> float:
    recency = recency_factor(achievement.time_end, achievement.time_start, today)
    return (
        settings.agent_weight_cosine * max(0.0, cosine)
        + settings.agent_weight_overlap * overlap
        + settings.agent_weight_recency * recency
        + settings.agent_weight_impact * impact_score(achievement)
    )


def _mentions(question: str, name: str | None) -> bool:
    if name is None or len(name) < MIN_NAME_CHARS:
        return False
    return (
        re.search(rf"(?<![A-Za-z0-9]){re.escape(name)}(?![A-Za-z0-9])", question, re.IGNORECASE)
        is not None
    )


def filter_by_mention(question: str, rows: list[Achievement]) -> list[Achievement]:
    """Narrow to the project or employer the question names; keep all when none matches."""
    matched: list[Achievement] = []
    for achievement in rows:
        project = (achievement.project_key or "").rsplit("/", 1)[-1] or None
        company = (achievement.employer_ref or {}).get("company")
        if _mentions(question, project) or (
            isinstance(company, str) and _mentions(question, company)
        ):
            matched.append(achievement)
    return matched or rows


def _achievement_text(achievement: Achievement) -> str:
    lines = [f"Title: {achievement.title}"]
    for label, value in (
        ("Situation", achievement.situation),
        ("Task", achievement.task),
        ("Action", achievement.action),
        ("Result", achievement.result),
    ):
        if value:
            lines.append(f"{label}: {value}")
    confirmed = [
        str(metric.get("text") or "")
        for metric in achievement.metrics
        if metric.get("verified") in CONFIRMED_METRICS
    ]
    if confirmed:
        lines.append("Confirmed metrics: " + "; ".join(confirmed))
    if achievement.skills:
        lines.append("Skills: " + ", ".join(achievement.skills))
    if achievement.project_key:
        lines.append(f"Project: {achievement.project_key}")
    company = (achievement.employer_ref or {}).get("company")
    if isinstance(company, str) and company:
        lines.append(f"Employer: {company}")
    if achievement.time_start:
        end = achievement.time_end.isoformat() if achievement.time_end else "present"
        lines.append(f"Period: {achievement.time_start.isoformat()} to {end}")
    return redact("\n".join(lines)).text


def _snippet(item: EvidenceItem, limit: int) -> str:
    text = " ".join(f"{item.title or ''} {item.body}".split())
    return redact(text).text[:limit]


async def _query_vector(query: str) -> list[float] | None:
    try:
        return (await embed_texts([query]))[0]
    except LLMError as exc:
        logger.warning("agent.retrieval query embedding failed error=%s", exc)
        return None


async def _ranked(
    session: AsyncSession, candidate_id: uuid.UUID, vector: list[float] | None
) -> list[tuple[Achievement, float]]:
    columns = [Achievement]
    if vector is not None:
        columns.append(Achievement.embedding.cosine_distance(vector).label("distance"))
    statement = select(*columns).where(
        Achievement.candidate_id == candidate_id,
        Achievement.status == AchievementStatus.approved,
    )
    rows = (await session.execute(statement)).all()
    ranked: list[tuple[Achievement, float]] = []
    for row in rows:
        distance = row[1] if vector is not None and len(row) > 1 else None
        ranked.append((row[0], 0.0 if distance is None else 1.0 - float(distance)))
    return ranked


def select_hits(
    ranked: list[tuple[Achievement, float]],
    query: str,
    *,
    intro: bool,
    today: date,
    settings: Settings,
) -> tuple[list[tuple[Achievement, float]], float]:
    """Top achievements with their score, and the best score seen (before the floor)."""
    if intro:
        scored = [
            (
                achievement,
                INTRO_IMPACT_SHARE * impact_score(achievement)
                + (1 - INTRO_IMPACT_SHARE)
                * recency_factor(achievement.time_end, achievement.time_start, today),
            )
            for achievement, _ in ranked
        ]
        scored.sort(key=lambda pair: (-pair[1], str(pair[0].id)))
        return scored[:INTRO_ACHIEVEMENTS], scored[0][1] if scored else 0.0
    allowed = {a.id for a in filter_by_mention(query, [a for a, _ in ranked])}
    query_keys = skill_keys(query)
    scored = [
        (
            achievement,
            hybrid_score(
                cosine=cosine,
                overlap=skill_overlap(query_keys, achievement),
                achievement=achievement,
                today=today,
                settings=settings,
            ),
        )
        for achievement, cosine in ranked
        if achievement.id in allowed
    ]
    scored.sort(key=lambda pair: (-pair[1], str(pair[0].id)))
    best = scored[0][1] if scored else 0.0
    kept = [pair for pair in scored if pair[1] >= settings.agent_min_retrieval_score]
    return kept[:TOP_ACHIEVEMENTS], best


async def _linked_items(
    session: AsyncSession, achievement_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[EvidenceItem]]:
    rows = (
        await session.execute(
            select(AchievementEvidence, EvidenceItem)
            .join(EvidenceItem, EvidenceItem.id == AchievementEvidence.item_id)
            .where(AchievementEvidence.achievement_id.in_(achievement_ids))
        )
    ).all()
    grouped: dict[uuid.UUID, list[tuple[bool, str, EvidenceItem]]] = {}
    for link, item in rows:
        grouped.setdefault(link.achievement_id, []).append(
            (link.role != "primary", str(item.id), item)
        )
    return {key: [item for *_, item in sorted(value)] for key, value in grouped.items()}


async def _drill_down(
    session: AsyncSession, item_ids: list[uuid.UUID], vector: list[float] | None
) -> list[tuple[EvidenceChunk, uuid.UUID]]:
    """Top chunks containing the items, with the first of the given items each contains."""
    order = (
        EvidenceChunk.embedding.cosine_distance(vector)
        if vector is not None
        else EvidenceChunk.time_end.desc()
    )
    rows = (
        await session.execute(
            select(EvidenceChunk, EvidenceChunkItem.item_id)
            .join(EvidenceChunkItem, EvidenceChunkItem.chunk_id == EvidenceChunk.id)
            .where(EvidenceChunkItem.item_id.in_(item_ids))
            .order_by(order.nulls_last() if vector is not None else order, EvidenceChunk.id)
        )
    ).all()
    seen: set[uuid.UUID] = set()
    chunks: list[tuple[EvidenceChunk, uuid.UUID]] = []
    for chunk, item_id in rows:
        if chunk.id in seen:
            continue
        seen.add(chunk.id)
        chunks.append((chunk, item_id))
        if len(chunks) == CHUNKS_PER_ACHIEVEMENT:
            break
    return chunks


def _evidence_blocks(
    achievement: Achievement,
    items: list[EvidenceItem],
    chunks: list[tuple[EvidenceChunk, uuid.UUID]],
    counter: int,
) -> list[ContextBlock]:
    extra: dict[uuid.UUID, list[EvidenceChunk]] = {}
    for chunk, item_id in chunks:
        extra.setdefault(item_id, []).append(chunk)
    blocks: list[ContextBlock] = []
    for item in items[:ITEMS_PER_ACHIEVEMENT]:
        counter += 1
        snippet = _snippet(item, ITEM_CHARS)
        texts = [snippet]
        private = item.is_private
        for chunk in extra.get(item.id, []):
            if chunk.text.strip() == item.body.strip():
                continue
            texts.append("Context from the same work: " + redact(chunk.text).text[:CHUNK_CHARS])
            private = private or chunk.contains_private
        blocks.append(
            ContextBlock(
                marker=f"E{counter}",
                kind="evidence",
                text=f"{item.kind.value}: " + "\n".join(texts),
                corpus=tuple(texts),
                achievement_id=achievement.id,
                evidence_item_id=item.id,
                url=item.url,
                quote=snippet,
                private=private,
            )
        )
    return blocks


async def retrieve(
    session: AsyncSession, candidate_id: uuid.UUID, query: str, *, intro: bool = False
) -> Retrieval:
    """Approved achievements for `query`, each with its evidence and the best drill-down chunks."""
    settings = get_settings()
    vector = None if intro else await _query_vector(query)
    ranked = await _ranked(session, candidate_id, vector)
    result = Retrieval(approved=len(ranked))
    if not ranked:
        return result
    hits, result.best_score = select_hits(
        ranked, query, intro=intro, today=datetime.now(UTC).date(), settings=settings
    )
    if not hits:
        return result
    linked = await _linked_items(session, [achievement.id for achievement, _ in hits])
    evidence_counter = 0
    for number, (achievement, _) in enumerate(hits, start=1):
        items = linked.get(achievement.id, [])
        chunks = (
            []
            if intro or not items
            else await _drill_down(
                session, [item.id for item in items[:ITEMS_PER_ACHIEVEMENT]], vector
            )
        )
        evidence = _evidence_blocks(achievement, items, chunks, evidence_counter)
        evidence_counter += len(evidence)
        text = _achievement_text(achievement)
        result.achievement_ids.append(achievement.id)
        result.blocks.append(
            ContextBlock(
                marker=f"A{number}",
                kind="achievement",
                text=text,
                corpus=(text, *(part for block in evidence for part in block.corpus)),
                skills=tuple(achievement.skills),
                achievement_id=achievement.id,
                private=achievement.derived_from_private,
            )
        )
        result.blocks.extend(evidence)
    return result
