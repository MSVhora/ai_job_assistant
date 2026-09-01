from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.job_sources import registry
from app.adapters.job_sources.base import JobSource
from app.core.errors import DisclosureNotAcknowledgedError, JobSourceNotFoundError
from app.models import SourceState
from app.schemas.job_search import SourceInfoResponse


async def list_sources_with_state(session: AsyncSession) -> list[SourceInfoResponse]:
    acknowledged = await _acknowledged_names(session)
    return [_source_info(source, acknowledged) for source in registry.all_sources()]


async def enable_source(
    session: AsyncSession, name: str, acknowledged_disclosure: bool
) -> SourceInfoResponse:
    source = registry.get_source(name)
    if source is None:
        raise JobSourceNotFoundError()
    if source.disclosure_required:
        if not acknowledged_disclosure:
            raise DisclosureNotAcknowledgedError()
        await _acknowledge(session, name)
    return _source_info(source, await _acknowledged_names(session))


async def enabled_sources(session: AsyncSession) -> list[JobSource]:
    acknowledged = await _acknowledged_names(session)
    return [
        source
        for source in registry.all_sources()
        if source.is_configured()
        and (not source.disclosure_required or source.name in acknowledged)
    ]


def _source_info(source: JobSource, acknowledged: set[str]) -> SourceInfoResponse:
    return SourceInfoResponse(
        name=source.name,
        is_official_api=source.is_official_api,
        disclosure_required=source.disclosure_required,
        is_configured=source.is_configured(),
        enabled=source.is_configured()
        and (not source.disclosure_required or source.name in acknowledged),
        supports_exclusions=source.supports_exclusions,
    )


async def _acknowledged_names(session: AsyncSession) -> set[str]:
    rows = await session.execute(
        select(SourceState.source_name).where(SourceState.acknowledged_at.is_not(None))
    )
    return set(rows.scalars().all())


async def _acknowledge(session: AsyncSession, name: str) -> None:
    state = await session.get(SourceState, name)
    if state is None:
        state = SourceState(source_name=name)
        session.add(state)
    if state.acknowledged_at is None:
        state.acknowledged_at = datetime.now(UTC)
    await session.flush()
