import logging
import uuid
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.llm import LLMError, usage_meter
from app.core.errors import CommentNotFoundError, InvalidCommentTargetError
from app.models import ResumeDocument
from app.schemas.resume_document import (
    Bullet,
    CommentCreate,
    CommentUpdate,
    GenerationUsage,
    ResumeComment,
    ResumeDocumentResponse,
)
from app.services import resume_documents
from app.services.resume_blocks import Entry, ensure_ids, find_block, header, is_current, section_of
from app.services.resume_builder import Context, load_context, persist
from app.services.resume_jd import analyze_jd
from app.services.resume_terms import scan_skills
from app.services.resume_writer import BlockSpec, WriteItem, WrittenItem, build_item, write_block

logger = logging.getLogger(__name__)

ADD_NOTE_HINT = "Add a note so this becomes evidence, then it can be used next time."


@dataclass
class _Plan:
    """What applying one block's open comments will rewrite."""

    items: list[WriteItem] = field(default_factory=list[WriteItem])
    by_comment: dict[str, list[str]] = field(default_factory=dict[str, list[str]])


def _now() -> datetime:
    return datetime.now(UTC)


def _comments(document: ResumeDocument) -> list[ResumeComment]:
    return [ResumeComment.model_validate(item) for item in document.comments]


def _store(document: ResumeDocument, comments: list[ResumeComment]) -> None:
    document.comments = [comment.model_dump(mode="json") for comment in comments]


async def _save(session: AsyncSession, document: ResumeDocument) -> ResumeDocumentResponse:
    await session.flush()
    await session.refresh(document)
    return resume_documents.to_response(document)


async def _owned_with_ids(
    session: AsyncSession, document_id: uuid.UUID
) -> tuple[ResumeDocument, Context]:
    document = await resume_documents.owned_document(session, document_id)
    ctx = await load_context(session, document)
    ensure_ids(ctx.content)
    return document, ctx


def _validate_target(ctx: Context, payload: CommentCreate) -> None:
    entry = find_block(ctx.content, payload.target.block_id)
    if entry is None or section_of(entry) != payload.target.section:
        raise InvalidCommentTargetError
    bullet_id = payload.target.bullet_id
    if bullet_id is not None and all(item.id != bullet_id for item in entry.highlights):
        raise InvalidCommentTargetError


async def add_comment(
    session: AsyncSession, document_id: uuid.UUID, payload: CommentCreate
) -> ResumeDocumentResponse:
    document, ctx = await _owned_with_ids(session, document_id)
    _validate_target(ctx, payload)
    comments = _comments(document)
    comments.append(
        ResumeComment(
            id=uuid.uuid4().hex[:12], target=payload.target, text=payload.text, created_at=_now()
        )
    )
    _store(document, comments)
    return await _save(session, document)


async def update_comment(
    session: AsyncSession, document_id: uuid.UUID, comment_id: str, payload: CommentUpdate
) -> ResumeDocumentResponse:
    document = await resume_documents.owned_document(session, document_id)
    comments = _comments(document)
    comment = next((item for item in comments if item.id == comment_id), None)
    if comment is None:
        raise CommentNotFoundError
    comment.text = payload.text
    comment.status = "open"
    comment.reason = None
    comment.action = None
    comment.resolved_at = None
    _store(document, comments)
    return await _save(session, document)


async def delete_comment(
    session: AsyncSession, document_id: uuid.UUID, comment_id: str
) -> ResumeDocumentResponse:
    document = await resume_documents.owned_document(session, document_id)
    comments = _comments(document)
    remaining = [item for item in comments if item.id != comment_id]
    if len(remaining) == len(comments):
        raise CommentNotFoundError
    _store(document, remaining)
    return await _save(session, document)


def _reject(comment: ResumeComment, reason: str, *, add_note: bool) -> None:
    comment.status = "rejected"
    comment.reason = reason
    comment.action = "add_note" if add_note else None
    comment.resolved_at = _now()


def _rewritable(ctx: Context, entry: Entry, comment: ResumeComment) -> list[Bullet]:
    scope = [b for b in entry.highlights if comment.target.bullet_id in (None, b.id)]
    return [
        b
        for b in scope
        if b.origin == "generated"
        and not b.pinned
        and b.achievement_id is not None
        and b.achievement_id in ctx.achievements
    ]


def _unsupported_tools(comment: ResumeComment, items: list[WriteItem]) -> list[str]:
    supported: set[str] = set()
    for item in items:
        supported |= item.source.skills
    lowered = " ".join(item.source.corpus for item in items).casefold()
    return list(
        dict.fromkeys(
            wording
            for wording, key in scan_skills(comment.text)
            if key not in supported and wording.casefold() not in lowered
        )
    )


def _plan_block(ctx: Context, entry: Entry, comments: list[ResumeComment]) -> _Plan:
    plan = _Plan()
    keys: dict[uuid.UUID, str] = {}
    instructions: dict[uuid.UUID, list[str]] = {}
    bullets: dict[uuid.UUID, Bullet] = {}
    for comment in comments:
        targets = _rewritable(ctx, entry, comment)
        if not targets:
            _reject(
                comment,
                "Nothing here can be rewritten automatically: its bullets are pinned, edited "
                "by you or copied from your profile. Edit them directly.",
                add_note=False,
            )
            continue
        for bullet in targets:
            achievement_id = bullet.achievement_id
            if achievement_id is None:
                continue
            bullets[achievement_id] = bullet
            instructions.setdefault(achievement_id, []).append(comment.text)
            keys.setdefault(achievement_id, f"A{len(keys) + 1}")
            plan.by_comment.setdefault(comment.id, []).append(keys[achievement_id])
    for achievement_id, key in keys.items():
        bullet = bullets[achievement_id]
        item = build_item(
            key,
            ctx.achievements[achievement_id],
            ctx.links.get(achievement_id, []),
            ctx.jd,
            bullet.score,
        )
        plan.items.append(
            replace(item, instruction=" ".join(instructions[achievement_id]), previous=bullet.text)
        )
    return plan


def _screen_unsupported(comments: list[ResumeComment], plan: _Plan) -> list[ResumeComment]:
    """Reject comments that ask for a tool the block's evidence never mentions."""
    live: list[ResumeComment] = []
    by_key = {item.key: item for item in plan.items}
    for comment in comments:
        if comment.status != "open":
            continue
        items = [by_key[key] for key in plan.by_comment.get(comment.id, []) if key in by_key]
        missing = _unsupported_tools(comment, items)
        if missing:
            _reject(
                comment,
                f"There is no evidence for {', '.join(missing)} in this section, so the comment "
                f"was not applied. {ADD_NOTE_HINT}",
                add_note=True,
            )
        else:
            live.append(comment)
    return live


def _apply_results(
    entry: Entry, comments: list[ResumeComment], plan: _Plan, results: list[WrittenItem]
) -> None:
    by_key = {result.item.key: result for result in results}
    for result in results:
        if result.bullet is None:
            continue
        index = next(
            (
                i
                for i, b in enumerate(entry.highlights)
                if b.achievement_id == result.bullet.achievement_id
            ),
            None,
        )
        if index is not None:
            entry.highlights[index] = result.bullet
    for comment in comments:
        written = [by_key[k] for k in plan.by_comment.get(comment.id, []) if k in by_key]
        if any(item.bullet is not None for item in written):
            comment.status = "applied"
            comment.resolved_at = _now()
            continue
        declined = next((item.rejected_reason for item in written if item.rejected_reason), None)
        _reject(
            comment,
            f"The evidence does not support this request: {declined or 'no change was made'}. "
            f"{ADD_NOTE_HINT}",
            add_note=True,
        )


async def _apply_block(ctx: Context, entry: Entry, comments: list[ResumeComment]) -> None:
    plan = _plan_block(ctx, entry, comments)
    live = _screen_unsupported(comments, plan)
    keep = {key for comment in live for key in plan.by_comment.get(comment.id, [])}
    plan.items = [item for item in plan.items if item.key in keep]
    if not plan.items:
        return
    spec = BlockSpec(entry.id, header(entry), is_current(entry))
    try:
        results = await write_block(ctx.session, spec, plan.items)
    except LLMError as exc:
        logger.warning("resume.comments write failed error=%s", type(exc).__name__)
        ctx.generation.warnings.append(
            f"Comments on {header(entry)} could not be applied; they stay open."
        )
        return
    _apply_results(entry, live, plan, results)


async def _load_jd(ctx: Context) -> None:
    if not ctx.document.job_description:
        return
    try:
        ctx.jd = await analyze_jd(ctx.session, ctx.document.job_description)
    except LLMError:
        ctx.jd = None


async def apply_comments(session: AsyncSession, document_id: uuid.UUID) -> ResumeDocumentResponse:
    """Regenerate only the commented blocks; every other block stays byte-identical."""
    document, ctx = await _owned_with_ids(session, document_id)
    comments = _comments(document)
    open_comments = [item for item in comments if item.status == "open"]
    if not open_comments:
        return resume_documents.to_response(document)
    ctx.generation.warnings = []
    grouped: dict[str, list[ResumeComment]] = {}
    for comment in open_comments:
        grouped.setdefault(comment.target.block_id, []).append(comment)
    with usage_meter() as meter:
        await _load_jd(ctx)
        for block_id, block_comments in grouped.items():
            entry = find_block(ctx.content, block_id)
            if entry is None:
                for comment in block_comments:
                    _reject(comment, "That section is no longer in the document.", add_note=False)
                continue
            await _apply_block(ctx, entry, block_comments)
    ctx.generation.usage = GenerationUsage(
        calls=sum(usage.calls for usage in meter.tasks.values()),
        prompt_tokens=meter.prompt_tokens,
        completion_tokens=meter.completion_tokens,
        cost_usd=meter.cost_usd,
        cache_hits=meter.cache_hits,
        cache_misses=meter.cache_misses,
    )
    _store(document, comments)
    await persist(ctx, "apply_comments")
    return resume_documents.to_response(document)
