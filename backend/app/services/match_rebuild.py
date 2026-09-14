import logging
import time
import uuid

from fastapi import BackgroundTasks
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import session_factory
from app.core.errors import (
    MatchRebuildNotFoundError,
    ProfileNotEmbeddedError,
    ProfileNotFoundError,
)
from app.models import MatchRebuild, MatchRebuildStatus, Profile
from app.schemas.matching import MatchRebuildStatusResponse
from app.services import embedding, matching

logger = logging.getLogger(__name__)


async def _require_profile(session: AsyncSession, profile_id: uuid.UUID) -> Profile:
    profile = await session.get(Profile, profile_id)
    if profile is None:
        raise ProfileNotFoundError()
    return profile


def _to_response(run: MatchRebuild) -> MatchRebuildStatusResponse:
    return MatchRebuildStatusResponse(
        id=run.id,
        profile_id=run.profile_id,
        status=run.status.value,
        corpus_count=run.corpus_count,
        scored_count=run.scored_count,
        warning=run.warning,
        created_at=run.created_at,
        updated_at=run.updated_at,
    )


async def start_rebuild(
    session: AsyncSession, background_tasks: BackgroundTasks, profile_id: uuid.UUID
) -> MatchRebuildStatusResponse:
    profile = await _require_profile(session, profile_id)
    if profile.embedding is None:
        raise ProfileNotEmbeddedError()
    run = MatchRebuild(profile_id=profile_id, status=MatchRebuildStatus.pending)
    session.add(run)
    await session.flush()
    await session.refresh(run)
    background_tasks.add_task(run_rebuild, run.id)
    logger.info("matching.rebuild.start profile_id=%s run_id=%s", profile_id, run.id)
    return _to_response(run)


async def get_latest_rebuild(
    session: AsyncSession, profile_id: uuid.UUID
) -> MatchRebuildStatusResponse:
    await _require_profile(session, profile_id)
    run = (
        await session.execute(
            select(MatchRebuild)
            .where(MatchRebuild.profile_id == profile_id)
            .order_by(MatchRebuild.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if run is None:
        raise MatchRebuildNotFoundError()
    return _to_response(run)


async def run_rebuild(run_id: uuid.UUID) -> None:
    started = time.monotonic()
    async with session_factory() as session:
        run = await session.get(MatchRebuild, run_id)
        if run is None:
            logger.error("matching.rebuild run_id=%s missing", run_id)
            return
        profile_id = run.profile_id
        run.status = MatchRebuildStatus.running
        await session.commit()
        profile = await session.get(Profile, profile_id)
        if profile is None:
            run.status = MatchRebuildStatus.failed
            run.warning = "profile no longer exists"
            await session.commit()
            return
        try:
            await embedding.refresh_profile_embedding(profile)
            run.corpus_count = await matching.count_corpus_postings(session, profile_id)
            await matching.delete_out_of_corpus_matches(session, profile_id)
            outcome = await matching.rescore_and_rerank(session, profile)
            run.scored_count = outcome.scored_count
            run.status = MatchRebuildStatus.succeeded
            run.warning = outcome.warning
            await session.commit()
        except Exception:
            await session.rollback()
            logger.exception("matching.rebuild run_id=%s failed", run_id)
            run = await session.get(MatchRebuild, run_id)
            if run is None:
                return
            run.status = MatchRebuildStatus.failed
            run.warning = "rebuild failed unexpectedly"
            await session.commit()

    logger.info(
        "matching.rebuild.done run_id=%s profile_id=%s status=%s duration_ms=%.0f",
        run_id,
        profile_id,
        run.status.value,
        (time.monotonic() - started) * 1000,
    )
