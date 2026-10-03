import hashlib
import logging
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace

from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.llm import LLMError, LLMTask, parse_structured
from app.core.config import get_settings
from app.models import Achievement, AchievementEvidence, EvidenceItem
from app.schemas.resume_document import Bullet, JDAnalysis
from app.schemas.resume_writing import MAX_BULLETS_PER_CALL, BulletBatch, Verdicts
from app.services.llm_cache import cached_parse_structured
from app.services.prompts.bullet import (
    BULLET_PROMPT_VERSION,
    JUDGE_PROMPT_VERSION,
    JUDGE_SYSTEM,
    WRITER_SYSTEM,
    render_items,
    render_judging,
)
from app.services.redaction import redact
from app.services.resume_terms import AllowedTerm, allowed_terms
from app.services.resume_verify import (
    Source,
    build_source,
    check_claims,
    lint_bullet,
    metric_ids_used,
    unconfirmed_figures,
)

logger = logging.getLogger(__name__)

SNIPPET_CHARS = 500
MAX_SNIPPETS = 4
JUDGE_UNAVAILABLE = "the claim check was unavailable, so this bullet needs your review"
NO_BULLET = "the writer returned no bullet for this item"


@dataclass(frozen=True)
class Snippet:
    label: str
    item_id: uuid.UUID
    line: str


@dataclass(frozen=True)
class BlockSpec:
    block_id: str
    header: str
    current: bool


@dataclass(frozen=True)
class WriteItem:
    key: str
    achievement_id: uuid.UUID
    facts: Mapping[str, object]
    metrics_raw: tuple[Mapping[str, object], ...]
    snippets: tuple[Snippet, ...]
    allowed: tuple[AllowedTerm, ...]
    disallowed: tuple[str, ...]
    source: Source
    priority: float
    from_private: bool
    instruction: str | None = None
    previous: str | None = None
    violations: tuple[str, ...] = ()

    @property
    def evidence_lines(self) -> list[str]:
        return [snippet.line for snippet in self.snippets]

    @property
    def payload(self) -> dict[str, object]:
        return {
            **self.facts,
            "key": self.key,
            "allowed_terms": [term.wording for term in self.allowed],
            "forbidden_terms": list(self.disallowed),
            "instruction": self.instruction,
            "previous": self.previous,
            "violations": list(self.violations),
        }


@dataclass(frozen=True)
class WrittenItem:
    item: WriteItem
    bullet: Bullet | None
    rejected_reason: str | None = None


@dataclass
class _Attempt:
    text: str | None = None
    violations: list[str] = field(default_factory=list[str])
    rejected: str | None = None
    cited: list[str] = field(default_factory=list[str])


def bullet_id(block_id: str, key: object) -> str:
    return hashlib.sha1(f"{block_id}|{key}".encode(), usedforsecurity=False).hexdigest()[:12]


def order_links(
    links: Sequence[tuple[AchievementEvidence, EvidenceItem]],
) -> list[tuple[AchievementEvidence, EvidenceItem]]:
    return sorted(links, key=lambda pair: (pair[0].role != "primary", str(pair[1].id)))


def _link_text(link: AchievementEvidence, item: EvidenceItem) -> str:
    return " ".join(f"{item.title or ''} {item.body} {link.quote or ''}".split())


def achievement_source(
    achievement: Achievement, ordered: Sequence[tuple[AchievementEvidence, EvidenceItem]]
) -> Source:
    """The text, tools, numbers and years a bullet about this achievement may rely on."""
    star = (achievement.situation, achievement.task, achievement.action, achievement.result)
    parts = [achievement.title, *(value for value in star if value)]
    for metric in achievement.metrics:
        parts += [str(metric.get("text") or ""), str(metric.get("source_quote") or "")]
    parts += [_link_text(link, item) for link, item in ordered]
    return build_source(parts, achievement.skills, _years(achievement, ordered))


def _years(
    achievement: Achievement, links: Sequence[tuple[AchievementEvidence, EvidenceItem]]
) -> set[int]:
    years = {d.year for d in (achievement.time_start, achievement.time_end) if d is not None}
    years |= {item.occurred_at.year for _, item in links if item.occurred_at is not None}
    return years


def build_item(
    key: str,
    achievement: Achievement,
    links: Sequence[tuple[AchievementEvidence, EvidenceItem]],
    jd: JDAnalysis | None,
    priority: float,
) -> WriteItem:
    """Everything the writer, the verifier and the judge need for one achievement."""
    redacting = get_settings().evidence_redaction_enabled
    ordered = sorted(links, key=lambda pair: (pair[0].role != "primary", str(pair[1].id)))
    snippets: list[Snippet] = []
    parts = [achievement.title]
    parts += [
        value
        for value in (
            achievement.situation,
            achievement.task,
            achievement.action,
            achievement.result,
        )
        if value
    ]
    for metric in achievement.metrics:
        parts += [str(metric.get("text") or ""), str(metric.get("source_quote") or "")]
    for link, item in ordered:
        text = " ".join(f"{item.title or ''} {item.body} {link.quote or ''}".split())
        parts.append(text)
        if len(snippets) < MAX_SNIPPETS:
            label = f"E{len(snippets) + 1}"
            body = f"{label}: [{item.kind.value}] {text[:SNIPPET_CHARS]}"
            snippets.append(Snippet(label, item.id, redact(body).text if redacting else body))
    source = build_source(parts, achievement.skills, _years(achievement, ordered))
    allowed, disallowed = allowed_terms(jd, achievement.skills, source.corpus)
    metrics = [
        {"id": str(metric.get("id") or f"m{index}"), "text": str(metric.get("text") or "")}
        for index, metric in enumerate(achievement.metrics)
        if metric.get("verified") in ("evidence", "user")
    ]
    facts: dict[str, object] = {
        "title": achievement.title,
        "situation": achievement.situation,
        "task": achievement.task,
        "action": achievement.action,
        "result": achievement.result,
        "confirmed_metrics": metrics,
    }
    return WriteItem(
        key=key,
        achievement_id=achievement.id,
        facts=facts,
        metrics_raw=tuple(achievement.metrics),
        snippets=tuple(snippets),
        allowed=tuple(allowed),
        disallowed=tuple(disallowed),
        source=source,
        priority=priority,
        from_private=achievement.derived_from_private or any(i.is_private for _, i in ordered),
    )


def evaluate_text(item: WriteItem, text: str, *, current: bool) -> list[str]:
    """Deterministic checks for one drafted bullet."""
    return [
        *lint_bullet(text, current=current, evidence_corpus=item.source.corpus),
        *check_claims(text, item.source, item.disallowed),
        *unconfirmed_figures(text, item.metrics_raw),
    ]


async def _generate(
    session: AsyncSession, block: BlockSpec, items: Sequence[WriteItem]
) -> BulletBatch:
    pairs = [(item.payload, item.evidence_lines) for item in items]
    prompt = render_items(block.header, current=block.current, items=pairs)
    result = await cached_parse_structured(
        session,
        task=LLMTask.write,
        prompt_version=BULLET_PROMPT_VERSION,
        key_parts={"header": block.header, "current": block.current, "items": pairs},
        schema=BulletBatch,
        call=lambda: parse_structured(
            prompt,
            schema=BulletBatch,
            system=WRITER_SYSTEM,
            temperature=0.0,
            task=LLMTask.write,
        ),
    )
    return result.data


def _judge_lines(item: WriteItem) -> list[str]:
    facts = [
        f"{name}: {value}"
        for name in ("title", "situation", "task", "action", "result")
        if (value := item.facts.get(name))
    ]
    return [*facts, *item.evidence_lines]


async def _judge(
    session: AsyncSession, claims: Sequence[tuple[WriteItem, str]]
) -> dict[str, tuple[bool, str | None]] | None:
    rendered = [(item.key, text, _judge_lines(item)) for item, text in claims]
    try:
        result = await cached_parse_structured(
            session,
            task=LLMTask.judge,
            prompt_version=JUDGE_PROMPT_VERSION,
            key_parts=rendered,
            schema=Verdicts,
            call=lambda: parse_structured(
                render_judging(rendered),
                schema=Verdicts,
                system=JUDGE_SYSTEM,
                temperature=0.0,
                task=LLMTask.judge,
            ),
        )
    except LLMError:
        logger.warning("resume.judge unavailable")
        return None
    return {verdict.key: (verdict.entailed, verdict.reason) for verdict in result.data.verdicts}


async def _attempt(
    session: AsyncSession, block: BlockSpec, items: Sequence[WriteItem]
) -> dict[str, _Attempt]:
    batch = await _generate(session, block, items)
    drafts = {draft.key: draft for draft in batch.bullets}
    attempts: dict[str, _Attempt] = {}
    judged: list[tuple[WriteItem, str]] = []
    for item in items:
        draft = drafts.get(item.key)
        text = " ".join(draft.text.split()) if draft else ""
        if draft is None or (not text and not draft.unsupported_reason):
            attempts[item.key] = _Attempt(violations=[NO_BULLET])
        elif not text:
            attempts[item.key] = _Attempt(rejected=draft.unsupported_reason)
        else:
            violations = evaluate_text(item, text, current=block.current)
            attempts[item.key] = _Attempt(text, violations, cited=draft.evidence_ids)
            judged.append((item, text))
    verdicts = await _judge(session, judged) if judged else {}
    for item, _ in judged:
        attempt = attempts[item.key]
        if verdicts is None:
            attempt.violations.append(JUDGE_UNAVAILABLE)
        elif (verdict := verdicts.get(item.key)) is not None and not verdict[0]:
            reason = verdict[1] or "a claim is not supported"
            attempt.violations.append(f"not supported by the evidence: {reason}")
    return attempts


def _fixable(attempt: _Attempt) -> bool:
    return attempt.rejected is None and any(v != JUDGE_UNAVAILABLE for v in attempt.violations)


def _to_written(block: BlockSpec, item: WriteItem, attempt: _Attempt) -> WrittenItem:
    if attempt.rejected is not None:
        return WrittenItem(item, None, attempt.rejected)
    if attempt.text is None:
        return WrittenItem(item, None, NO_BULLET)
    by_label = {snippet.label: snippet.item_id for snippet in item.snippets}
    cited = [by_label[label] for label in dict.fromkeys(attempt.cited) if label in by_label]
    bullet = Bullet(
        id=bullet_id(block.block_id, item.achievement_id),
        text=attempt.text,
        achievement_id=item.achievement_id,
        evidence_ids=cited or [snippet.item_id for snippet in item.snippets],
        metric_ids=metric_ids_used(attempt.text, item.metrics_raw),
        from_private=item.from_private,
        score=round(item.priority, 4),
        origin="generated",
        check="needs_review" if attempt.violations else "passed",
        flags=list(attempt.violations),
    )
    return WrittenItem(item, bullet)


async def write_block(
    session: AsyncSession, block: BlockSpec, items: Sequence[WriteItem]
) -> list[WrittenItem]:
    """Write, verify and (once) repair the bullets of one employer or project block.

    A bullet that still fails after the one regeneration is kept with `check="needs_review"`
    and its violations in `flags`. An item the writer declines is returned as rejected.
    """
    written: list[WrittenItem] = []
    for start in range(0, len(items), MAX_BULLETS_PER_CALL):
        chunk = items[start : start + MAX_BULLETS_PER_CALL]
        attempts = await _attempt(session, block, chunk)
        failing = [item for item in chunk if _fixable(attempts[item.key])]
        if failing:
            redo = [
                replace(
                    item,
                    previous=attempts[item.key].text,
                    violations=tuple(attempts[item.key].violations),
                )
                for item in failing
            ]
            second = await _attempt(session, block, redo)
            for item in failing:
                attempts[item.key] = second[item.key]
        written.extend(_to_written(block, item, attempts[item.key]) for item in chunk)
    return written
