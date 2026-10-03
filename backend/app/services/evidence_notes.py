import re
import uuid
from datetime import UTC, datetime
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import DuplicateEvidenceError, EvidenceItemNotFoundError
from app.core.pagination import DEFAULT_PAGE, Pagination
from app.models import EvidenceItem, EvidenceItemStatus, EvidenceKind
from app.schemas.evidence import ItemResponse, LinkCreate, NoteCreate, NoteUpdate
from app.services.evidence_items import (
    ItemFilters,
    count_items,
    item_response,
    list_items,
    owned_item,
)
from app.services.evidence_pipeline.dedupe import digest
from app.services.resume_service import get_or_create_candidate

SLUG_LENGTH = 40
_SLUG_RUN = re.compile(r"[^a-z0-9]+")


def _slug(text: str) -> str:
    return _SLUG_RUN.sub("-", text.lower()).strip("-")[:SLUG_LENGTH].strip("-") or "note"


async def _find(
    session: AsyncSession, candidate_id: uuid.UUID, kind: EvidenceKind, external_id: str
) -> EvidenceItem | None:
    return (
        await session.execute(
            select(EvidenceItem).where(
                EvidenceItem.candidate_id == candidate_id,
                EvidenceItem.kind == kind,
                EvidenceItem.external_id == external_id,
            )
        )
    ).scalar_one_or_none()


def _revive(item: EvidenceItem) -> EvidenceItem:
    meta = dict(item.meta)
    meta.pop("superseded_by", None)
    item.meta = meta
    item.status = EvidenceItemStatus.kept
    item.filter_reason = None
    return item


async def _store(session: AsyncSession, item: EvidenceItem) -> EvidenceItem:
    """Insert `item`, or revive an excluded twin; a kept twin is a duplicate."""
    twin = await _find(session, item.candidate_id, item.kind, item.external_id)
    if twin is not None:
        if twin.status is EvidenceItemStatus.kept:
            raise DuplicateEvidenceError
        revived = _revive(twin)
        await session.flush()
        return revived
    session.add(item)
    await session.flush()
    return item


async def create_note(session: AsyncSession, payload: NoteCreate) -> ItemResponse:
    candidate = await get_or_create_candidate(session)
    external_id = digest(payload.title or "", payload.body)
    item = EvidenceItem(
        candidate_id=candidate.id,
        kind=EvidenceKind.note,
        external_id=external_id,
        project_key=f"note:{_slug(payload.title or payload.body)}",
        title=payload.title,
        body=payload.body,
        occurred_at=datetime.now(UTC),
        status=EvidenceItemStatus.kept,
        content_hash=external_id,
    )
    stored = await _store(session, item)
    await session.refresh(stored)
    return item_response(stored)


async def _owned_note(session: AsyncSession, item_id: uuid.UUID) -> EvidenceItem:
    item = await owned_item(session, item_id)
    if item.kind is not EvidenceKind.note or item.status is not EvidenceItemStatus.kept:
        raise EvidenceItemNotFoundError
    return item


async def update_note(
    session: AsyncSession, item_id: uuid.UUID, payload: NoteUpdate
) -> tuple[ItemResponse, uuid.UUID]:
    """Editing creates a new note version and excludes the old one (`meta.superseded_by`)."""
    old = await _owned_note(session, item_id)
    title = payload.title if "title" in payload.model_fields_set else old.title
    body = payload.body if payload.body is not None else old.body
    external_id = digest(title or "", body)
    if external_id == old.external_id:
        return item_response(old), old.candidate_id
    replacement = EvidenceItem(
        candidate_id=old.candidate_id,
        kind=EvidenceKind.note,
        external_id=external_id,
        project_key=f"note:{_slug(title or body)}",
        title=title,
        body=body,
        occurred_at=datetime.now(UTC),
        status=EvidenceItemStatus.kept,
        content_hash=external_id,
    )
    stored = await _store(session, replacement)
    old.status = EvidenceItemStatus.excluded
    old.meta = {**old.meta, "superseded_by": str(stored.id)}
    await session.flush()
    await session.refresh(stored)
    return item_response(stored), stored.candidate_id


async def delete_note(session: AsyncSession, item_id: uuid.UUID) -> uuid.UUID:
    item = await _owned_note(session, item_id)
    item.status = EvidenceItemStatus.excluded
    await session.flush()
    return item.candidate_id


async def list_notes(
    session: AsyncSession, page: Pagination = DEFAULT_PAGE
) -> tuple[list[ItemResponse], int]:
    filters = ItemFilters(kind=EvidenceKind.note)
    return await list_items(session, filters, page), await count_items(session, filters)


async def create_link(session: AsyncSession, payload: LinkCreate) -> ItemResponse:
    candidate = await get_or_create_candidate(session)
    url = str(payload.url)
    host = urlparse(url).hostname or "link"
    external_id = digest(url)
    item = EvidenceItem(
        candidate_id=candidate.id,
        kind=EvidenceKind.link,
        external_id=external_id,
        project_key=f"link:{host}",
        title=payload.title,
        body=payload.text or payload.title or url,
        url=url,
        occurred_at=datetime.now(UTC),
        status=EvidenceItemStatus.kept,
        meta={"url_only": payload.text is None},
        content_hash=external_id,
    )
    stored = await _store(session, item)
    await session.refresh(stored)
    return item_response(stored)
