import logging
import time
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import BackgroundTasks
from pydantic import ValidationError
from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.job_sources import registry
from app.adapters.job_sources.base import (
    ConnectorError,
    JobPostingData,
    JobSource,
    validate_source_options,
)
from app.adapters.llm import LLMError
from app.core.config import get_settings
from app.core.db import session_factory
from app.core.errors import (
    DomainError,
    DuplicateRunError,
    JobPostingNotFoundError,
    JobSearchNotFoundError,
    JobSourceNotEnabledError,
    MissingProfileIdError,
    MissingSearchCountryError,
    MissingSearchQueryError,
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
    JobSearchSummary,
    MatchingOutcome,
    SourceOutcome,
)
from app.schemas.profile import StructuredProfile
from app.services import embedding, matching, query_rendering
from app.services import sources as sources_service

logger = logging.getLogger(__name__)


def resolve_profile_defaults(payload: JobSearchRequest, profile: Profile) -> JobSearchRequest:
    """Fill omitted shared filters from the profile; request values always win."""
    structured = StructuredProfile.model_validate(profile.structured_profile)
    preferences = structured.preferences
    if payload.country is None and structured.contact.country is None:
        raise MissingSearchCountryError()
    update: dict[str, object] = {"country": payload.country or structured.contact.country}
    if payload.location is None and preferences is not None:
        update["location"] = preferences.target_location
    if preferences is not None:
        if payload.salary_min is None:
            update["salary_min"] = preferences.salary_min
        if payload.salary_max is None:
            update["salary_max"] = preferences.salary_max
        if payload.salary_currency is None:
            update["salary_currency"] = preferences.currency
        if payload.seniority is None and preferences.seniority is not None:
            update["seniority"] = preferences.seniority
    return payload.model_copy(update=update)


def _validate_queries(payload: JobSearchRequest, source: JobSource) -> None:
    spec = (payload.source_queries or {}).get(source.name)
    if spec is not None:
        validate_source_options(source.filters(), spec.options, source.name)
        if spec.has_content():
            return
    if payload.query:
        return
    raise MissingSearchQueryError(f"no search query for source: {source.name}")


async def _selected_source(session: AsyncSession, payload: JobSearchRequest) -> JobSource:
    source = registry.get_source(payload.source)
    if source is None:
        raise UnknownJobSourceError(f"unknown job source: {payload.source}")
    enabled = {
        enabled_source.name: enabled_source
        for enabled_source in await sources_service.enabled_sources(session)
    }
    selected = enabled.get(payload.source)
    if selected is None:
        raise JobSourceNotEnabledError(f"job source is not enabled: {payload.source}")
    return selected


async def _require_profile(session: AsyncSession, profile_id: uuid.UUID | None) -> Profile:
    if profile_id is None:
        raise MissingProfileIdError()
    profile = await session.get(Profile, profile_id)
    if profile is None:
        raise ProfileNotFoundError()
    return profile


ACTIVE_STATUSES = (JobSearchStatus.pending, JobSearchStatus.running)
_ABANDONED_WARNING = "run abandoned — in-flight lock released"


async def _sweep_stale_runs(session: AsyncSession) -> int:
    """Mark runs stuck in pending/running longer than max_run_age_minutes
    failed, releasing the one-active-run-per-(profile, source) lock (#36)."""
    settings = get_settings()
    cutoff = datetime.now(UTC) - timedelta(minutes=settings.max_run_age_minutes)
    stored_result = func.jsonb_build_array(
        func.jsonb_build_object(
            "source",
            func.coalesce(
                func.jsonb_extract_path_text(JobSearch.query, "source"),
                func.jsonb_extract_path_text(
                    func.jsonb_extract_path(JobSearch.query, "sources"), "0"
                ),
                "unknown",
            ),
            "status",
            "failed",
            "count",
            0,
            "warning",
            _ABANDONED_WARNING,
        )
    ).cast(JSONB)
    result = await session.execute(
        update(JobSearch)
        .where(JobSearch.status.in_(ACTIVE_STATUSES), JobSearch.updated_at < cutoff)
        .values(status=JobSearchStatus.failed, results=stored_result, updated_at=func.now())
    )
    swept = result.rowcount
    if swept:
        logger.info(
            "ingestion.sweep swept=%d max_run_age_minutes=%d",
            swept,
            settings.max_run_age_minutes,
        )
    return swept


def _select_active_run(profile_id: uuid.UUID, source_name: str):
    return (
        select(JobSearch)
        .where(
            JobSearch.profile_id == profile_id,
            JobSearch.source == source_name,
            JobSearch.status.in_(ACTIVE_STATUSES),
        )
        .order_by(JobSearch.updated_at.desc())
        .limit(1)
    )


async def _raise_if_duplicate_run(
    session: AsyncSession, profile_id: uuid.UUID, source_name: str
) -> None:
    row = (await session.execute(_select_active_run(profile_id, source_name))).scalar_one_or_none()
    if row is not None:
        logger.warning(
            "ingestion.duplicate profile_id=%s source=%s active_search=%s",
            profile_id,
            source_name,
            row.id,
        )
        raise DuplicateRunError(active_search_id=row.id)


async def start_search(
    session: AsyncSession, background_tasks: BackgroundTasks, payload: JobSearchRequest
) -> JobSearchStartResponse:
    profile = await _require_profile(session, payload.profile_id)
    profile_id = profile.id
    resolved = resolve_profile_defaults(payload, profile)
    source = await _selected_source(session, resolved)
    _validate_queries(resolved, source)
    await _sweep_stale_runs(session)
    await _raise_if_duplicate_run(session, profile_id, resolved.source)
    run = JobSearch(
        status=JobSearchStatus.pending,
        profile_id=profile_id,
        source=resolved.source,
        query=resolved.model_dump(mode="json"),
    )
    try:
        async with session.begin_nested():
            session.add(run)
            await session.flush()
    except IntegrityError as exc:
        row = (
            await session.execute(_select_active_run(profile_id, resolved.source))
        ).scalar_one_or_none()
        logger.warning(
            "ingestion.duplicate profile_id=%s source=%s raced the active-run index",
            profile_id,
            resolved.source,
        )
        raise DuplicateRunError(active_search_id=row.id if row is not None else None) from exc
    background_tasks.add_task(run_search, run.id, resolved)
    logger.info("ingestion.start search_id=%s source=%s", run.id, source.name)
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
            source = await _selected_source(session, payload)
            _validate_queries(payload, source)
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

        outcome = await _run_source(session, source, payload, search_id)
        outcomes: list[SourceOutcome] = [outcome]
        run.results = [item.model_dump(mode="json") for item in outcomes]
        run.status = JobSearchStatus.succeeded if outcome.status == "ok" else JobSearchStatus.failed
        run.matching = (await _matching_stage(session, run, outcome)).model_dump(mode="json")
        await session.commit()

    logger.info(
        "ingestion.done search_id=%s status=%s duration_ms=%.0f",
        search_id,
        run.status.value,
        (time.monotonic() - started) * 1000,
    )


async def _matching_stage(
    session: AsyncSession, run: JobSearch, outcome: SourceOutcome
) -> MatchingOutcome:
    """Re-score the profile corpus after ingestion — only when it can have changed."""
    if outcome.status != "ok" or outcome.count == 0:
        logger.info(
            "ingestion.matching skipped search_id=%s source_outcome=%s count=%d",
            run.id,
            outcome.status,
            outcome.count,
        )
        return MatchingOutcome(
            status="skipped",
            warning="no postings ingested by this run — matches kept as-is",
        )
    return await _run_matching(session, run.profile_id)


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


async def list_profile_searches(
    session: AsyncSession, profile_id: uuid.UUID
) -> list[JobSearchSummary]:
    """Recent runs for a profile (fresh first) — drives run banners after a reload."""
    await _require_profile(session, profile_id)
    result = await session.execute(
        select(JobSearch)
        .where(JobSearch.profile_id == profile_id)
        .order_by(JobSearch.created_at.desc())
        .limit(20)
    )
    runs = result.scalars().all()
    return [
        JobSearchSummary(
            search_id=run.id,
            status=run.status.value,
            results=[SourceOutcome.model_validate(item) for item in (run.results or [])],
            matching=MatchingOutcome.model_validate(run.matching) if run.matching else None,
            created_at=run.created_at,
            updated_at=run.updated_at,
        )
        for run in runs
    ]


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
