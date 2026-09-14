import logging
import time
import uuid
from datetime import UTC, datetime

from fastapi import BackgroundTasks
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.job_sources import registry
from app.adapters.job_sources.base import (
    ConnectorError,
    JobPostingData,
    JobSource,
    validate_source_options,
)
from app.adapters.llm import LLMError
from app.core.db import session_factory
from app.core.errors import (
    DomainError,
    JobPostingNotFoundError,
    JobSearchNotFoundError,
    JobSourceNotEnabledError,
    MissingProfileIdError,
    MissingSearchQueryError,
    NoJobSourcesConfiguredError,
    ProfileNotFoundError,
    UnknownJobSourceError,
)
from app.models import JobPosting, JobSearch, JobSearchStatus, Profile, SearchPosting
from app.schemas.job_search import (
    JobPostingDetail,
    JobPostingSummary,
    JobSearchRequest,
    JobSearchStartResponse,
    JobSearchStatusResponse,
    MatchingOutcome,
    SourceOutcome,
)
from app.services import embedding, matching, query_rendering
from app.services import sources as sources_service

logger = logging.getLogger(__name__)


def _validate_queries(payload: JobSearchRequest, selected: list[JobSource]) -> None:
    for name in payload.source_queries or {}:
        if registry.get_source(name) is None:
            raise UnknownJobSourceError(f"unknown job source: {name}")
    for source in selected:
        spec = (payload.source_queries or {}).get(source.name)
        if spec is not None:
            validate_source_options(source.filters(), spec.options, source.name)
            if spec.has_content():
                continue
        if payload.query:
            continue
        raise MissingSearchQueryError(f"no search query for source: {source.name}")


async def _selected_sources(session: AsyncSession, payload: JobSearchRequest) -> list[JobSource]:
    for name in payload.sources or []:
        if registry.get_source(name) is None:
            raise UnknownJobSourceError(f"unknown job source: {name}")
    enabled = {source.name: source for source in await sources_service.enabled_sources(session)}
    selected: list[JobSource] = []
    if payload.sources is None:
        selected = list(enabled.values())
    else:
        for name in payload.sources:
            source = enabled.get(name)
            if source is None:
                raise JobSourceNotEnabledError(f"job source is not enabled: {name}")
            selected.append(source)
    if not selected:
        raise NoJobSourcesConfiguredError()
    return selected


async def _require_profile(session: AsyncSession, profile_id: uuid.UUID | None) -> Profile:
    if profile_id is None:
        raise MissingProfileIdError()
    profile = await session.get(Profile, profile_id)
    if profile is None:
        raise ProfileNotFoundError()
    return profile


async def start_search(
    session: AsyncSession, background_tasks: BackgroundTasks, payload: JobSearchRequest
) -> JobSearchStartResponse:
    await _require_profile(session, payload.profile_id)
    selected = await _selected_sources(session, payload)
    _validate_queries(payload, selected)
    run = JobSearch(
        status=JobSearchStatus.pending,
        profile_id=payload.profile_id,
        query=payload.model_dump(mode="json"),
    )
    session.add(run)
    await session.flush()
    background_tasks.add_task(run_search, run.id, payload)
    logger.info(
        "ingestion.start search_id=%s sources=%s", run.id, [source.name for source in selected]
    )
    return JobSearchStartResponse(search_id=run.id, status=run.status.value)


async def run_search(search_id: uuid.UUID, payload: JobSearchRequest) -> None:
    started = time.monotonic()
    async with session_factory() as session:
        run = await session.get(JobSearch, search_id)
        if run is None:
            logger.error("ingestion.run search_id=%s missing", search_id)
            return
        run.status = JobSearchStatus.running
        await session.commit()

        try:
            selected = await _selected_sources(session, payload)
            _validate_queries(payload, selected)
        except DomainError as exc:
            run.status = JobSearchStatus.failed
            run.results = [
                SourceOutcome(source="run", status="failed", warning=exc.detail).model_dump(
                    mode="json"
                )
            ]
            await session.commit()
            logger.warning("ingestion.run search_id=%s selection failed: %s", search_id, exc.detail)
            return

        outcomes: list[SourceOutcome] = []
        for source in selected:
            outcomes.append(await _run_source(session, source, payload, search_id))

        ok = [outcome for outcome in outcomes if outcome.status == "ok"]
        run.results = [outcome.model_dump(mode="json") for outcome in outcomes]
        run.status = (
            JobSearchStatus.succeeded
            if outcomes and len(ok) == len(outcomes)
            else JobSearchStatus.partial
            if ok
            else JobSearchStatus.failed
        )
        run.matching = (await _run_matching(session, run.profile_id)).model_dump(mode="json")
        await session.commit()

    logger.info(
        "ingestion.done search_id=%s status=%s duration_ms=%.0f",
        search_id,
        run.status.value,
        (time.monotonic() - started) * 1000,
    )


async def _run_matching(session: AsyncSession, profile_id: uuid.UUID) -> MatchingOutcome:
    try:
        return await matching.refresh_matches_for_profile(session, profile_id)
    except Exception:
        logger.exception("matching stage failed for search run")
        return MatchingOutcome(status="failed", warning="matching stage failed unexpectedly")


async def _run_source(
    session: AsyncSession, source: JobSource, payload: JobSearchRequest, search_id: uuid.UUID
) -> SourceOutcome:
    source_started = time.monotonic()
    query = query_rendering.build_connector_query(
        source.name,
        (payload.source_queries or {}).get(source.name),
        payload.query,
        payload,
    )
    try:
        raw_postings = await source.search(query)
    except ConnectorError as exc:
        logger.warning("ingestion source=%s failed: %s", source.name, exc)
        return SourceOutcome(source=source.name, status="failed", warning=str(exc))

    persisted = 0
    skipped = 0
    normalized: list[JobPostingData] = []
    for raw in raw_postings:
        try:
            data = source.normalize(raw)
        except (ConnectorError, ValidationError):
            skipped += 1
            continue
        normalized.append(data)

    embeddings: list[list[float] | None] = [None] * len(normalized)
    embed_warning: str | None = None
    try:
        embeddings = await embedding.embed_postings(normalized)
    except LLMError as exc:
        embed_warning = f"embeddings unavailable: {exc}"
        logger.warning("ingestion source=%s embedding failed: %s", source.name, exc)

    for data, vector in zip(normalized, embeddings, strict=True):
        await _upsert_posting(session, source.name, data, search_id, vector)
    persisted = len(normalized)
    await session.commit()

    warning = f"{skipped} posting(s) skipped (un-mappable)" if skipped else None
    if embed_warning:
        warning = f"{warning}; {embed_warning}" if warning else embed_warning

    logger.info(
        "ingestion source=%s duration_ms=%.0f fetched=%d persisted=%d skipped=%d",
        source.name,
        (time.monotonic() - source_started) * 1000,
        len(raw_postings),
        persisted,
        skipped,
    )
    return SourceOutcome(
        source=source.name,
        status="ok",
        count=persisted,
        warning=warning,
    )


async def _upsert_posting(
    session: AsyncSession,
    source_name: str,
    data: JobPostingData,
    search_id: uuid.UUID,
    embedding_vector: list[float] | None,
) -> None:
    stmt = (
        pg_insert(JobPosting)
        .values(
            source=source_name,
            external_id=data.external_id,
            title=data.title,
            company=data.company,
            url=data.url,
            location=data.location,
            job_type=data.job_type,
            remote_type=data.remote_type,
            description=data.description,
            embedding=embedding_vector,
            posted_at=data.posted_at,
            expires_at=data.expires_at,
            is_closed=data.is_closed,
            salary_min=data.salary_min,
            salary_max=data.salary_max,
            currency=data.currency.upper() if data.currency else None,
            raw_payload=data.raw_payload,
            fetched_at=datetime.now(UTC),
        )
        .returning(JobPosting.id)
    )
    stmt = stmt.on_conflict_do_update(
        constraint="uq_job_posting_source_external_id",
        set_={
            "title": stmt.excluded.title,
            "company": stmt.excluded.company,
            "url": stmt.excluded.url,
            "location": stmt.excluded.location,
            "job_type": stmt.excluded.job_type,
            "remote_type": stmt.excluded.remote_type,
            "description": stmt.excluded.description,
            "embedding": stmt.excluded.embedding,
            "posted_at": stmt.excluded.posted_at,
            "expires_at": stmt.excluded.expires_at,
            "is_closed": stmt.excluded.is_closed,
            "salary_min": stmt.excluded.salary_min,
            "salary_max": stmt.excluded.salary_max,
            "currency": stmt.excluded.currency,
            "raw_payload": stmt.excluded.raw_payload,
            "fetched_at": stmt.excluded.fetched_at,
        },
    )
    posting_id = (await session.execute(stmt)).scalar_one()
    await session.execute(
        pg_insert(SearchPosting)
        .values(search_id=search_id, posting_id=posting_id)
        .on_conflict_do_nothing(constraint="uq_search_posting_search_posting")
    )


async def _require_owned_search(
    session: AsyncSession, search_id: uuid.UUID, profile_id: uuid.UUID | None
) -> JobSearch:
    run = await session.get(JobSearch, search_id)
    if run is None or run.profile_id != profile_id:
        raise JobSearchNotFoundError()
    return run


async def get_search_status(
    session: AsyncSession, search_id: uuid.UUID, profile_id: uuid.UUID
) -> JobSearchStatusResponse:
    run = await _require_owned_search(session, search_id, profile_id)
    results = [SourceOutcome.model_validate(item) for item in (run.results or [])]
    matching = MatchingOutcome.model_validate(run.matching) if run.matching else None
    return JobSearchStatusResponse(
        search_id=run.id,
        status=run.status.value,
        query=run.query,
        results=results,
        matching=matching,
        created_at=run.created_at,
        updated_at=run.updated_at,
    )


async def get_search_postings(
    session: AsyncSession, search_id: uuid.UUID, profile_id: uuid.UUID
) -> list[JobPostingSummary]:
    await _require_owned_search(session, search_id, profile_id)
    result = await session.execute(
        select(JobPosting)
        .join(SearchPosting, SearchPosting.posting_id == JobPosting.id)
        .where(SearchPosting.search_id == search_id, matching.freshness_condition())
        .order_by(JobPosting.posted_at.desc().nulls_last(), JobPosting.title)
    )
    return [JobPostingSummary.from_posting(posting) for posting in result.scalars().all()]


async def get_posting_detail(session: AsyncSession, posting_id: uuid.UUID) -> JobPostingDetail:
    posting = await session.get(JobPosting, posting_id)
    if posting is None:
        raise JobPostingNotFoundError()
    return JobPostingDetail.from_posting(posting)
