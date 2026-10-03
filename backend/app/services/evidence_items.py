import uuid
from dataclasses import dataclass

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import EvidenceItemNotFoundError
from app.core.pagination import DEFAULT_PAGE, Pagination
from app.models import Candidate, EvidenceItem, EvidenceItemStatus, EvidenceKind
from app.schemas.evidence import ItemResponse


@dataclass(frozen=True)
class ItemFilters:
    kind: EvidenceKind | None = None
    project_key: str | None = None
    status: EvidenceItemStatus = EvidenceItemStatus.kept
    is_private: bool | None = None


def item_response(item: EvidenceItem) -> ItemResponse:
    return ItemResponse.model_validate(item)


async def candidate_id_or_none(session: AsyncSession) -> uuid.UUID | None:
    return (await session.execute(select(Candidate.id).limit(1))).scalars().first()


async def owned_item(session: AsyncSession, item_id: uuid.UUID) -> EvidenceItem:
    candidate_id = await candidate_id_or_none(session)
    item = await session.get(EvidenceItem, item_id)
    if item is None or candidate_id is None or item.candidate_id != candidate_id:
        raise EvidenceItemNotFoundError
    return item


def _filtered(candidate_id: uuid.UUID, filters: ItemFilters) -> Select[tuple[EvidenceItem]]:
    query = select(EvidenceItem).where(
        EvidenceItem.candidate_id == candidate_id, EvidenceItem.status == filters.status
    )
    if filters.kind is not None:
        query = query.where(EvidenceItem.kind == filters.kind)
    if filters.project_key is not None:
        query = query.where(EvidenceItem.project_key == filters.project_key)
    if filters.is_private is not None:
        query = query.where(EvidenceItem.is_private.is_(filters.is_private))
    return query


async def count_items(session: AsyncSession, filters: ItemFilters) -> int:
    candidate_id = await candidate_id_or_none(session)
    if candidate_id is None:
        return 0
    subquery = _filtered(candidate_id, filters).subquery()
    return (await session.execute(select(func.count()).select_from(subquery))).scalar_one()


async def list_items(
    session: AsyncSession, filters: ItemFilters, page: Pagination = DEFAULT_PAGE
) -> list[ItemResponse]:
    candidate_id = await candidate_id_or_none(session)
    if candidate_id is None:
        return []
    rows = (
        (
            await session.execute(
                _filtered(candidate_id, filters)
                .order_by(EvidenceItem.occurred_at.desc().nulls_last(), EvidenceItem.id)
                .limit(page.limit)
                .offset(page.offset)
            )
        )
        .scalars()
        .all()
    )
    return [item_response(row) for row in rows]


async def get_item(session: AsyncSession, item_id: uuid.UUID) -> ItemResponse:
    return item_response(await owned_item(session, item_id))


async def set_item_status(
    session: AsyncSession, item_id: uuid.UUID, status: EvidenceItemStatus
) -> tuple[ItemResponse, uuid.UUID]:
    """Restore a filtered/excluded item or exclude a kept one; touches no profile table."""
    item = await owned_item(session, item_id)
    if item.status is not status:
        item.status = status
        if status is EvidenceItemStatus.kept:
            item.filter_reason = None
    await session.flush()
    await session.refresh(item)
    return item_response(item), item.candidate_id
