import asyncio
import hashlib
import json
import logging
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, cast

from fastapi import BackgroundTasks
from sqlalchemy import Select, func, select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.llm import (
    CostEstimate,
    LLMError,
    LLMTask,
    StructuredResult,
    UsageMeter,
    estimate_cost,
    estimate_structured_cost,
    is_llm_configured,
    model_for,
    parse_structured,
    usage_meter,
)
from app.core.config import get_settings
from app.core.db import session_factory
from app.core.errors import (
    DuplicateExtractionError,
    EstimateMismatchError,
    ExtractionRunNotFoundError,
    LLMNotConfiguredError,
    NothingToExtractError,
)
from app.core.pagination import DEFAULT_PAGE, Pagination
from app.models import (
    Achievement,
    AchievementEvidence,
    AchievementExtractionRun,
    AchievementRevision,
    AchievementRevisionSource,
    AchievementStatus,
    EvidenceChunk,
    EvidenceChunkItem,
    EvidenceItem,
    EvidenceScope,
    LLMOutputCache,
    SyncStatus,
)
from app.schemas.achievement import (
    ExtractionBatch,
    ExtractionEstimateResponse,
    ExtractionRunResponse,
    ExtractionStartResponse,
)
from app.schemas.cost import CostEstimateResponse
from app.services.achievement_validation import Rejection, ValidatedAchievement, validate
from app.services.embedding import embed_texts
from app.services.employer_mapping import ProfileFacts, load_profile_facts, suggest_employer
from app.services.evidence_items import candidate_id_or_none
from app.services.evidence_pipeline.dedupe import digest
from app.services.llm_cache import cache_key, cached_parse_structured
from app.services.prompts.achievement import ACHIEVEMENT_PROMPT_VERSION, SYSTEM_PROMPT, build_prompt
from app.services.redaction import redact
from app.services.resume_service import get_or_create_candidate
from app.services.skill_canon import canonicalize

if TYPE_CHECKING:
    from sqlalchemy.engine import CursorResult

logger = logging.getLogger(__name__)

EXPECTED_COMPLETION_TOKENS = 450
EXPECTED_EMBED_TOKENS = 200
ACTIVE_STATUSES = (SyncStatus.pending, SyncStatus.running)
ABANDONED_ERROR = "run abandoned - in-flight lock released"
QUOTE_MAX = 500
LABEL_TITLE_MAX = 80
_EPOCH = datetime.min.replace(tzinfo=UTC)


@dataclass(frozen=True)
class _Label:
    label: str
    item_id: uuid.UUID
    is_private: bool
    line: str


ALWAYS_EXTRACTED = frozenset({"note", "resume_entry"})


@dataclass(frozen=True)
class _Unit:
    chunk_id: uuid.UUID
    kind: str
    project_key: str | None
    title: str | None
    text: str
    content_hash: str
    extracted_hash: str | None
    contains_private: bool
    time_start: datetime | None
    time_end: datetime | None
    labels: tuple[_Label, ...]
    scope_employer: dict[str, object] | None

    @property
    def key(self) -> str:
        return digest(self.content_hash, ACHIEVEMENT_PROMPT_VERSION)

    @property
    def prompt(self) -> str:
        lines = [label.line for label in self.labels]
        return build_prompt(self.project_key, self.title, self.text, lines)

    @property
    def cache_parts(self) -> dict[str, object]:
        return {
            "project": self.project_key,
            "text": self.text,
            "labels": [label.line for label in self.labels],
        }

    @property
    def cache_key(self) -> str:
        return cache_key(
            LLMTask.extract,
            model_for(LLMTask.extract),
            ACHIEVEMENT_PROMPT_VERSION,
            self.cache_parts,
        )


def _label_line(index: int, item: EvidenceItem, *, redaction_enabled: bool) -> str:
    when = f" ({item.occurred_at:%Y-%m-%d})" if item.occurred_at else ""
    summary = " ".join((item.title or item.body).split())[:LABEL_TITLE_MAX]
    line = f"E{index}: [{item.kind.value}] {summary}{when}"
    return redact(line).text if redaction_enabled else line


async def _load_units(session: AsyncSession, candidate_id: uuid.UUID) -> list[_Unit]:
    redaction_enabled = get_settings().evidence_redaction_enabled
    chunks = (
        (
            await session.execute(
                select(EvidenceChunk)
                .where(EvidenceChunk.candidate_id == candidate_id)
                .order_by(EvidenceChunk.project_key, EvidenceChunk.time_start, EvidenceChunk.id)
            )
        )
        .scalars()
        .all()
    )
    rows = (
        await session.execute(
            select(EvidenceChunkItem.chunk_id, EvidenceItem, EvidenceScope.employer_ref)
            .join(EvidenceItem, EvidenceItem.id == EvidenceChunkItem.item_id)
            .outerjoin(EvidenceScope, EvidenceScope.id == EvidenceItem.scope_id)
            .where(EvidenceItem.candidate_id == candidate_id)
        )
    ).all()
    members: dict[uuid.UUID, list[tuple[EvidenceItem, dict[str, object] | None]]] = {}
    for row in rows:
        members.setdefault(row[0], []).append((row[1], row[2]))
    units: list[_Unit] = []
    for chunk in chunks:
        ordered = sorted(
            members.get(chunk.id, []),
            key=lambda pair: (pair[0].occurred_at or _EPOCH, pair[0].external_id),
        )
        labels = tuple(
            _Label(
                label=f"E{index}",
                item_id=item.id,
                is_private=item.is_private,
                line=_label_line(index, item, redaction_enabled=redaction_enabled),
            )
            for index, (item, _) in enumerate(ordered, start=1)
        )
        employer = next((ref for _, ref in ordered if ref), None)
        units.append(
            _Unit(
                chunk_id=chunk.id,
                kind=chunk.kind,
                project_key=chunk.project_key,
                title=chunk.title,
                text=chunk.text,
                content_hash=chunk.content_hash,
                extracted_hash=chunk.extracted_hash,
                contains_private=chunk.contains_private,
                time_start=chunk.time_start,
                time_end=chunk.time_end,
                labels=labels,
                scope_employer={**employer, "source": "scope"} if employer else None,
            )
        )
    return units


def _split_pending(units: list[_Unit]) -> tuple[list[_Unit], int]:
    """(chunks to extract, how many outstanding chunks are too short to be worth a call).

    Your own notes and resume lines are never skipped. A short chunk is not marked extracted, so
    lowering `EXTRACTION_MIN_CHUNK_CHARS` brings it back.
    """
    minimum = get_settings().extraction_min_chunk_chars
    outstanding = [unit for unit in units if unit.extracted_hash != unit.key]
    worth = [
        unit for unit in outstanding if unit.kind in ALWAYS_EXTRACTED or len(unit.text) >= minimum
    ]
    return worth, len(outstanding) - len(worth)


def _sum_estimates(estimates: list[CostEstimate], model: str) -> CostEstimate:
    if not estimates:
        return estimate_cost(model, 0, 0)
    usd = None if any(e.usd is None for e in estimates) else sum(e.usd or 0.0 for e in estimates)
    basis = estimates[0].basis if usd is not None else "unavailable"
    return CostEstimate(
        prompt_tokens=sum(e.prompt_tokens for e in estimates),
        completion_tokens=sum(e.completion_tokens for e in estimates),
        usd=usd,
        basis=basis,
    )


def _estimate_id(pending: list[_Unit]) -> str:
    payload = json.dumps(
        [
            ACHIEVEMENT_PROMPT_VERSION,
            model_for(LLMTask.extract),
            sorted((str(u.chunk_id), u.content_hash, u.extracted_hash or "") for u in pending),
        ],
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode()).hexdigest()


async def estimate(session: AsyncSession) -> ExtractionEstimateResponse:
    """What an extraction would cost, computed from the real chunk prompts (nothing is sent)."""
    candidate_id = await candidate_id_or_none(session)
    units = [] if candidate_id is None else await _load_units(session, candidate_id)
    pending, skipped = _split_pending(units)
    keys = [unit.cache_key for unit in pending]
    cached: set[str] = (
        set(
            (
                await session.execute(
                    select(LLMOutputCache.key).where(LLMOutputCache.key.in_(keys))
                )
            ).scalars()
        )
        if keys
        else set()
    )
    to_call = [unit for unit in pending if unit.cache_key not in cached]
    settings = get_settings()
    model = model_for(LLMTask.extract)
    llm = _sum_estimates(
        [
            estimate_structured_cost(
                unit.prompt,
                schema=ExtractionBatch,
                system=SYSTEM_PROMPT,
                expected_completion_tokens=EXPECTED_COMPLETION_TOKENS,
                task=LLMTask.extract,
            )
            for unit in to_call
        ],
        model,
    )
    embedding = estimate_cost(settings.embedding_model, EXPECTED_EMBED_TOKENS * len(pending))
    private = sum(1 for unit in pending if unit.contains_private)
    return ExtractionEstimateResponse(
        estimate_id=_estimate_id(pending),
        chunks_total=len(units),
        chunks_up_to_date=len(units) - len(pending) - skipped,
        chunks_skipped_short=skipped,
        chunks_cached=len(pending) - len(to_call),
        chunks_to_extract=len(to_call),
        llm_cost=CostEstimateResponse.from_estimate(llm),
        embedding_cost=CostEstimateResponse.from_estimate(embedding),
        total_usd=None if llm.usd is None or embedding.usd is None else llm.usd + embedding.usd,
        private_chunks=private,
        private_share=round(private / len(pending), 4) if pending else 0.0,
    )


def _select_active_run(candidate_id: uuid.UUID) -> Select[tuple[AchievementExtractionRun]]:
    return (
        select(AchievementExtractionRun)
        .where(
            AchievementExtractionRun.candidate_id == candidate_id,
            AchievementExtractionRun.status.in_(ACTIVE_STATUSES),
        )
        .order_by(AchievementExtractionRun.updated_at.desc())
        .limit(1)
    )


async def _sweep_stale_runs(session: AsyncSession) -> int:
    cutoff = datetime.now(UTC) - timedelta(minutes=get_settings().max_run_age_minutes)
    result = cast(
        "CursorResult[tuple[()]]",
        await session.execute(
            update(AchievementExtractionRun)
            .where(
                AchievementExtractionRun.status.in_(ACTIVE_STATUSES),
                AchievementExtractionRun.updated_at < cutoff,
            )
            .values(status=SyncStatus.failed, error=ABANDONED_ERROR)
        ),
    )
    if result.rowcount:
        logger.info("achievements.sweep swept=%d", result.rowcount)
    return result.rowcount


async def _raise_if_duplicate_run(session: AsyncSession, candidate_id: uuid.UUID) -> None:
    active = (await session.execute(_select_active_run(candidate_id))).scalar_one_or_none()
    if active is not None:
        logger.warning("achievements.duplicate active_run=%s", active.id)
        raise DuplicateExtractionError(active_run_id=active.id)


async def start_extraction(
    session: AsyncSession, background_tasks: BackgroundTasks, confirmed_estimate_id: str
) -> ExtractionStartResponse:
    if not is_llm_configured():
        raise LLMNotConfiguredError
    candidate = await get_or_create_candidate(session)
    current = await estimate(session)
    if current.chunks_to_extract + current.chunks_cached == 0:
        raise NothingToExtractError
    if current.estimate_id != confirmed_estimate_id:
        raise EstimateMismatchError
    await _sweep_stale_runs(session)
    await _raise_if_duplicate_run(session, candidate.id)
    run = AchievementExtractionRun(
        candidate_id=candidate.id,
        status=SyncStatus.pending,
        estimate=current.model_dump(mode="json"),
        progress={"total": current.chunks_to_extract + current.chunks_cached},
    )
    try:
        async with session.begin_nested():
            session.add(run)
            await session.flush()
    except IntegrityError as exc:
        raced = (await session.execute(_select_active_run(candidate.id))).scalar_one_or_none()
        logger.warning("achievements.duplicate raced the active-run index")
        raise DuplicateExtractionError(active_run_id=raced.id if raced else None) from exc
    background_tasks.add_task(run_extraction, run.id)
    logger.info("achievements.start run_id=%s", run.id)
    return ExtractionStartResponse(run_id=run.id, status=run.status.value)


@dataclass
class _Counters:
    total: int = 0
    done: int = 0
    failed: int = 0
    cached: int = 0
    achievements: int = 0
    rejected: int = 0
    flagged: int = 0
    embed_failed: int = 0

    def as_progress(self) -> dict[str, object]:
        return dict(self.__dict__)


def _embed_text(item: ValidatedAchievement, skills: list[str]) -> str:
    parts = [item.title, item.situation, item.task, item.action, item.result or ""]
    if skills:
        parts.append(f"Skills: {', '.join(skills)}")
    return "\n".join(part for part in parts if part)


def _quote(item: ValidatedAchievement) -> str | None:
    if item.result_quote:
        return item.result_quote[:QUOTE_MAX]
    for metric in item.metrics:
        if metric.get("verified") == "evidence":
            return str(metric["source_quote"])[:QUOTE_MAX]
    return None


def _build_rows(
    candidate_id: uuid.UUID,
    unit: _Unit,
    item: ValidatedAchievement,
    context: ProfileFacts,
) -> tuple[Achievement, list[AchievementEvidence], list[str]]:
    by_label = {label.label: label for label in unit.labels}
    cited = [by_label[label] for label in item.evidence_labels]
    skills = canonicalize(item.skills, context.skills)
    start = item.time_start or (unit.time_start.date() if unit.time_start else None)
    end = item.time_end or (unit.time_end.date() if unit.time_end else None)
    employer = unit.scope_employer or suggest_employer(unit.project_key, start, end, context.groups)
    metrics = [
        {
            **metric,
            "evidence_ids": [
                str(by_label[label].item_id) for label in cast("list[str]", metric["evidence_ids"])
            ],
        }
        for metric in item.metrics
    ]
    achievement = Achievement(
        candidate_id=candidate_id,
        title=item.title,
        situation=item.situation,
        task=item.task,
        action=item.action,
        result=item.result,
        metrics=metrics,
        skills=skills,
        impact_type=item.impact_type,
        difficulty=item.difficulty,
        project_key=unit.project_key,
        employer_ref=employer,
        time_start=start,
        time_end=end,
        prompt_version=ACHIEVEMENT_PROMPT_VERSION,
        source_chunk_hash=unit.content_hash,
        derived_from_private=any(label.is_private for label in cited),
        review_flags=item.review_flags,
    )
    quote = _quote(item)
    links = [
        AchievementEvidence(
            item_id=label.item_id,
            role="primary" if index == 0 else "supporting",
            quote=quote if index == 0 else None,
        )
        for index, label in enumerate(cited)
    ]
    return achievement, links, skills


_Built = tuple[Achievement, list[AchievementEvidence], list[str], ValidatedAchievement]


@dataclass
class _UnitResult:
    failed: bool = False
    cached: bool = False
    created: int = 0
    rejected: int = 0
    flagged: int = 0
    embed_failed: int = 0
    skipped: bool = False


async def _existing_for_chunk(
    session: AsyncSession, candidate_id: uuid.UUID, unit: _Unit
) -> list[Achievement]:
    return list(
        (
            await session.execute(
                select(Achievement).where(
                    Achievement.candidate_id == candidate_id,
                    Achievement.source_chunk_hash == unit.content_hash,
                    Achievement.status != AchievementStatus.archived,
                )
            )
        )
        .scalars()
        .all()
    )


def _supersede(session: AsyncSession, existing: list[Achievement]) -> None:
    """Drafts from an older prompt version give way to the new extraction; approved stay."""
    for row in existing:
        if row.status is AchievementStatus.draft:
            row.status = AchievementStatus.archived
            session.add(
                AchievementRevision(
                    achievement_id=row.id,
                    source=AchievementRevisionSource.status_change,
                    diff={"status": ["draft", "archived"], "reason": "superseded_by_new_prompt"},
                )
            )


async def _mark_extracted(session: AsyncSession, unit: _Unit) -> None:
    chunk = await session.get(EvidenceChunk, unit.chunk_id)
    if chunk is not None:
        chunk.extracted_hash = unit.key


async def _process_unit(candidate_id: uuid.UUID, unit: _Unit, context: ProfileFacts) -> _UnitResult:
    result = _UnitResult()
    called = False

    async def call() -> StructuredResult[ExtractionBatch]:
        nonlocal called
        called = True
        return await parse_structured(
            unit.prompt,
            schema=ExtractionBatch,
            system=SYSTEM_PROMPT,
            temperature=0.0,
            task=LLMTask.extract,
        )

    async with session_factory() as session:
        existing = await _existing_for_chunk(session, candidate_id, unit)
        if any(row.prompt_version == ACHIEVEMENT_PROMPT_VERSION for row in existing):
            await _mark_extracted(session, unit)
            await session.commit()
            result.skipped = True
            return result
        try:
            parsed = await cached_parse_structured(
                session,
                task=LLMTask.extract,
                prompt_version=ACHIEVEMENT_PROMPT_VERSION,
                key_parts=unit.cache_parts,
                schema=ExtractionBatch,
                call=call,
            )
        except LLMError:
            await session.rollback()
            result.failed = True
            return result
        result.cached = not called
        _supersede(session, existing)
        labels = {label.label for label in unit.labels}
        built: list[
            tuple[Achievement, list[AchievementEvidence], list[str], ValidatedAchievement]
        ] = []
        for extracted in parsed.data.achievements:
            outcome = validate(extracted, chunk_text=unit.text, labels=labels)
            if isinstance(outcome, Rejection):
                result.rejected += 1
                continue
            achievement, links, skills = _build_rows(candidate_id, unit, outcome, context)
            result.flagged += 1 if outcome.review_flags else 0
            built.append((achievement, links, skills, outcome))
        for achievement, links, _, _ in built:
            session.add(achievement)
            await session.flush()
            for link in links:
                link.achievement_id = achievement.id
                session.add(link)
            session.add(
                AchievementRevision(
                    achievement_id=achievement.id,
                    source=AchievementRevisionSource.ai_extraction,
                    diff={
                        "created": {
                            "title": achievement.title,
                            "prompt_version": ACHIEVEMENT_PROMPT_VERSION,
                            "source_chunk_hash": unit.content_hash,
                        }
                    },
                )
            )
        result.created = len(built)
        result.embed_failed = await _embed_drafts(built)
        await _mark_extracted(session, unit)
        await session.commit()
    return result


async def _embed_drafts(built: list[_Built]) -> int:
    if not built:
        return 0
    try:
        vectors = await embed_texts([_embed_text(item, skills) for _, _, skills, item in built])
    except LLMError as exc:
        logger.warning("achievements.embedding failed error=%s drafts=%d", exc, len(built))
        return len(built)
    for (achievement, _, _, _), vector in zip(built, vectors, strict=True):
        achievement.embedding = vector
    return 0


async def _record_progress(run_id: uuid.UUID, counters: _Counters, meter: UsageMeter) -> None:
    async with session_factory() as session:
        run = await session.get(AchievementExtractionRun, run_id)
        if run is None:
            return
        run.progress = counters.as_progress()
        run.usage = {
            "prompt_tokens": meter.prompt_tokens,
            "completion_tokens": meter.completion_tokens,
            "cost_usd": meter.cost_usd,
            "cache_hits": meter.cache_hits,
            "cache_misses": meter.cache_misses,
        }
        await session.commit()


async def _reconcile_stale(session: AsyncSession, candidate_id: uuid.UUID) -> None:
    """Archive drafts whose source chunk vanished; flag approved ones whose evidence changed."""
    current = set(
        (
            await session.execute(
                select(EvidenceChunk.content_hash).where(EvidenceChunk.candidate_id == candidate_id)
            )
        ).scalars()
    )
    rows = (
        (
            await session.execute(
                select(Achievement).where(
                    Achievement.candidate_id == candidate_id,
                    Achievement.source_chunk_hash.is_not(None),
                    Achievement.status.in_((AchievementStatus.draft, AchievementStatus.approved)),
                )
            )
        )
        .scalars()
        .all()
    )
    now = datetime.now(UTC)
    for achievement in rows:
        if achievement.source_chunk_hash in current:
            continue
        if achievement.status is AchievementStatus.draft:
            achievement.status = AchievementStatus.archived
            session.add(
                AchievementRevision(
                    achievement_id=achievement.id,
                    source=AchievementRevisionSource.status_change,
                    diff={"status": ["draft", "archived"], "reason": "source_chunk_changed"},
                )
            )
        elif achievement.evidence_stale_at is None:
            achievement.evidence_stale_at = now


async def _extract_concurrently(
    run_id: uuid.UUID,
    candidate_id: uuid.UUID,
    pending: list[_Unit],
    context: ProfileFacts,
    counters: _Counters,
    meter: UsageMeter,
) -> None:
    """Run chunks a few at a time. Each chunk owns its session; the counters, the run row and the
    meter are only touched on the event loop, and progress is written under a lock."""
    gate = asyncio.Semaphore(get_settings().extraction_concurrency)
    progress = asyncio.Lock()

    async def work(unit: _Unit) -> None:
        async with gate:
            outcome = await _process_unit(candidate_id, unit, context)
        async with progress:
            counters.done += 1
            counters.failed += 1 if outcome.failed else 0
            counters.cached += 1 if outcome.cached else 0
            counters.achievements += outcome.created
            counters.rejected += outcome.rejected
            counters.flagged += outcome.flagged
            counters.embed_failed += outcome.embed_failed
            await _record_progress(run_id, counters, meter)

    async with asyncio.TaskGroup() as group:
        for unit in pending:
            group.create_task(work(unit))


async def run_extraction(run_id: uuid.UUID) -> None:
    started = time.monotonic()
    async with session_factory() as session:
        run = await session.get(AchievementExtractionRun, run_id)
        if run is None:
            logger.error("achievements.run run_id=%s missing", run_id)
            return
        run.status = SyncStatus.running
        await session.commit()
        candidate_id = run.candidate_id
        units = await _load_units(session, candidate_id)
        context = await load_profile_facts(session, candidate_id)
    pending, skipped = _split_pending(units)
    counters = _Counters(total=len(pending))
    with usage_meter() as meter:
        await _extract_concurrently(run_id, candidate_id, pending, context, counters, meter)
    status = await _finish(run_id, candidate_id, counters)
    logger.info(
        "achievements.done run_id=%s status=%s chunks=%d skipped_short=%d achievements=%d "
        "failed=%d duration_ms=%.0f",
        run_id,
        status.value,
        counters.total,
        skipped,
        counters.achievements,
        counters.failed,
        (time.monotonic() - started) * 1000,
    )


async def _finish(run_id: uuid.UUID, candidate_id: uuid.UUID, counters: _Counters) -> SyncStatus:
    async with session_factory() as session:
        run = await session.get(AchievementExtractionRun, run_id)
        if run is None:
            return SyncStatus.failed
        if counters.total and counters.failed == counters.total:
            status = SyncStatus.failed
            run.error = "every chunk failed - check the provider and retry"
        else:
            status = SyncStatus.succeeded
        try:
            if counters.failed == 0:
                await _reconcile_stale(session, candidate_id)
        except SQLAlchemyError as exc:
            logger.warning("achievements.reconcile failed error_type=%s", type(exc).__name__)
            await session.rollback()
            run = await session.get_one(AchievementExtractionRun, run_id)
        run.status = status
        run.progress = counters.as_progress()
        await session.commit()
        return status


def _run_response(run: AchievementExtractionRun) -> ExtractionRunResponse:
    return ExtractionRunResponse(
        id=run.id,
        status=run.status.value,
        estimate=run.estimate,
        progress=run.progress,
        usage=run.usage,
        error=run.error,
        created_at=run.created_at,
        updated_at=run.updated_at,
    )


async def get_run(session: AsyncSession, run_id: uuid.UUID) -> ExtractionRunResponse:
    candidate_id = await candidate_id_or_none(session)
    run = await session.get(AchievementExtractionRun, run_id)
    if run is None or candidate_id is None or run.candidate_id != candidate_id:
        raise ExtractionRunNotFoundError
    return _run_response(run)


async def count_runs(session: AsyncSession) -> int:
    candidate_id = await candidate_id_or_none(session)
    if candidate_id is None:
        return 0
    query = select(func.count()).where(AchievementExtractionRun.candidate_id == candidate_id)
    return (await session.execute(query)).scalar_one()


async def list_runs(
    session: AsyncSession, page: Pagination = DEFAULT_PAGE
) -> list[ExtractionRunResponse]:
    """Newest first, so the page can pick up a run that is still going after a reload."""
    candidate_id = await candidate_id_or_none(session)
    if candidate_id is None:
        return []
    rows = (
        (
            await session.execute(
                select(AchievementExtractionRun)
                .where(AchievementExtractionRun.candidate_id == candidate_id)
                .order_by(AchievementExtractionRun.created_at.desc())
                .limit(page.limit)
                .offset(page.offset)
            )
        )
        .scalars()
        .all()
    )
    return [_run_response(run) for run in rows]
