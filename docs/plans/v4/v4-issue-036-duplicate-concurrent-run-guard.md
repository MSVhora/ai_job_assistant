# Issue #36 — Guard against duplicate concurrent runs of the same profile + source (M4 / Phase D)

**Status:** Planned
**Tracks:** GitHub issue #36 (milestone `v4`, Phase D / M4 — run hygiene)
**Plan of record:** [v4-search-relevance-plan.md](v4-search-relevance-plan.md) Problem 6 (this issue adds no multi-source behavior — one source per run remains intentional)
**Depends on:** #31–#35 implementation state only insofar as `start_search()` still takes a single `source` in `JobSearchRequest` (`schemas/job_search.py:87`) — no direct code dependency, but the plan assumes their branches land per sequencing (D comes after A–C)
**Blocks:** Phase E (#37+) — ingestion upserts must not race a duplicate run before hybrid scoring lands; also unblocks the "fan-out anything else" the plan warns about

---

## Goal

Nothing stops a user firing the same `(profile_id, source)` search twice while the
first run is still `pending`/`running`. Consequences: double Apify spend
(`limitPerSource`-billed), double Adzuna quota burn, and two ingestion runs
upserting the same postings concurrently.

Today `start_search()` (`services/ingestion.py:105-121`) does a background-task
fire-and-forget with no guard at all. There is also **no existing stale-run
handling** (grep confirms): a crashed worker leaves a `running` row forever,
which would make any in-flight lock leak.

Note the model mismatch: `JobSearch` (`models/job_search.py:44-61`) has **no
`source` column** — the source name lives only inside `query` JSONB
(`resolved.model_dump()` at `ingestion.py:115`), persisted after the
client-id isn't knowable at INSERT time. The enforcement surface must therefore
first materialize `source` onto the row.

## Locked decisions

| Decision | Choice | Rationale |
|---|---|---|
| Enforcement mechanism | **Partial unique index**: `CREATE UNIQUE INDEX uq_job_search_active_run ON job_search (profile_id, source) WHERE status IN ('pending', 'running')` — NOT advisory locks | The plan lists both; the index makes the constraint survive worker crashes/restarts without lock-reconciliation logic (advisory locks are session-scoped and silently vanish or get held forever depending on failure mode), it is declaratively visible in the schema, and it degrades to "SQL raises IntegrityError" which pytest can exercise directly |
| Schema change | `job_search` gains a **real `source` column** (`String`, nullable→NOT NULL after backfill), not `(query->>'source')` expression in the index | DB standard: queryable ⇒ column (we also want to filter on it later, e.g. run history UI). The model is the source of truth; one migration covers column + backfill + index. `query` JSONB remains the full resolved-request echo, unchanged |
| Backend status naming | Non-terminal statuses are `pending` and `running` (actual `JobSearchStatus` enum) — the plan-of-record's `queued` does not exist in this codebase; the Where-clause uses this pair | Match models to reality; the v1–v3 enum uses `pending` not `queued` |
| Where the pre-flight check lives | `start_search()` explicitly SELECTs an active run for the same pair **before** INSERT — to return the active run's id — but this check is advisory only; the index is the enforcement (race = IntegrityError on flush → same 409) | The SELECT alone is racy; the index closes the race. Rendering the 409 with the active id needs the lookup anyway; treating it as advisory keeps one code path for both outcomes |
| 409 shape | New `DuplicateRunError(DomainError)` (`status_code=409`, `default_detail="a run for this profile and source is already active"`), carrying `active_search_id`; `domain_error_handler` emits `{"detail": ..., "active_search_id": ...}` when set | UI must be able to point the user at the run, not just print a string. Extending the handler (not a router-level `HTTPException`) keeps error mapping central and typed |
| Flush-safety | `start_search()` wraps `session.flush()` in try/`IntegrityError` → translate to `DuplicateRunError` with the already-fetched active run id | `DbCommitMiddleware` commits on `http.response.start` — the IntegrityError surfaces at flush inside the service (before any response start), so the domain handler still runs; no rollback juggling beyond the middleware's rollback path |
| No multi-worker advisory-lock code | None | The index covers any worker count; this app is single-user/self-host anyway |
| Sweeper design | `max_run_age_minutes` in `Settings` (default 30); one bulk UPDATE at the top of `start_search()` marking `pending`/`running` rows with `updated_at < now() - max_run_age_minutes` as `failed` with a `SourceOutcome(source=<stored source>, status="failed", warning="run abandoned — in-flight lock released")` in `results` | Issue's point 4. Runs never take 30 min today (source search + matching stage); timed-out/stuck runs get reclaimed so the lock releases. A per-process throttle on the UPDATE is deferred — single-user deployment makes a cheap bulk UPDATE acceptable; revisit only if start latency ever matters |
| Stuck-run failure detail source | The sweeper reads `<stored query dict>["source"]` — the same echo `start_search` wrote — falling back to "unknown" if a pre-#36 row lacks it (before backfill made the column NOT NULL, `query.source` was always present, so this is belt-and-braces) | The `results` JSONB schema (`SourceOutcome`) requires the key; no model change needed for failed runs |
| Concurrency-safety of the sweeper's UPDATE vs the index | The sweeper UPDATE commits as part of the same request transaction, before the pre-flight SELECT; a running-but-fresh run is unaffected | ORDERING: sweep → select-active → insert. Two parallel restarts can't both sweep-then-insert because the index is still the arbiter |
| Frontend message | `startJobSearch` wrapper (new `DuplicateRunError extends ApiError` with `searchId` field, thrown by `lib/api/index.ts` when status is 409 and the body carries `active_search_id`); `SearchStepperModal` catches it in the existing `start.isError` slot: message "A search for this profile and source is already running" + a **"Go to active run"** button calling `onSearchStarted(error.searchId)` (mounted into the run-banner flow), which aborts the modal | The DoD says "message pointing to the active run." The pointer is the run id; reusing `onSearchStarted` plugs the run into the existing `RunBanner` polling UI with zero new UI states |
| `run_search` re-validation | Unchanged (`run_search` keeps validating source selection at task start; no second duplicate guard inside the task) | The task just reflects one row's reality; a task that wakes up on a `failed`-marked row is impossible by construction (the row failed-swept means the task never launched) |

## Scope

### Migration (one Alembic migration, models first)

`0017_add_job_search_source_and_active_run_unique_index`:

1. `op.add_column("job_search", sa.Column("source", sa.String(length=64), nullable=True))`.
2. Backfill (single bulk SQL, NOT row-by-row):
   `UPDATE job_search SET source = query->>'source' WHERE source IS NULL` —
   `query` has always carried `source` (request had it minimal-`1` since v1).
3. Set NOT NULL on `source`.
4. Partial unique index
   `uq_job_search_active_run ON (profile_id, source) WHERE status IN ('pending','running')`.
5. Downgrade: drop index, drop column. Docstring notes the destructive
   (backfilled) bit is the NOT NULL reversal on downgrade, not data loss.

Migration review checklist (per standards): no enum manipulation (`job_search_status` is untouched), no renames.

### Backend (`backend/app/`)

- `models/job_search.py`: add `source: Mapped[str]` (`String(length=64)`,
  non-nullable once migrated).
- `services/ingestion.py`:
  - `start_search()`: after `_validate_queries(resolved, source)`:
    1. `await _sweep_stale_runs(session)` (max_run_age check, bulk UPDATE; write `results` for swept rows from their stored `query.source`).
    2. Advisory SELECT for an active run on the same pair → if found, raise `DuplicateRunError(active_search_id=run.id)` **before** any INSERT.
    3. INSERT with the new `source` column set; catch `IntegrityError` on flush → re-raise as `DuplicateRunError(active_search_id=<re-fetched run id>)` (lookup by the same predicate, `updated_at DESC` tiebreak).
  - `_sweep_stale_runs()`: the bulk UPDATE implementing the sweeper (shared by nothing else; deliberately not a background task — start_search is the natural sweep point and a task would race the eventual duplicate guard).
- `core/errors.py`: `DuplicateRunError` with `active_search_id: uuid.UUID | None = None` attribute set post-construction.
- `main.py` / error handler registration: `domain_error_handler` updated to include `active_search_id` in the 409 JSON body when present (handler signature unchanged).
- `core/config.py`: `max_run_age_minutes: Annotated[int, Field(ge=1)] = 30`; `.env.example` gains `MAX_RUN_AGE_MINUTES=30` with a comment.
- `routers/jobs.py`: unchanged (service raises; handler maps). The 202 route gains no new params.
- `parseStructured`-style retry logic: none affected. JobSource connector code: untouched.

### OpenAPI / types

- Regenerate `frontend/lib/api/schema.d.ts` + `openapi.json` from the running
  backend after the 409-body change (the response body for `/api/jobs/search`
  gains an error variant; even though FastAPI doesn't model error bodies, the
  `JobSearchStartResponse` shape itself is unchanged).

### Frontend

- `lib/api/client.ts`: `DuplicateRunError extends ApiError { readonly searchId: string; }` (name≈`DuplicateRunError` in TS too). `errorMessage` unchanged; parsing lives in the caller.
- `lib/api/index.ts`: `startJobSearch()` wraps `apiFetch` — on response status 409, parse the JSON body and throw `DuplicateRunError(status, message, searchId)` instead of plain `ApiError`.
- `components/features/jobs/SearchStepperModal.tsx`: the existing `start.isError` block special-cases `error instanceof DuplicateRunError` to render:
  `A search for this profile and source is already running.` + a `Button` (secondary variant, type="button") "Go to active run" → `onSearchStarted(error.searchId)` then `onOpenChange(false)`.
  The plain `error.message` line remains as the fallback for other failures.
- No other feature component changes: `RunBanner` / `RunBanners` already render active runs by id; the 409 path simply funnels the user into them.

### Tests

Backend (`backend/tests/`, scratch Postgres via `migrated_database` — no SQLite):

- `test_ingestion.py`:
  - happy-path start works with the new `source` column written (assert row source persisted).
  - duplicate start: insert an active run for `(profile, source)` then start again → `DuplicateRunError` raised with the right `active_search_id` (409 via handler); **same pair, but first run terminal (`succeeded`) → 202** (no false positive); **different source, same profile → 202**; **different profile, same source → 202**.
  - sweeper: row `running` older than `max_run_age_minutes` → start succeeds, stale row is marked `failed` with abandonment warning; fresh `running` row still blocks.
  - no stale-run sweep on every call path except `start_search` (start of `run_search` untouched).
- `test_job_endpoints.py`: route-level 409 body asserts `active_search_id` present (httpx against the app).
- New `test_duplicate_run_concurrency.py` (named in the DoD): two concurrent `start_search` calls (asyncio.gather, two sessions, same profile+source):
  - exactly one returns 202 / one raises `DuplicateRunError` (or, if both went through the advisory SELECT, the index rejects the loser at flush — the test must prove whichever path wins the race can never emit two inserts);
  - race-path test with the pre-flight SELECT monkeypatched to a no-op: the loser's INSERT hits the index → `IntegrityError` is translated to `DuplicateRunError` (proves the index path alone is intact).
- `test_migrations.py`: `0017` up applies (column, backfill, partial index exist); downgrade removes index cleanly; the model-first round trip is exercised by the shared version chain.
- `test_source_*` / connector tests: excluded — no connector behavior changes.

### Gates

- Backend: `ruff check . && ruff format --check . && pytest` green in `backend/`.
- Frontend: `npm run lint && npm run build` green in `frontend/` (OpenAPI shapes regenerated, not hand-written).
- Migration ships in the same change as the model edit (same PR).
- `.env.example`: new `MAX_RUN_AGE_MINUTES`.
- Docs: `docs/guide/03-job-discovery-and-matching.md` documents the "one active run per profile+source" behavior + the Go-to-active-run UI; `docs/architecture.md` run-lifecycle notes the partial unique index + sweeper; re-render diagrams via `node scripts/render-diagrams.mjs` only if the run-lifecycle diagram actually changes (likely: add the 409/lock edge to the search run sequence diagram).

## Risks

| Risk | Mitigation |
|---|---|
| Racy parallel start requests hide the "second INSERT is fine" false-positive | Concurrency test pins the invariant; the index makes the error surface at flush synchronously (no post-commit cleanup window) |
| Dual-check drift: pre-flight SELECT says "no active run" but INSERT loses the race → attempted re-fetch finds nothing (row vanished mid-flight, e.g. swept concurrently) | Re-fetch uses the same predicate; on empty lookup, fall back to a detail-only 409 (message without id) — UI already handles missing searchId gracefully (plain ApiError-style message) |
| Long-running legitimate searches swept (~> default 30 min) | A single run is a connector call + matching — realistically minutes; `MAX_RUN_AGE_MINUTES` is tunable via .env and documented; sweeping increments a log line (`ingestion.sweep count=N duration=…`) so long-run casualties are visible |
| Backfill misses rows (source never in `query` JSONB) | Belt-and-braces: safe fallback `UPDATE ... WHERE source IS NULL AND query ? 'source'` only — the primary statement (no WHERE beyond `source IS NULL`) uses `query->>'source'` which yields NULL → still NULL → NOT NULL apply should be written as *verify zero-remaining* after the first pass, in the migration itself, failing loudly if any row can't be backfilled |
| `updated_at` staleness for sinks where `onupdate=func.now()` server default vs SQLAlchemy-side `onupdate` | Sweeper uses a raw `sqlalchemy.update()` statement, so only server-side defaults apply — the existing `onupdate=func.now()` on the column is SQLAlchemy-side and won't fire under bulk update; the migration is designed to avoid this ambiguity by sweeping on `updated_at` (which is re-asserted explicitly), not relying on the trigger |

## Out of scope (this issue)

- Any multi-source run fan-out (Problem 5 "one source per run is intentional" remains the rule).
- Real quota counters / cost accounting (Adzuna run-budget bookkeeping is #34's; Apify credit tracking stays out).
- Cancellation/user-initiated abandonment of an active run (a "cancel" button is a separate UX feature — the sweeper handles crashes, not user intent).
- Cross-profile concurrency (two profiles may run the same source simultaneously — deliberately untouched).
- Advisory-lock alternative implementation (approach chose the index; no lock code written).
- BackgroundTasks cancellation semantics or `session_factory` lifecycle changes.
