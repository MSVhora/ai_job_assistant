import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BulletNotFoundError, InvalidResumeDocumentError
from app.schemas.resume_document import Bullet, BulletUpdate, ResumeDocumentResponse, WorkEntry
from app.services import resume_documents
from app.services.resume_blocks import Entry, ensure_ids, find_bullet
from app.services.resume_builder import Context, load_context, persist
from app.services.resume_verify import (
    Source,
    build_source,
    check_claims,
    metric_ids_used,
    unconfirmed_figures,
)
from app.services.resume_writer import achievement_source, order_links


def _entry_source(entry: Entry, bullet: Bullet) -> Source:
    """Without an achievement, a bullet may rely on its own block's profile text."""
    parts = [bullet.text, *(item.text for item in entry.highlights)]
    if isinstance(entry, WorkEntry):
        return build_source([*parts, entry.title or "", entry.company or ""])
    parts += [entry.name, entry.role or "", entry.description or ""]
    return build_source(parts, entry.technologies)


def _violations(ctx: Context, entry: Entry, bullet: Bullet, text: str) -> list[str]:
    achievement = ctx.achievements.get(bullet.achievement_id) if bullet.achievement_id else None
    if achievement is None:
        return check_claims(text, _entry_source(entry, bullet))
    source = achievement_source(achievement, order_links(ctx.links.get(achievement.id, [])))
    bullet.metric_ids = metric_ids_used(text, achievement.metrics)
    return [*check_claims(text, source), *unconfirmed_figures(text, achievement.metrics)]


def _edit_text(ctx: Context, entry: Entry, bullet: Bullet, text: str) -> None:
    """A user's own wording: re-verified deterministically, pinned, never regenerated."""
    cleaned = " ".join(text.split())
    violations = _violations(ctx, entry, bullet, cleaned)
    bullet.text = cleaned
    bullet.origin = "user_edited"
    bullet.pinned = True
    bullet.approved_anyway = False
    bullet.check = "needs_review" if violations else "passed"
    bullet.flags = violations


async def _context_with_bullet(
    session: AsyncSession, document_id: uuid.UUID, bullet_id: str
) -> tuple[Context, Entry, Bullet]:
    document = await resume_documents.owned_document(session, document_id)
    ctx = await load_context(session, document)
    ensure_ids(ctx.content)
    found = find_bullet(ctx.content, bullet_id)
    if found is None:
        raise BulletNotFoundError
    return ctx, found[0], found[1]


async def update_bullet(
    session: AsyncSession, document_id: uuid.UUID, bullet_id: str, payload: BulletUpdate
) -> ResumeDocumentResponse:
    ctx, entry, bullet = await _context_with_bullet(session, document_id, bullet_id)
    if payload.text is not None:
        _edit_text(ctx, entry, bullet, payload.text)
    if payload.pinned is not None:
        bullet.pinned = payload.pinned or bullet.origin == "user_edited"
    await persist(ctx, "bullet_edit")
    return resume_documents.to_response(ctx.document)


async def approve_anyway(
    session: AsyncSession, document_id: uuid.UUID, bullet_id: str
) -> ResumeDocumentResponse:
    """Explicit override of a `needs_review` flag; the flags stay so the override is on record."""
    ctx, _, bullet = await _context_with_bullet(session, document_id, bullet_id)
    if bullet.check != "needs_review":
        msg = "only a bullet flagged for review can be approved anyway"
        raise InvalidResumeDocumentError(msg)
    bullet.check = "passed"
    bullet.approved_anyway = True
    await persist(ctx, "approve_anyway")
    return resume_documents.to_response(ctx.document)


async def remove_bullet(
    session: AsyncSession, document_id: uuid.UUID, bullet_id: str
) -> ResumeDocumentResponse:
    """Take a bullet out of the document; its achievement goes back to the unwritten pool."""
    ctx, entry, bullet = await _context_with_bullet(session, document_id, bullet_id)
    entry.highlights = [item for item in entry.highlights if item.id != bullet.id]
    for pooled in ctx.generation.pool:
        if bullet.achievement_id is not None and pooled.achievement_id == bullet.achievement_id:
            pooled.written = False
    await persist(ctx, "bullet_remove")
    return resume_documents.to_response(ctx.document)
