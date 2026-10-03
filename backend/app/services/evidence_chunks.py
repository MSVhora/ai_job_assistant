import logging
import uuid
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field, replace

from sqlalchemy import and_, delete, func, insert, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.llm import LLMError, is_llm_configured, usage_meter
from app.core.config import get_settings
from app.core.db import session_factory
from app.models import (
    Candidate,
    EvidenceChunk,
    EvidenceChunkItem,
    EvidenceItem,
    EvidenceItemStatus,
)
from app.schemas.evidence import ChunkSummaryResponse
from app.services.embedding import MAX_EMBED_CHARS, embed_texts
from app.services.evidence_pipeline.chunking import ChunkDraft, ItemView, build_chunks
from app.services.evidence_pipeline.dedupe import CHUNKER_VERSION, SQUASH_REASON

logger = logging.getLogger(__name__)

EMBED_BATCH_SIZE = 32
_INT64_MASK = 0x7FFFFFFFFFFFFFFF

ChunkKey = tuple[str, str | None, str]


@dataclass
class RebuildResult:
    created: int = 0
    deleted: int = 0
    unchanged: int = 0
    embedded: int = 0
    embed_failed: int = 0
    pending_embedding: int = 0
    prompt_tokens: int = 0
    cost_usd: float | None = 0.0
    redactions: dict[str, int] = field(default_factory=dict[str, int])

    def as_progress(self) -> dict[str, object]:
        return {
            "created": self.created,
            "deleted": self.deleted,
            "unchanged": self.unchanged,
            "embedded": self.embedded,
            "embed_failed": self.embed_failed,
            "pending_embedding": self.pending_embedding,
            "redactions": self.redactions,
        }


def _batched(items: Sequence[EvidenceChunk], size: int) -> Iterator[Sequence[EvidenceChunk]]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


def _embed_text(chunk: EvidenceChunk) -> str:
    text = f"{chunk.title}\n{chunk.text}" if chunk.title else chunk.text
    return text[:MAX_EMBED_CHARS]


async def _load_views(session: AsyncSession, candidate_id: uuid.UUID) -> list[ItemView]:
    squash = and_(
        EvidenceItem.status == EvidenceItemStatus.filtered,
        EvidenceItem.filter_reason == SQUASH_REASON,
    )
    rows = (
        (
            await session.execute(
                select(EvidenceItem).where(
                    EvidenceItem.candidate_id == candidate_id,
                    or_(EvidenceItem.status == EvidenceItemStatus.kept, squash),
                )
            )
        )
        .scalars()
        .all()
    )
    return [
        ItemView(
            id=row.id,
            kind=row.kind,
            external_id=row.external_id,
            project_key=row.project_key,
            title=row.title,
            body=row.body,
            occurred_at=row.occurred_at,
            is_private=row.is_private,
            meta=row.meta,
        )
        for row in rows
    ]


def _merge_drafts(drafts: Sequence[ChunkDraft]) -> dict[ChunkKey, ChunkDraft]:
    merged: dict[ChunkKey, ChunkDraft] = {}
    for draft in drafts:
        key = (draft.kind, draft.project_key, draft.content_hash)
        known = merged.get(key)
        if known is None:
            merged[key] = draft
        else:
            merged[key] = replace(
                known,
                item_ids=tuple(dict.fromkeys((*known.item_ids, *draft.item_ids))),
                contains_private=known.contains_private or draft.contains_private,
            )
    return merged


def _apply_draft(chunk: EvidenceChunk, draft: ChunkDraft) -> None:
    chunk.title = draft.title
    chunk.text = draft.text
    chunk.token_count = draft.token_count
    chunk.chunker_version = CHUNKER_VERSION
    chunk.contains_private = draft.contains_private
    chunk.time_start = draft.time_start
    chunk.time_end = draft.time_end


async def _embed_pending(chunks: list[EvidenceChunk], result: RebuildResult) -> None:
    pending = [chunk for chunk in chunks if chunk.embedding is None]
    if not pending:
        return
    if not is_llm_configured():
        result.pending_embedding = len(pending)
        return
    with usage_meter() as meter:
        for index, batch in enumerate(_batched(pending, EMBED_BATCH_SIZE)):
            try:
                vectors = await embed_texts([_embed_text(chunk) for chunk in batch])
            except LLMError as exc:
                failed = len(pending) - index * EMBED_BATCH_SIZE
                result.embed_failed = failed
                logger.warning(
                    "evidence.chunks embedding failed error=%s remaining=%d", exc, failed
                )
                break
            for chunk, vector in zip(batch, vectors, strict=True):
                chunk.embedding = vector
            result.embedded += len(batch)
    result.pending_embedding = len(pending) - result.embedded
    result.prompt_tokens = meter.prompt_tokens
    result.cost_usd = meter.cost_usd


async def rebuild_chunks(session: AsyncSession, candidate_id: uuid.UUID) -> RebuildResult:
    """Make stored chunks match the kept evidence; embed only chunks without a vector.

    Serialized per candidate with a transaction-level advisory lock; the caller commits.
    """
    await session.execute(select(func.pg_advisory_xact_lock(candidate_id.int & _INT64_MASK)))
    settings = get_settings()
    views = await _load_views(session, candidate_id)
    built = build_chunks(views, redaction_enabled=settings.evidence_redaction_enabled)
    desired = _merge_drafts(built.drafts)
    existing = {
        (chunk.kind, chunk.project_key, chunk.content_hash): chunk
        for chunk in (
            await session.execute(
                select(EvidenceChunk).where(EvidenceChunk.candidate_id == candidate_id)
            )
        )
        .scalars()
        .all()
    }
    result = RebuildResult(redactions=built.redactions)
    for key, chunk in existing.items():
        if key not in desired:
            await session.delete(chunk)
            result.deleted += 1
    current: list[EvidenceChunk] = []
    links: list[dict[str, uuid.UUID]] = []
    for key, draft in desired.items():
        chunk = existing.get(key)
        if chunk is None:
            chunk = EvidenceChunk(
                candidate_id=candidate_id,
                kind=draft.kind,
                project_key=draft.project_key,
                content_hash=draft.content_hash,
            )
            session.add(chunk)
            result.created += 1
        else:
            result.unchanged += 1
        _apply_draft(chunk, draft)
        current.append(chunk)
    await session.flush()
    chunk_ids = [chunk.id for chunk in current]
    if chunk_ids:
        await session.execute(
            delete(EvidenceChunkItem).where(EvidenceChunkItem.chunk_id.in_(chunk_ids))
        )
    for chunk, draft in zip(current, desired.values(), strict=True):
        links.extend({"chunk_id": chunk.id, "item_id": item_id} for item_id in draft.item_ids)
    if links:
        await session.execute(insert(EvidenceChunkItem), links)
    await _embed_pending(current, result)
    logger.info(
        "evidence.chunks created=%d deleted=%d unchanged=%d embedded=%d embed_failed=%d "
        "prompt_tokens=%d redactions=%s",
        result.created,
        result.deleted,
        result.unchanged,
        result.embedded,
        result.embed_failed,
        result.prompt_tokens,
        result.redactions,
    )
    return result


async def rebuild_chunks_background(candidate_id: uuid.UUID) -> RebuildResult:
    async with session_factory() as session:
        result = await rebuild_chunks(session, candidate_id)
        await session.commit()
        return result


async def chunk_summary(session: AsyncSession) -> ChunkSummaryResponse:
    candidate_id = (await session.execute(select(Candidate.id).limit(1))).scalars().first()
    rows: list[tuple[str, int, bool, bool]] = []
    if candidate_id is not None:
        result = await session.execute(
            select(
                EvidenceChunk.kind,
                EvidenceChunk.token_count,
                EvidenceChunk.contains_private,
                EvidenceChunk.embedding.is_(None),
            ).where(EvidenceChunk.candidate_id == candidate_id)
        )
        rows = [(row[0], row[1], row[2], row[3]) for row in result.all()]
    by_kind: dict[str, int] = {}
    for kind, _, _, _ in rows:
        by_kind[kind] = by_kind.get(kind, 0) + 1
    private = sum(1 for _, _, contains_private, _ in rows if contains_private)
    pending = sum(1 for _, _, _, missing in rows if missing)
    return ChunkSummaryResponse(
        chunks=len(rows),
        tokens=sum(tokens for _, tokens, _, _ in rows),
        private_chunks=private,
        private_share=round(private / len(rows), 4) if rows else 0.0,
        embedded=len(rows) - pending,
        pending_embedding=pending,
        by_kind=by_kind,
    )
