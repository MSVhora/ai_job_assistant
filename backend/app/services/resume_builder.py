import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.llm import LLMError, usage_meter
from app.core.config import Settings, get_settings
from app.core.errors import (
    AchievementNotFoundError,
    CannotFitError,
    InvalidResumeDocumentError,
    ResumeBlockNotFoundError,
)
from app.models import (
    Achievement,
    AchievementEvidence,
    AchievementStatus,
    EvidenceItem,
    EvidenceItemStatus,
    ResumeDocument,
)
from app.models import Candidate as CandidateRow
from app.schemas.resume_document import (
    Bullet,
    GapItem,
    Generation,
    GenerationUsage,
    JDAnalysis,
    Layout,
    OmittedRole,
    PoolEntry,
    ResumeContent,
    ResumeDocumentCreate,
    ResumeDocumentResponse,
    WorkEntry,
)
from app.services import resume_documents
from app.services.company_names import Merges
from app.services.embedding import embed_texts
from app.services.evidence_items import candidate_id_or_none
from app.services.profile_derivation import resolve_date
from app.services.resume_blocks import (
    Entry,
    block_for_achievement,
    blocks,
    ensure_ids,
    find_block,
    header,
    is_current,
)
from app.services.resume_jd import analyze_jd, jd_from_match, jd_hash
from app.services.resume_priority import (
    Candidate,
    Omission,
    RoleSpan,
    alignment,
    base_priority,
    blended,
    mmr_order,
    recency_factor,
    resolve_overlaps,
    role_priority,
    role_span,
    select_for_writing,
    tailoring_weight,
)
from app.services.resume_render.fit import fit_layout, unfitted_layout
from app.services.resume_render.page_meter import measure_pages
from app.services.resume_terms import GapSource, canon, gaps_report, jd_skill_wordings
from app.services.resume_writer import (
    BlockSpec,
    WriteItem,
    achievement_source,
    build_item,
    order_links,
    write_block,
)

logger = logging.getLogger(__name__)

Links = dict[uuid.UUID, list[tuple[AchievementEvidence, EvidenceItem]]]
MAX_REASON = 300


@dataclass
class Context:
    session: AsyncSession
    document: ResumeDocument
    content: ResumeContent
    generation: Generation
    settings: Settings
    achievements: dict[uuid.UUID, Achievement] = field(default_factory=dict[uuid.UUID, Achievement])
    links: Links = field(default_factory=Links)
    jd: JDAnalysis | None = None
    vector: list[float] | None = None
    weight: float = 0.0
    merges: Merges = field(default_factory=Merges)
    today: date = field(default_factory=lambda: datetime.now(UTC).date())


async def load_links(session: AsyncSession, ids: list[uuid.UUID]) -> Links:
    """Kept evidence behind each achievement; excluded or filtered items support no claim."""
    links: Links = {achievement_id: [] for achievement_id in ids}
    if not ids:
        return links
    rows = await session.execute(
        select(AchievementEvidence, EvidenceItem)
        .join(EvidenceItem, EvidenceItem.id == AchievementEvidence.item_id)
        .where(
            AchievementEvidence.achievement_id.in_(ids),
            EvidenceItem.status == EvidenceItemStatus.kept,
        )
    )
    for link, item in rows.tuples():
        links[link.achievement_id].append((link, item))
    return links


async def load_achievements(
    session: AsyncSession, candidate_id: uuid.UUID, *, exclude_private: bool
) -> list[Achievement]:
    approved = await resume_documents.approved_achievements(session, candidate_id)
    return [a for a in approved if not (exclude_private and a.derived_from_private)]


def jd_digest(jd: JDAnalysis) -> str:
    parts = [jd.domain or "", jd.seniority or "", *jd.must_haves, *jd.nice_to_haves, *jd.keywords]
    return "\n".join(part for part in parts if part)


async def _prepare_jd(ctx: Context) -> None:
    text = ctx.document.job_description
    if not text:
        return
    try:
        ctx.jd = await analyze_jd(ctx.session, text)
    except LLMError as exc:
        logger.warning("resume.jd analysis failed error=%s", type(exc).__name__)
        ctx.generation.warnings.append(
            "The job description could not be analysed, so this resume is not tailored to it."
        )
        return
    try:
        ctx.vector = (await embed_texts([jd_digest(ctx.jd)]))[0]
    except (LLMError, IndexError):
        ctx.generation.warnings.append(
            "The job description could not be embedded; tailoring uses keyword overlap only."
        )


def _embedding(achievement: Achievement) -> tuple[float, ...] | None:
    if achievement.embedding is None:
        return None
    return tuple(float(value) for value in achievement.embedding)


def _candidates(ctx: Context) -> tuple[list[Candidate], int]:
    terms: set[str] = set(jd_skill_wordings(ctx.jd)) if ctx.jd else set()
    found: list[Candidate] = []
    unplaced = 0
    for achievement in ctx.achievements.values():
        block_id = block_for_achievement(achievement, ctx.content, ctx.merges)
        if block_id is None:
            unplaced += 1
            continue
        base = base_priority(achievement, ctx.today, ctx.settings)
        aligned = (
            alignment(achievement.skills, _embedding(achievement), terms, ctx.vector)
            if ctx.jd
            else 0.0
        )
        found.append(
            Candidate(
                achievement_id=achievement.id,
                title=achievement.title,
                block_id=block_id,
                base=base,
                alignment=aligned,
                priority=blended(base, aligned, ctx.weight),
                skills=frozenset(canon(skill) for skill in achievement.skills),
                embedding=_embedding(achievement),
                from_private=achievement.derived_from_private,
            )
        )
    return found, unplaced


def _restore_omitted(ctx: Context) -> None:
    for omitted in sorted(ctx.generation.omitted_roles, key=lambda item: item.position):
        ctx.content.work.insert(min(omitted.position, len(ctx.content.work)), omitted.entry)
    ctx.generation.omitted_roles = []


def _role_spans(ctx: Context, candidates: list[Candidate]) -> list[RoleSpan]:
    by_block: dict[str, list[float]] = {}
    for candidate in candidates:
        by_block.setdefault(candidate.block_id, []).append(candidate.priority)
    spans: list[RoleSpan] = []
    for job in ctx.content.work:
        end = resolve_date(job.end_date) or (ctx.today if job.is_current else None)
        recency = recency_factor(end, resolve_date(job.start_date), ctx.today)
        spans.append(role_span(job, role_priority(by_block.get(job.id, []), recency), ctx.today))
    return spans


def _apply_overlaps(ctx: Context, candidates: list[Candidate]) -> set[str]:
    """Drop the lower-priority role of each overlapping pair; return the dropped block ids."""
    forced = frozenset(ctx.generation.included_roles)
    spans = _role_spans(ctx, candidates)
    _, omissions = resolve_overlaps(
        spans, ctx.settings.resume_overlap_min_days, forced, ctx.merges.key
    )
    position = {job.id: index for index, job in enumerate(ctx.content.work)}
    for omission in omissions:
        entry = next(job for job in ctx.content.work if job.id == omission.role.block_id)
        ctx.generation.omitted_roles.append(_omitted(omission, entry, position[entry.id]))
    dropped = {item.role.block_id for item in omissions}
    ctx.content.work = [job for job in ctx.content.work if job.id not in dropped]
    return dropped


def _omitted(omission: Omission, entry: WorkEntry, position: int) -> OmittedRole:
    blocker = omission.blocker
    name = f"{blocker.title or 'a role'} at {blocker.company or 'another employer'}"
    return OmittedRole(
        block_id=omission.role.block_id,
        company=omission.role.company,
        title=omission.role.title,
        priority=round(omission.role.priority, 4),
        overlaps_with=blocker.block_id,
        reason=f"Overlaps {name} by more than {get_settings().resume_overlap_min_days} days "
        "and ranks lower.",
        position=position,
        entry=entry.model_copy(deep=True),
    )


def _items_for(ctx: Context, chosen: list[Candidate]) -> list[WriteItem]:
    return [
        build_item(
            f"A{number}",
            ctx.achievements[candidate.achievement_id],
            ctx.links.get(candidate.achievement_id, []),
            ctx.jd,
            candidate.priority,
        )
        for number, candidate in enumerate(chosen, start=1)
    ]


async def _write_blocks(ctx: Context, selected: list[Candidate]) -> dict[str, list[Bullet]]:
    """Newly written bullets by block id; a block whose writer call fails is left untouched."""
    grouped: dict[str, list[Candidate]] = {}
    for candidate in selected:
        grouped.setdefault(candidate.block_id, []).append(candidate)
    written: dict[str, list[Bullet]] = {}
    for block_id, chosen in grouped.items():
        entry = find_block(ctx.content, block_id)
        if entry is None:
            continue
        spec = BlockSpec(entry.id, header(entry), is_current(entry))
        try:
            results = await write_block(ctx.session, spec, _items_for(ctx, chosen))
        except LLMError as exc:
            logger.warning("resume.write failed error=%s", type(exc).__name__)
            ctx.generation.warnings.append(
                f"Bullets for {header(entry)} could not be written; its existing bullets are kept."
            )
            continue
        written[block_id] = [item.bullet for item in results if item.bullet is not None]
    return written


def assemble_highlights(entry: Entry, generated: list[Bullet]) -> None:
    """Pinned and edited bullets stay; the rest is the new set; profile text only as fallback."""
    kept = [b for b in entry.highlights if b.pinned or b.origin == "user_edited"]
    taken = {b.achievement_id for b in kept if b.achievement_id is not None}
    fresh = [b for b in generated if b.achievement_id not in taken]
    combined = sorted([*kept, *fresh], key=lambda bullet: -bullet.score)
    if combined:
        entry.highlights = combined
        return
    entry.highlights = [b for b in entry.highlights if b.origin == "profile_verbatim"]


def _selection(ctx: Context, ordered: list[Candidate], only_block: str | None) -> list[Candidate]:
    if only_block is None:
        return select_for_writing(
            ordered, ctx.document.page_target, ctx.settings.resume_candidate_oversample
        )
    previous = {entry.achievement_id for entry in ctx.generation.pool if entry.written}
    in_block = [c for c in ordered if c.block_id == only_block]
    chosen = [c for c in in_block if c.achievement_id in previous]
    return chosen or in_block[:1]


def _order_skills(ctx: Context, placed: list[Candidate]) -> list[str]:
    """Profile skills plus evidence-backed ones; JD-relevant first, nothing unsupported added."""
    seen: dict[str, str] = {}
    for skill in ctx.content.skills:
        seen.setdefault(canon(skill), skill)
    for candidate in placed:
        for skill in ctx.achievements[candidate.achievement_id].skills:
            if skill.strip():
                seen.setdefault(canon(skill), skill.strip())
    wanted: set[str] = set(jd_skill_wordings(ctx.jd)) if ctx.jd else set()
    return [seen[key] for key in sorted(seen, key=lambda key: key not in wanted)]


def _gaps(ctx: Context, placed: list[Candidate]) -> list[GapItem]:
    sources = [
        GapSource(
            candidate.achievement_id,
            candidate.title,
            tuple(ctx.achievements[candidate.achievement_id].skills),
            achievement_source(
                ctx.achievements[candidate.achievement_id],
                order_links(ctx.links.get(candidate.achievement_id, [])),
            ).corpus,
        )
        for candidate in placed
    ]
    return gaps_report(ctx.jd, sources)


def _pool(ordered: list[Candidate], content: ResumeContent) -> list[PoolEntry]:
    written = {
        bullet.achievement_id
        for entry in blocks(content)
        for bullet in entry.highlights
        if bullet.achievement_id is not None
    }
    return [
        PoolEntry(
            achievement_id=candidate.achievement_id,
            block_id=candidate.block_id,
            title=candidate.title,
            priority=round(candidate.priority, 4),
            rank=rank,
            written=candidate.achievement_id in written,
        )
        for rank, candidate in enumerate(ordered, start=1)
    ]


async def _build(ctx: Context, only_block: str | None) -> None:
    ensure_ids(ctx.content)
    _restore_omitted(ctx)
    await _prepare_jd(ctx)
    ctx.weight = tailoring_weight(
        ctx.generation.tailoring_strength, ctx.settings, has_jd=ctx.jd is not None
    )
    candidates, ctx.generation.unplaced_count = _candidates(ctx)
    dropped = _apply_overlaps(ctx, candidates)
    placed = [c for c in candidates if c.block_id not in dropped]
    ordered = mmr_order(placed)
    written = await _write_blocks(ctx, _selection(ctx, ordered, only_block))
    for block_id, bullets in written.items():
        entry = find_block(ctx.content, block_id)
        if entry is not None and only_block in (None, block_id):
            assemble_highlights(entry, bullets)
    if only_block is None:
        ctx.content.skills = _order_skills(ctx, placed)
    ctx.generation.jd = ctx.jd
    ctx.generation.pool = _pool(ordered, ctx.content)
    ctx.generation.included_roles = [
        job.id for job in ctx.content.work if job.id in set(ctx.generation.included_roles)
    ]
    ctx.generation.gaps = _gaps(ctx, placed)
    ctx.generation.private_bullet_count = sum(
        1 for entry in blocks(ctx.content) for bullet in entry.highlights if bullet.from_private
    )


async def load_context(session: AsyncSession, document: ResumeDocument) -> Context:
    generation = Generation.model_validate(document.generation)
    achievements = await load_achievements(
        session, document.candidate_id, exclude_private=generation.exclude_private
    )
    links = await load_links(session, [a.id for a in achievements])
    candidate = await session.get(CandidateRow, document.candidate_id)
    return Context(
        session=session,
        document=document,
        content=ResumeContent.model_validate(document.content),
        generation=generation,
        settings=get_settings(),
        achievements={a.id: a for a in achievements},
        links=links,
        merges=Merges.from_stored(candidate.employer_merges if candidate else None),
    )


async def fit_context(ctx: Context, *, strict: bool) -> Layout:
    """Run the page fit off the event loop; when nothing fits, keep the content and say so.

    `strict` re-raises `CannotFitError` for the explicit fit and render actions.
    """
    document = ctx.document
    target = min(document.page_target, ctx.settings.resume_max_pages)
    try:
        return await asyncio.to_thread(
            fit_layout,
            ctx.content,
            ctx.generation,
            target,
            document.template,
            measure_pages,
            ctx.settings.resume_fit_max_compiles,
        )
    except CannotFitError:
        if strict:
            raise
        reason = f"nothing fits {target} page(s) even at the smallest type size"
        ctx.generation.warnings.append(f"The resume does not fit: {reason}.")
        return unfitted_layout(ctx.content, ctx.generation, reason)


async def persist(ctx: Context, source: str, *, strict: bool = False) -> None:
    """Store content, layout and generation; version and snapshot only when content changed."""
    document = ctx.document
    layout = await fit_context(ctx, strict=strict)
    ctx.generation.warnings = list(dict.fromkeys(ctx.generation.warnings))
    content = ctx.content.model_dump(mode="json")
    document.layout = layout.model_dump(mode="json")
    document.generation = ctx.generation.model_dump(mode="json")
    changed = content != document.content
    if changed:
        document.content = content
        document.version += 1
    await ctx.session.flush()
    if changed:
        await resume_documents.snapshot_revision(ctx.session, document, source)
    await ctx.session.refresh(document)


async def generate(
    session: AsyncSession, document: ResumeDocument, only_block: str | None = None
) -> ResumeDocumentResponse:
    """Rank, write and verify the document's content; returns data only, never a PDF."""
    ctx = await load_context(session, document)
    if only_block is not None and find_block(ctx.content, only_block) is None:
        raise ResumeBlockNotFoundError
    ctx.generation.warnings = []
    with usage_meter() as meter:
        await _build(ctx, only_block)
    ctx.generation.usage = GenerationUsage(
        calls=sum(usage.calls for usage in meter.tasks.values()),
        prompt_tokens=meter.prompt_tokens,
        completion_tokens=meter.completion_tokens,
        cost_usd=meter.cost_usd,
        cache_hits=meter.cache_hits,
        cache_misses=meter.cache_misses,
    )
    document.jd_weight = ctx.weight
    await persist(ctx, "generate")
    return resume_documents.to_response(document)


async def create_and_generate(
    session: AsyncSession, payload: ResumeDocumentCreate
) -> ResumeDocumentResponse:
    settings = get_settings()
    if payload.page_target > settings.resume_max_pages:
        msg = f"page_target cannot exceed {settings.resume_max_pages}"
        raise InvalidResumeDocumentError(msg)
    created = await resume_documents.create_document(session, payload)
    document = await resume_documents.owned_document(session, created.id)
    text = payload.job_description
    if payload.match_id is not None:
        text = await jd_from_match(session, document.profile_id, payload.match_id)
    document.template = payload.template
    document.job_description = text
    document.jd_hash = jd_hash(text) if text else None
    document.generation = Generation(
        tailoring_strength=payload.tailoring_strength, exclude_private=payload.exclude_private
    ).model_dump(mode="json")
    return await generate(session, document)


async def regenerate(
    session: AsyncSession, document_id: uuid.UUID, block_id: str | None
) -> ResumeDocumentResponse:
    document = await resume_documents.owned_document(session, document_id)
    return await generate(session, document, block_id)


async def include_role_anyway(
    session: AsyncSession, document_id: uuid.UUID, block_id: str
) -> ResumeDocumentResponse:
    document = await resume_documents.owned_document(session, document_id)
    generation = Generation.model_validate(document.generation)
    if all(item.block_id != block_id for item in generation.omitted_roles):
        raise ResumeBlockNotFoundError
    generation.included_roles = [*generation.included_roles, block_id]
    document.generation = generation.model_dump(mode="json")
    return await generate(session, document)


async def write_on_demand(
    session: AsyncSession, document_id: uuid.UUID, achievement_id: uuid.UUID
) -> ResumeDocumentResponse:
    """Write one available (ranked but unwritten) achievement and pin it into its block."""
    document = await resume_documents.owned_document(session, document_id)
    ctx = await load_context(session, document)
    achievement = ctx.achievements.get(achievement_id)
    candidate_id = await candidate_id_or_none(session)
    if achievement is None or achievement.candidate_id != candidate_id:
        raise AchievementNotFoundError
    if achievement.status != AchievementStatus.approved:
        raise AchievementNotFoundError
    ensure_ids(ctx.content)
    block_id = block_for_achievement(achievement, ctx.content, ctx.merges)
    entry = find_block(ctx.content, block_id) if block_id else None
    if entry is None:
        msg = "the achievement belongs to a role or project that is not in this document"
        raise InvalidResumeDocumentError(msg)
    if any(b.achievement_id == achievement_id for b in entry.highlights):
        return resume_documents.to_response(document)
    pooled = next((p for p in ctx.generation.pool if p.achievement_id == achievement_id), None)
    priority = pooled.priority if pooled else base_priority(achievement, ctx.today, ctx.settings)
    item = build_item("A1", achievement, ctx.links.get(achievement_id, []), ctx.jd, priority)
    with usage_meter():
        results = await write_block(
            session, BlockSpec(entry.id, header(entry), is_current(entry)), [item]
        )
    bullet = results[0].bullet if results else None
    if bullet is None:
        reason = (results[0].rejected_reason if results else None) or "no bullet was written"
        raise InvalidResumeDocumentError(reason[:MAX_REASON])
    bullet.pinned = True
    entry.highlights = sorted([*entry.highlights, bullet], key=lambda b: -b.score)
    if pooled is not None:
        pooled.written = True
    await persist(ctx, "write_on_demand")
    return resume_documents.to_response(document)
