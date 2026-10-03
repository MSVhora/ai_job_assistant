import hashlib
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Literal, cast

from fastapi import BackgroundTasks
from sqlalchemy import Select, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.evidence_sources import registry
from app.adapters.evidence_sources.base import (
    EvidenceSource,
    EvidenceSourceError,
    EvidenceSourcePausedError,
)
from app.adapters.job_sources.base import json_object
from app.core.config import get_settings
from app.core.db import session_factory
from app.core.errors import (
    DisclosureRequiredError,
    DuplicateSyncError,
    EvidenceScopeNotFoundError,
    EvidenceSourceNotConfiguredError,
    EvidenceSourceUnavailableError,
    InvalidEmployerError,
    NoEnabledScopesError,
    SyncRunNotFoundError,
)
from app.core.pagination import DEFAULT_PAGE, Pagination
from app.models import (
    Candidate,
    EvidenceItem,
    EvidenceItemStatus,
    EvidenceKind,
    EvidenceScope,
    EvidenceSourceAccount,
    EvidenceSyncRun,
    SyncStatus,
)
from app.schemas.evidence import (
    EmployerOption,
    EvidenceItemData,
    EvidenceStatusResponse,
    ScopeCandidate,
    ScopeResponse,
    ScopeState,
    ScopeUpdateRequest,
    SyncPage,
    SyncRunResponse,
    SyncStartResponse,
)
from app.services.achievement_review import apply_scope_employer, mark_stale_after_sync
from app.services.employer_mapping import (
    load_profile_facts,
    normalize_employer_ref,
    suggest_for_scope,
)
from app.services.evidence_chunks import rebuild_chunks_background
from app.services.evidence_pipeline.dedupe import SQUASH_REASON
from app.services.evidence_pipeline.noise import classify
from app.services.resume_service import get_or_create_candidate

if TYPE_CHECKING:
    from sqlalchemy.engine import CursorResult

logger = logging.getLogger(__name__)

SyncMode = Literal["incremental", "full"]
SOURCE_KIND = "github"
ACTIVE_STATUSES = (SyncStatus.pending, SyncStatus.running)
ABANDONED_ERROR = "run abandoned - in-flight lock released"
STORAGE_WARNING = "could not store evidence"
ITEM_UPDATE_COLUMNS = (
    "scope_id",
    "project_key",
    "title",
    "body",
    "url",
    "occurred_at",
    "authored_by_user",
    "status",
    "filter_reason",
    "is_private",
    "meta",
    "content_hash",
)


async def _candidate_id(session: AsyncSession) -> uuid.UUID | None:
    return (await session.execute(select(Candidate.id).limit(1))).scalars().first()


def _select_account(candidate_id: uuid.UUID) -> Select[tuple[EvidenceSourceAccount]]:
    return select(EvidenceSourceAccount).where(
        EvidenceSourceAccount.candidate_id == candidate_id,
        EvidenceSourceAccount.kind == SOURCE_KIND,
    )


async def _get_or_create_account(
    session: AsyncSession, candidate_id: uuid.UUID
) -> EvidenceSourceAccount:
    account = (await session.execute(_select_account(candidate_id))).scalar_one_or_none()
    if account is not None:
        return account
    try:
        async with session.begin_nested():
            account = EvidenceSourceAccount(candidate_id=candidate_id, kind=SOURCE_KIND)
            session.add(account)
            await session.flush()
    except IntegrityError:
        return (await session.execute(_select_account(candidate_id))).scalar_one()
    return account


def _require_source() -> EvidenceSource:
    source = registry.get_source(SOURCE_KIND)
    if not source.is_configured():
        raise EvidenceSourceNotConfiguredError
    return source


def _run_response(run: EvidenceSyncRun) -> SyncRunResponse:
    return SyncRunResponse(
        id=run.id,
        status=run.status.value,
        mode=str(run.progress.get("mode", "incremental")),
        progress=run.progress,
        rate_limit=run.rate_limit,
        resume_at=run.resume_at,
        error=run.error,
        usage=run.usage,
        created_at=run.created_at,
        updated_at=run.updated_at,
    )


def _scope_response(
    scope: EvidenceScope,
    live: ScopeCandidate | None,
    *,
    is_new: bool,
    suggested: dict[str, object] | None = None,
) -> ScopeResponse:
    return ScopeResponse(
        ref=scope.ref,
        is_private=scope.is_private,
        is_fork=live.is_fork if live else False,
        description=live.description if live else None,
        pushed_at=live.pushed_at if live else None,
        enabled=scope.enabled,
        is_new=is_new,
        content_level=scope.content_level,
        sync_state=scope.sync_state.value,
        last_synced_at=scope.last_synced_at,
        employer_ref=scope.employer_ref,
        suggested_employer=suggested,
    )


async def _stored_scopes(session: AsyncSession, source_id: uuid.UUID) -> dict[str, EvidenceScope]:
    rows = (
        (await session.execute(select(EvidenceScope).where(EvidenceScope.source_id == source_id)))
        .scalars()
        .all()
    )
    return {scope.ref: scope for scope in rows}


async def get_status(session: AsyncSession) -> EvidenceStatusResponse:
    configured = registry.get_source(SOURCE_KIND).is_configured()
    candidate_id = await _candidate_id(session)
    account = None
    if candidate_id is not None:
        account = (await session.execute(_select_account(candidate_id))).scalar_one_or_none()
    if account is None:
        return EvidenceStatusResponse(
            configured=configured,
            login=None,
            acknowledged_at=None,
            last_synced_at=None,
            scopes_total=0,
            scopes_enabled=0,
            scopes_unmapped=0,
            latest_sync=None,
        )
    scopes = await _stored_scopes(session, account.id)
    latest = (
        await session.execute(
            select(EvidenceSyncRun)
            .where(EvidenceSyncRun.source_id == account.id)
            .order_by(EvidenceSyncRun.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    return EvidenceStatusResponse(
        configured=configured,
        login=account.account_login,
        acknowledged_at=account.acknowledged_at,
        last_synced_at=account.last_synced_at,
        scopes_total=len(scopes),
        scopes_enabled=sum(1 for scope in scopes.values() if scope.enabled),
        scopes_unmapped=sum(
            1
            for scope in scopes.values()
            if scope.enabled and scope.employer_ref is None and scope.last_synced_at is not None
        ),
        latest_sync=_run_response(latest) if latest is not None else None,
    )


async def _suggestions(
    session: AsyncSession, candidate_id: uuid.UUID, scopes: list[EvidenceScope]
) -> dict[uuid.UUID, dict[str, object]]:
    """Suggested employer per unmapped scope, from its authored-item date span."""
    unmapped = [scope for scope in scopes if scope.employer_ref is None]
    if not unmapped:
        return {}
    spans = (
        await session.execute(
            select(
                EvidenceItem.scope_id,
                func.min(EvidenceItem.occurred_at),
                func.max(EvidenceItem.occurred_at),
            )
            .where(
                EvidenceItem.candidate_id == candidate_id,
                EvidenceItem.kind.in_((EvidenceKind.commit, EvidenceKind.pull_request)),
                EvidenceItem.scope_id.in_([scope.id for scope in unmapped]),
            )
            .group_by(EvidenceItem.scope_id)
        )
    ).all()
    experiences = (await load_profile_facts(session, candidate_id)).experiences
    suggestions: dict[uuid.UUID, dict[str, object]] = {}
    for scope_id, first, last in spans:
        suggestion = suggest_for_scope(
            first.date() if first else None, last.date() if last else None, experiences
        )
        if scope_id is not None and suggestion is not None:
            suggestions[scope_id] = suggestion
    return suggestions


async def list_scopes(session: AsyncSession) -> list[ScopeResponse]:
    source = _require_source()
    candidate = await get_or_create_candidate(session)
    account = await _get_or_create_account(session, candidate.id)
    try:
        identity = await source.identify()
        live = await source.list_scopes()
    except EvidenceSourceError as exc:
        logger.warning("evidence.scopes failed error_type=%s", type(exc).__name__)
        raise EvidenceSourceUnavailableError(str(exc)) from exc
    account.account_login = identity.login
    stored = await _stored_scopes(session, account.id)
    new_refs: set[str] = set()
    matched: list[tuple[EvidenceScope, ScopeCandidate]] = []
    for candidate_scope in live:
        scope = stored.pop(candidate_scope.ref, None)
        if scope is None:
            scope = EvidenceScope(
                source_id=account.id,
                ref=candidate_scope.ref,
                is_private=candidate_scope.is_private,
                enabled=False,
            )
            session.add(scope)
            new_refs.add(candidate_scope.ref)
        scope.is_private = candidate_scope.is_private
        matched.append((scope, candidate_scope))
    await session.flush()
    everything = [scope for scope, _ in matched] + list(stored.values())
    suggestions = await _suggestions(session, candidate.id, everything)
    responses = [
        _scope_response(
            scope,
            candidate_scope,
            is_new=scope.ref in new_refs,
            suggested=suggestions.get(scope.id),
        )
        for scope, candidate_scope in matched
    ]
    responses.extend(
        _scope_response(scope, None, is_new=False, suggested=suggestions.get(scope.id))
        for scope in stored.values()
    )
    return responses


async def update_scopes(session: AsyncSession, payload: ScopeUpdateRequest) -> list[ScopeResponse]:
    candidate = await get_or_create_candidate(session)
    account = await _get_or_create_account(session, candidate.id)
    stored = await _stored_scopes(session, account.id)
    missing = [item.ref for item in payload.scopes if item.ref not in stored]
    if missing:
        raise EvidenceScopeNotFoundError
    enabling_private = any(item.enabled and stored[item.ref].is_private for item in payload.scopes)
    if enabling_private and account.acknowledged_at is None:
        if not payload.acknowledged_disclosure:
            raise DisclosureRequiredError
        account.acknowledged_at = datetime.now(UTC)
    experiences = (await load_profile_facts(session, candidate.id)).experiences
    employers: dict[str, dict[str, object] | None] = {}
    for item in payload.scopes:
        if "employer_ref" in item.model_fields_set:
            try:
                employers[item.ref] = normalize_employer_ref(item.employer_ref, experiences)
            except ValueError as exc:
                raise InvalidEmployerError from exc
    updated: list[ScopeResponse] = []
    for item in payload.scopes:
        scope = stored[item.ref]
        if item.enabled is not None:
            scope.enabled = item.enabled
        if item.content_level is not None:
            scope.content_level = item.content_level
        if item.ref in employers:
            scope.employer_ref = employers[item.ref]
            await apply_scope_employer(session, candidate.id, scope.ref, employers[item.ref])
        updated.append(_scope_response(scope, None, is_new=False))
    await session.flush()
    return updated


async def employer_options(session: AsyncSession) -> list[EmployerOption]:
    candidate_id = await _candidate_id(session)
    options: list[EmployerOption] = []
    if candidate_id is not None:
        for experience in (await load_profile_facts(session, candidate_id)).experiences:
            label = f"{experience.company} ({experience.start_raw or 'dates unknown'})"
            options.append(
                EmployerOption(
                    kind="experience",
                    label=label,
                    company=experience.company,
                    start_date=experience.start_raw,
                )
            )
    options.append(EmployerOption(kind="personal", label="Personal / open source"))
    return options


def _select_active_run(source_id: uuid.UUID) -> Select[tuple[EvidenceSyncRun]]:
    return (
        select(EvidenceSyncRun)
        .where(EvidenceSyncRun.source_id == source_id, EvidenceSyncRun.status.in_(ACTIVE_STATUSES))
        .order_by(EvidenceSyncRun.updated_at.desc())
        .limit(1)
    )


async def _sweep_stale_runs(session: AsyncSession) -> int:
    """Fail runs stuck pending/running past `max_run_age_minutes`, releasing the run guard."""
    settings = get_settings()
    cutoff = datetime.now(UTC) - timedelta(minutes=settings.max_run_age_minutes)
    result = cast(
        "CursorResult[tuple[()]]",
        await session.execute(
            update(EvidenceSyncRun)
            .where(EvidenceSyncRun.status.in_(ACTIVE_STATUSES), EvidenceSyncRun.updated_at < cutoff)
            .values(status=SyncStatus.failed, error=ABANDONED_ERROR)
        ),
    )
    if result.rowcount:
        logger.info("evidence.sweep swept=%d", result.rowcount)
    return result.rowcount


async def _raise_if_duplicate_run(session: AsyncSession, source_id: uuid.UUID) -> None:
    active = (await session.execute(_select_active_run(source_id))).scalar_one_or_none()
    if active is not None:
        logger.warning("evidence.duplicate active_sync=%s", active.id)
        raise DuplicateSyncError(active_sync_id=active.id)


async def start_sync(
    session: AsyncSession, background_tasks: BackgroundTasks, mode: SyncMode
) -> SyncStartResponse:
    _require_source()
    candidate = await get_or_create_candidate(session)
    account = await _get_or_create_account(session, candidate.id)
    enabled = (
        await session.execute(
            select(func.count())
            .select_from(EvidenceScope)
            .where(EvidenceScope.source_id == account.id, EvidenceScope.enabled.is_(True))
        )
    ).scalar_one()
    if enabled == 0:
        raise NoEnabledScopesError
    await _sweep_stale_runs(session)
    await _raise_if_duplicate_run(session, account.id)
    run = EvidenceSyncRun(
        source_id=account.id,
        status=SyncStatus.pending,
        progress={"mode": mode, "scopes": {}, "items": 0, "warnings": []},
    )
    try:
        async with session.begin_nested():
            session.add(run)
            await session.flush()
    except IntegrityError as exc:
        raced = (await session.execute(_select_active_run(account.id))).scalar_one_or_none()
        logger.warning("evidence.duplicate raced the active-run index")
        raise DuplicateSyncError(active_sync_id=raced.id if raced is not None else None) from exc
    background_tasks.add_task(run_sync, run.id, mode)
    logger.info("evidence.start sync_id=%s mode=%s", run.id, mode)
    return SyncStartResponse(sync_id=run.id, status=run.status.value)


@dataclass
class _RunOutcome:
    items: int = 0
    scopes_ok: int = 0
    scopes_failed: int = 0
    warnings: list[str] = field(default_factory=list[str])
    paused: EvidenceSourcePausedError | None = None
    chunks: dict[str, object] | None = None
    stale_flagged: int | None = None


def _content_hash(item: EvidenceItemData) -> str:
    canonical = json.dumps(
        [
            item.kind.value,
            item.external_id,
            item.title,
            item.body,
            item.url,
            item.occurred_at.isoformat() if item.occurred_at else None,
            item.meta,
        ],
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def _item_row(
    item: EvidenceItemData, candidate_id: uuid.UUID, scope: EvidenceScope, bots: list[str]
) -> dict[str, object]:
    verdict = classify(item, bots)
    return {
        "candidate_id": candidate_id,
        "scope_id": scope.id,
        "kind": item.kind,
        "external_id": item.external_id,
        "project_key": item.project_key,
        "title": item.title,
        "body": item.body,
        "url": item.url,
        "occurred_at": item.occurred_at,
        "authored_by_user": item.authored_by_user,
        "status": EvidenceItemStatus.kept if verdict.kept else EvidenceItemStatus.filtered,
        "filter_reason": verdict.reason,
        "is_private": scope.is_private,
        "meta": item.meta,
        "content_hash": _content_hash(item),
    }


async def _store_items(
    session: AsyncSession,
    candidate_id: uuid.UUID,
    scope: EvidenceScope,
    items: list[EvidenceItemData],
) -> tuple[int, int]:
    bots = get_settings().evidence_bot_logins
    rows: dict[tuple[str, str], dict[str, object]] = {}
    for item in items:
        rows[(item.kind.value, item.external_id)] = _item_row(item, candidate_id, scope, bots)
    if not rows:
        return 0, 0
    statement = insert(EvidenceItem).values(list(rows.values()))
    excluded = statement.excluded
    await session.execute(
        statement.on_conflict_do_update(
            constraint="uq_evidence_item_candidate_kind_external",
            set_={column: excluded[column] for column in ITEM_UPDATE_COLUMNS},
            where=EvidenceItem.content_hash != excluded.content_hash,
        )
    )
    filtered = sum(1 for row in rows.values() if row["status"] is EvidenceItemStatus.filtered)
    return len(rows), filtered


async def _attach_squash_commits(session: AsyncSession, candidate_id: uuid.UUID, ref: str) -> None:
    """Standalone commits that are a PR's merge commit belong to the PR, not to the tally."""
    merge_oid = func.jsonb_extract_path_text(EvidenceItem.meta, "merge_commit_oid")
    number = func.jsonb_extract_path_text(EvidenceItem.meta, "number")
    pull_requests = (
        await session.execute(
            select(merge_oid, number).where(
                EvidenceItem.candidate_id == candidate_id,
                EvidenceItem.kind == EvidenceKind.pull_request,
                EvidenceItem.project_key == ref,
                merge_oid.is_not(None),
            )
        )
    ).all()
    for oid, pr_number in pull_requests:
        await session.execute(
            update(EvidenceItem)
            .where(
                EvidenceItem.candidate_id == candidate_id,
                EvidenceItem.kind == EvidenceKind.commit,
                EvidenceItem.external_id == oid,
                EvidenceItem.status == EvidenceItemStatus.kept,
                func.jsonb_extract_path_text(EvidenceItem.meta, "pr_number").is_(None),
            )
            .values(
                status=EvidenceItemStatus.filtered,
                filter_reason=SQUASH_REASON,
                meta=EvidenceItem.meta.op("||")(
                    func.jsonb_build_object("pr_number", int(pr_number or 0))
                ),
            )
        )


def _scope_items(entry: object) -> int:
    value = (json_object(entry) or {}).get("items", 0)
    return value if isinstance(value, int) else 0


def _merge_progress(
    run: EvidenceSyncRun, ref: str, page: SyncPage | None, scope_update: dict[str, object]
) -> None:
    progress = dict(run.progress)
    scopes = dict(json_object(progress.get("scopes")) or {})
    entry = dict(json_object(scopes.get(ref)) or {})
    entry.update(scope_update)
    scopes[ref] = entry
    progress["scopes"] = scopes
    progress["items"] = sum(_scope_items(value) for value in scopes.values())
    run.progress = progress
    if page is not None:
        usage = dict(run.usage)
        usage["requests"] = int(cast("int", usage.get("requests", 0))) + page.requests_used
        run.usage = usage
        rate_limit = dict(run.rate_limit)
        for info in page.rate_limits:
            rate_limit[info.api] = info.model_dump(mode="json")
        run.rate_limit = rate_limit


@dataclass
class _ScopeResult:
    items: int = 0
    warning: str | None = None
    paused: EvidenceSourcePausedError | None = None


async def _sync_scope(
    run_id: uuid.UUID,
    scope_id: uuid.UUID,
    candidate_id: uuid.UUID,
    source: EvidenceSource,
    mode: SyncMode,
) -> _ScopeResult:
    result = _ScopeResult()
    async with session_factory() as session:
        scope = await session.get(EvidenceScope, scope_id)
        run = await session.get(EvidenceSyncRun, run_id)
        if scope is None or run is None:
            return result
        ref = scope.ref
        if mode == "full":
            scope.cursor = {}
        scope.sync_state = SyncStatus.running
        _merge_progress(run, ref, None, {"status": "running", "items": 0, "filtered": 0})
        await session.commit()
        state = ScopeState(
            ref=ref,
            is_private=scope.is_private,
            content_level=scope.content_level,
            cursor=scope.cursor,
        )
        stored = filtered = 0
        try:
            async for page in source.sync_scope(state):
                count, dropped = await _store_items(session, candidate_id, scope, page.items)
                stored += count
                filtered += dropped
                if page.next_cursor is not None:
                    scope.cursor = page.next_cursor
                _merge_progress(
                    run, ref, page, {"status": "running", "items": stored, "filtered": filtered}
                )
                await session.commit()
            await _attach_squash_commits(session, candidate_id, ref)
            scope.sync_state = SyncStatus.succeeded
            scope.last_synced_at = datetime.now(UTC)
            _merge_progress(run, ref, None, {"status": "ok", "items": stored, "filtered": filtered})
            await session.commit()
            result.items = stored
        except EvidenceSourcePausedError as exc:
            await session.rollback()
            await _mark_scope(
                session, scope_id, run_id, _Mark(SyncStatus.paused, "paused", exc.reason)
            )
            result.items = stored
            result.paused = exc
        except (EvidenceSourceError, SQLAlchemyError) as exc:
            await session.rollback()
            warning = str(exc) if isinstance(exc, EvidenceSourceError) else STORAGE_WARNING
            logger.warning("evidence.scope failed error_type=%s", type(exc).__name__)
            await _mark_scope(
                session, scope_id, run_id, _Mark(SyncStatus.failed, "failed", warning)
            )
            result.items = stored
            result.warning = f"{ref}: {warning}"
    return result


@dataclass(frozen=True)
class _Mark:
    state: SyncStatus
    label: str
    warning: str


async def _mark_scope(
    session: AsyncSession, scope_id: uuid.UUID, run_id: uuid.UUID, mark: _Mark
) -> None:
    scope = await session.get(EvidenceScope, scope_id)
    run = await session.get(EvidenceSyncRun, run_id)
    if scope is None or run is None:
        return
    scope.sync_state = mark.state
    _merge_progress(run, scope.ref, None, {"status": mark.label, "warning": mark.warning})
    await session.commit()


async def run_sync(run_id: uuid.UUID, mode: SyncMode) -> None:
    started = time.monotonic()
    async with session_factory() as session:
        run = await session.get(EvidenceSyncRun, run_id)
        if run is None:
            logger.error("evidence.run sync_id=%s missing", run_id)
            return
        run.status = SyncStatus.running
        await session.commit()
        account = await session.get(EvidenceSourceAccount, run.source_id)
        if account is None:
            return
        candidate_id = account.candidate_id
        scope_ids = list(
            (
                await session.execute(
                    select(EvidenceScope.id)
                    .where(EvidenceScope.source_id == account.id, EvidenceScope.enabled.is_(True))
                    .order_by(EvidenceScope.ref)
                )
            )
            .scalars()
            .all()
        )
    outcome = _RunOutcome()
    source = registry.get_source(SOURCE_KIND)
    for scope_id in scope_ids:
        scope_result = await _sync_scope(run_id, scope_id, candidate_id, source, mode)
        outcome.items += scope_result.items
        if scope_result.paused is not None:
            outcome.paused = scope_result.paused
            break
        if scope_result.warning is not None:
            outcome.scopes_failed += 1
            outcome.warnings.append(scope_result.warning)
        else:
            outcome.scopes_ok += 1
    if outcome.scopes_ok or outcome.paused is not None:
        outcome.chunks = await _rebuild_chunks(candidate_id)
        outcome.stale_flagged = await _flag_stale(candidate_id)
    status = await _finish_run(run_id, outcome)
    logger.info(
        "evidence.done sync_id=%s status=%s items=%d duration_ms=%.0f",
        run_id,
        status.value,
        outcome.items,
        (time.monotonic() - started) * 1000,
    )


async def _rebuild_chunks(candidate_id: uuid.UUID) -> dict[str, object]:
    """Chunk and embed what the run stored; a failure degrades to a warning, never fails the run."""
    try:
        return (await rebuild_chunks_background(candidate_id)).as_progress()
    except SQLAlchemyError as exc:
        logger.warning("evidence.chunks failed error_type=%s", type(exc).__name__)
        return {"error": "could not build chunks"}


async def _flag_stale(candidate_id: uuid.UUID) -> int | None:
    """Approved achievements whose evidence changed get the re-review flag (never edited)."""
    try:
        async with session_factory() as session:
            flagged = await mark_stale_after_sync(session, candidate_id)
            await session.commit()
    except SQLAlchemyError as exc:
        logger.warning("evidence.stale failed error_type=%s", type(exc).__name__)
        return None
    return flagged


async def _finish_run(run_id: uuid.UUID, outcome: _RunOutcome) -> SyncStatus:
    async with session_factory() as session:
        run = await session.get(EvidenceSyncRun, run_id)
        if run is None:
            return SyncStatus.failed
        if outcome.paused is not None:
            status = SyncStatus.paused
            run.resume_at = outcome.paused.resume_at
            run.error = outcome.paused.reason
        elif outcome.scopes_failed and not outcome.scopes_ok:
            status = SyncStatus.failed
            run.error = "every repository failed - see the warnings"
        else:
            status = SyncStatus.succeeded
        progress = dict(run.progress)
        progress["warnings"] = outcome.warnings
        if outcome.chunks is not None:
            progress["chunks"] = outcome.chunks
        if outcome.stale_flagged is not None:
            progress["stale_flagged"] = outcome.stale_flagged
        run.progress = progress
        run.status = status
        if status is SyncStatus.succeeded:
            account = await session.get(EvidenceSourceAccount, run.source_id)
            if account is not None:
                account.last_synced_at = datetime.now(UTC)
        await session.commit()
        return status


async def get_sync(session: AsyncSession, sync_id: uuid.UUID) -> SyncRunResponse:
    candidate_id = await _candidate_id(session)
    run = await session.get(EvidenceSyncRun, sync_id)
    if run is None or candidate_id is None:
        raise SyncRunNotFoundError
    account = await session.get(EvidenceSourceAccount, run.source_id)
    if account is None or account.candidate_id != candidate_id:
        raise SyncRunNotFoundError
    return _run_response(run)


def _own_runs(candidate_id: uuid.UUID) -> Select[tuple[EvidenceSyncRun]]:
    return (
        select(EvidenceSyncRun)
        .join(EvidenceSourceAccount, EvidenceSourceAccount.id == EvidenceSyncRun.source_id)
        .where(EvidenceSourceAccount.candidate_id == candidate_id)
    )


async def count_syncs(session: AsyncSession) -> int:
    candidate_id = await _candidate_id(session)
    if candidate_id is None:
        return 0
    subquery = _own_runs(candidate_id).subquery()
    return (await session.execute(select(func.count()).select_from(subquery))).scalar_one()


async def list_syncs(
    session: AsyncSession, page: Pagination = DEFAULT_PAGE
) -> list[SyncRunResponse]:
    candidate_id = await _candidate_id(session)
    if candidate_id is None:
        return []
    rows = (
        (
            await session.execute(
                _own_runs(candidate_id)
                .order_by(EvidenceSyncRun.created_at.desc())
                .limit(page.limit)
                .offset(page.offset)
            )
        )
        .scalars()
        .all()
    )
    return [_run_response(run) for run in rows]
