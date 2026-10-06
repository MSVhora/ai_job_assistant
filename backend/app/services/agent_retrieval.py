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
    EvidenceItemStatus,
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
HIGHLIGHTS = 4
USER_CHUNKS = 3
USER_CHUNK_KINDS = ("resume_entry", "note")
USER_CHUNK_MIN_COSINE = 0.55
CHUNKS_PER_ACHIEVEMENT = 2
ITEMS_PER_ACHIEVEMENT = 3
ITEM_CHARS = 500
CHUNK_CHARS = 900
QUOTE_CHARS = 240
LABEL_CHARS = 90
MIN_NAME_CHARS = 3
HIGHLIGHT_IMPACT_SHARE = 0.6
TRAILER = re.compile(
    r"^\s*(?:co-authored-by|signed-off-by|reviewed-by)\s*:.*$", re.IGNORECASE | re.MULTILINE
)
LINK = re.compile(r"\(?https?://\S+\)?")


@dataclass(frozen=True)
class ContextBlock:
    """One citable piece of context. `corpus` is what a sentence citing the marker may rest on."""

    marker: str
    kind: CitationKind
    text: str
    corpus: tuple[str, ...]
    label: str = ""
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


def clean_excerpt(text: str, limit: int = QUOTE_CHARS) -> str:
    """A readable excerpt for the UI: no commit trailers or bare links, whitespace collapsed."""
    cleaned = " ".join(LINK.sub(" ", TRAILER.sub(" ", text)).split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[:limit].rsplit(" ", 1)[0].rstrip(".,;:") + "…"


def short_label(text: str | None, fallback: str) -> str:
    first = clean_excerpt((text or "").split("\n", 1)[0], LABEL_CHARS)
    return first or fallback


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
    pattern = rf"(?<![A-Za-z0-9]){re.escape(name)}(?![A-Za-z0-9])"
    return re.search(pattern, question, re.IGNORECASE) is not None


def _company(achievement: Achievement) -> str | None:
    company = (achievement.employer_ref or {}).get("company")
    return company if isinstance(company, str) and company else None


def filter_by_mention(question: str, rows: list[Achievement]) -> list[Achievement]:
    """Narrow to the project or employer the question names; keep all when none matches."""
    matched = [
        achievement
        for achievement in rows
        if _mentions(question, (achievement.project_key or "").rsplit("/", 1)[-1] or None)
        or _mentions(question, _company(achievement))
    ]
    return matched or rows


def _achievement_text(achievement: Achievement, *, compact: bool = False) -> str:
    lines = [f"Title: {achievement.title}"]
    fields = (
        (("Result", achievement.result),)
        if compact
        else (
            ("Situation", achievement.situation),
            ("Task", achievement.task),
            ("Action", achievement.action),
            ("Result", achievement.result),
        )
    )
    lines.extend(f"{label}: {value}" for label, value in fields if value)
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
    if company := _company(achievement):
        lines.append(f"Employer: {company}")
    if achievement.time_start:
        end = achievement.time_end.isoformat() if achievement.time_end else "present"
        lines.append(f"Period: {achievement.time_start.isoformat()} to {end}")
    return redact("\n".join(lines)).text


def _item_text(item: EvidenceItem) -> str:
    """Title and body, without repeating the title when the body already starts with it."""
    title = (item.title or "").strip()
    return (
        item.body if not title or item.body.lstrip().startswith(title) else f"{title}\n{item.body}"
    )


def _snippet(item: EvidenceItem, limit: int) -> str:
    return redact(" ".join(_item_text(item).split())).text[:limit]


def _item_label(item: EvidenceItem) -> str:
    title = short_label(item.title or item.body, item.kind.value.replace("_", " "))
    if not item.project_key or title.startswith(item.project_key):
        return title
    return f"{item.project_key}: {title}"


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
    ranked: list[tuple[Achievement, float]], query: str, *, today: date, settings: Settings
) -> tuple[list[tuple[Achievement, float]], float]:
    """Achievements relevant to the question, and the best score seen (before the floor)."""
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


def select_highlights(
    ranked: list[tuple[Achievement, float]], exclude: set[uuid.UUID], *, today: date
) -> list[Achievement]:
    """The best approved achievement per employer or project, so broad questions have material."""
    best: dict[str, tuple[float, Achievement]] = {}
    for achievement, _ in ranked:
        if achievement.id in exclude:
            continue
        group = _company(achievement) or achievement.project_key or "other"
        score = HIGHLIGHT_IMPACT_SHARE * impact_score(achievement) + (
            1 - HIGHLIGHT_IMPACT_SHARE
        ) * recency_factor(achievement.time_end, achievement.time_start, today)
        if group not in best or score > best[group][0]:
            best[group] = (score, achievement)
    ordered = sorted(best.values(), key=lambda pair: (-pair[0], str(pair[1].id)))
    return [achievement for _, achievement in ordered[:HIGHLIGHTS]]


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
        EvidenceChunk.embedding.cosine_distance(vector).nulls_last()
        if vector is not None
        else EvidenceChunk.time_end.desc()
    )
    rows = (
        await session.execute(
            select(EvidenceChunk, EvidenceChunkItem.item_id)
            .join(EvidenceChunkItem, EvidenceChunkItem.chunk_id == EvidenceChunk.id)
            .where(EvidenceChunkItem.item_id.in_(item_ids))
            .order_by(order, EvidenceChunk.id)
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
        texts = [_snippet(item, ITEM_CHARS)]
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
                label=_item_label(item),
                achievement_id=achievement.id,
                evidence_item_id=item.id,
                url=item.url,
                quote=clean_excerpt(_item_text(item)),
                private=private,
            )
        )
    return blocks


async def _user_chunks(
    session: AsyncSession, candidate_id: uuid.UUID, vector: list[float], counter: int
) -> list[ContextBlock]:
    """Resume entries and notes the user wrote, close to the question, as direct evidence."""
    distance = EvidenceChunk.embedding.cosine_distance(vector)
    rows = (
        await session.execute(
            select(EvidenceChunk, EvidenceItem, distance.label("distance"))
            .join(EvidenceChunkItem, EvidenceChunkItem.chunk_id == EvidenceChunk.id)
            .join(EvidenceItem, EvidenceItem.id == EvidenceChunkItem.item_id)
            .where(
                EvidenceChunk.candidate_id == candidate_id,
                EvidenceChunk.kind.in_(USER_CHUNK_KINDS),
                EvidenceChunk.embedding.is_not(None),
                EvidenceItem.status == EvidenceItemStatus.kept,
            )
            .order_by(distance, EvidenceChunk.id)
            .limit(USER_CHUNKS * 3)
        )
    ).all()
    blocks: list[ContextBlock] = []
    seen: set[uuid.UUID] = set()
    for chunk, item, chunk_distance in rows:
        if chunk.id in seen or 1.0 - float(chunk_distance) < USER_CHUNK_MIN_COSINE:
            continue
        seen.add(chunk.id)
        counter += 1
        text = redact(chunk.text).text[:CHUNK_CHARS]
        blocks.append(
            ContextBlock(
                marker=f"E{counter}",
                kind="evidence",
                text=f"{item.kind.value}: {text}",
                corpus=(text,),
                label=short_label(chunk.title or item.title, item.kind.value.replace("_", " ")),
                evidence_item_id=item.id,
                url=item.url,
                quote=clean_excerpt(chunk.text),
                private=chunk.contains_private or item.is_private,
            )
        )
        if len(blocks) == USER_CHUNKS:
            break
    return blocks


async def retrieve(session: AsyncSession, candidate_id: uuid.UUID, query: str) -> Retrieval:
    """Context for any question: relevant achievements and evidence, highlights, user writing."""
    settings = get_settings()
    today = datetime.now(UTC).date()
    vector = await _query_vector(query)
    ranked = await _ranked(session, candidate_id, vector)
    result = Retrieval(approved=len(ranked))
    hits, result.best_score = select_hits(ranked, query, today=today, settings=settings)
    linked = await _linked_items(session, [a.id for a, _ in hits]) if hits else {}
    evidence_counter = 0
    for number, (achievement, _) in enumerate(hits, start=1):
        items = linked.get(achievement.id, [])
        chunks = (
            await _drill_down(session, [i.id for i in items[:ITEMS_PER_ACHIEVEMENT]], vector)
            if items
            else []
        )
        evidence = _evidence_blocks(achievement, items, chunks, evidence_counter)
        evidence_counter += len(evidence)
        text = _achievement_text(achievement)
        result.achievement_ids.append(achievement.id)
        result.blocks.append(_achievement_block(f"A{number}", achievement, text, evidence))
        result.blocks.extend(evidence)
    marker = len(hits)
    for achievement in select_highlights(ranked, set(result.achievement_ids), today=today):
        marker += 1
        text = _achievement_text(achievement, compact=True)
        result.blocks.append(_achievement_block(f"A{marker}", achievement, text, []))
    if vector is not None:
        result.blocks.extend(await _user_chunks(session, candidate_id, vector, evidence_counter))
    return result


def _achievement_block(
    marker: str, achievement: Achievement, text: str, evidence: list[ContextBlock]
) -> ContextBlock:
    return ContextBlock(
        marker=marker,
        kind="achievement",
        text=text,
        corpus=(text, *(part for block in evidence for part in block.corpus)),
        label=short_label(achievement.title, "Achievement"),
        quote=clean_excerpt(achievement.result or achievement.action or achievement.title),
        skills=tuple(achievement.skills),
        achievement_id=achievement.id,
        private=achievement.derived_from_private,
    )
