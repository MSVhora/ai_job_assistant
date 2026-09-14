# Issue #25 — Scoped matching corpus + rebuild-matches affordance + frontend sends profile & URL param

**Status:** Planned (not started)
**Tracks:** GitHub issue #25 (milestone `v3`, M1 matching + frontend)
**Plan of record:** [v3-implementation-plan.md](v3-implementation-plan.md) §2 D1, D7; §4 M1 (matching + frontend part)
**Depends on:** #24 (merged — `job_search.profile_id` NOT NULL, `search_posting` join table, `_require_owned_search` all exist). **Blocks:** nothing in M1; M2/#26 builds on M1's frontend conventions.

---

## Goal

Close the last two enablers of the cross-profile job leak, and give the user an explicit
escape hatch for pre-existing global matches:

1. **Backend:** `rescore_matches` scores only the profile's own search corpus (D1) —
   postings found by profile A's searches never become profile B's matches. Today
   (`matching.py:121–170`) it scores the entire `job_posting` table against any profile.
2. **Backend:** a new `POST /api/profiles/{id}/rebuild-matches` runs the scoped rescore as
   a background task, with a queryable status (run-banner pattern) that reports corpus
   size (D7's explicit per-profile opt-in).
3. **Frontend:** the search form finally sends `profile_id` (the config-level hole in the
   reported bug; the DB/API level was closed by #24), `/jobs` adopts the `?profile=`
   URL-param convention established on `/profile`, profile switching resets run state,
   and a per-profile "Rebuild matches" action is wired to the new endpoint.

**Note — this issue also fixes a live regression from #24:** `getJobSearchStatus` and
`getSearchPostings` in `lib/api/index.ts` do not yet send the now-required `profile_id`
query param, so every run-status poll fails with 422. #25's frontend scope (send the
active profile everywhere on `/jobs`) resolves it.

## Locked decisions

| Decision | Choice | Rationale |
|---|---|---|
| Corpus query shape | `select(JobPosting.id, score)` with two predicates: `embedding IS NOT NULL` (unchanged) and `EXISTS (SELECT 1 FROM search_posting sp JOIN job_search js ON js.id = sp.search_id WHERE sp.posting_id = job_posting.id AND js.profile_id = :profile_id)` | EXISTS avoids DISTINCT over the many-to-many (a posting found by several of the profile's searches must be scored once) and reuses the #24 tables as-is — no new schema. Scoped corpus ≠ global corpus; the reporting bug's root cause is gone |
| Other `rescore_matches` call sites | Inherit scoping unchanged (`profile.py` create/save, `gap_fill.py`, `seed_demo.py`, `backfill_embeddings.py`) — no per-site changes | D1 is a property of the scoring function, not of who triggers it. Consequence, accepted: a **new profile with zero searches gets zero matches** until it runs a search. Previously it scored the global corpus immediately; that was the bug, so the regression test documents the empty-corpus behavior |
| Rebuild semantics | Rebuild = refresh profile embedding → scoped rescore (`invalidate_rationales=False`: postings still in the corpus keep their blended `role_fit`/`company_fit`) → `_rerank_top_matches` → **delete matches for the same profile whose posting is no longer in the scoped corpus** | ⚠ owner sign-off. D7's "not auto-deleted" protects the upgrade path (nothing is deleted until the user clicks Rebuild); once the user explicitly rebuilds, stale out-of-corpus matches contradict the scoped-corpus contract and would clutter the dashboard. Deletion is per matching profile only |
| Rebuild run state | New table `match_rebuild(id uuid pk, profile_id FK → profile.id CASCADE, status: pending/running/succeeded/failed, corpus_count int, scored_count int, warning text nullable, created_at, updated_at)`; one row per rebuild run. `GET /api/profiles/{id}/rebuild-matches` returns the **latest** run (404 if none); POST returns 202 with the run row | ⚠ owner sign-off on the small persistent-run table (migration `0014`). Background status must be DB-queryable per the long-running-work rule; polling via the existing run-banner pattern needs a row. Latest-run-only keeps the API surface single-user simple. `corpus_count` satisfies "run banner shows corpus size" |
| Rebuild trigger code path | Follow the `start_search`/`run_search` pattern exactly: router builds `BackgroundTasks` + scopes the session; service validates profile exists (404 `ProfileNotFoundError`) and `profile.embedding` is not null (409 `ProfileNotEmbedded` — existing error), creates the run row (`pending`), then `run()` opens a **fresh session** (`session_factory`) and stamps statuses | Matches the ingestion background-task convention (no long-lived sessions in background tasks); reuses existing domain errors — zero new error classes |
| Frontend `profile_id` plumbing | `toSearchRequest(values, sources, profileCurrency, profileId)` appends `profile_id` to the payload; `profileId` is also returned in the `missing: string[]` (as a schema payload field) so long-form submit is refused without a selected profile — the form never fires a search the backend will 400. `JobsPageClient` passes `activeProfileId` (existing fallback resolves to the first/only profile) | Form refuses submit per the issue body; backend stays the source of truth (#24's service-level 400 remains as defense) |
| `/jobs?profile=` convention | `JobsPageClient` (client subcomponent) reads `?profile=` via `useSearchParams()` (already `Suspense`-wrapped at page level on `/profile`; mirror that wrapper on `/jobs`); profile change → `router.replace("/jobs?profile=<id>")` + reset local run state (`searchId`, dismissed banners); matches refetch automatically via the existing `["matches", profileId, params]` query key | Mirrors the `/profile` page convention exactly (FirstReview/MergeMode precedent). Single source of truth for the selected profile goes in the URL, not hidden React state |
| Rebuild UI affordance | "Rebuild matches" button on `/jobs`, scoped to `activeProfileId`, disabled while a rebuild run is active or no profile is selected; a small rebuild run banner (reuse of the RunBanner pattern with a `useMatchRebuildStatus` hook polling the GET endpoint) shows status + corpus size + scored count | D7: explicit, per-profile, with visible corpus size. Lives next to the profile context (jobs page) rather than inside the config modal so parity with the search run banner is obvious |
| Run-banner status plumbing fix | `getJobSearchStatus(searchId, profileId)` and `getSearchPostings(searchId, profileId)` gain the required query param; `RunBanner`/hooks thread the active profile id through | Repairs the #24-induced 422; without it every search run shows a failed banner |

## Scope

### Backend

**Migration `0014_add_match_rebuild_table`**

- `match_rebuild`: `id` (uuid, server `gen_random_uuid()`), `profile_id` FK →
  `profile.id` `ON DELETE CASCADE` (indexed, FK-index standard),
  `status` (`sa.Enum(name="match_rebuild_status", values=["pending","running","succeeded","failed"])`),
  `corpus_count int not null default 0`, `scored_count int not null default 0`,
  `warning text nullable`, `created_at`/`updated_at` (`timestamptz` conventions).
  Index `(profile_id, created_at DESC)` for the latest-run lookup.
- Downgrade: drop table + enum. Non-destructive to existing data (pure addition).

### Services

- `matching.py`:
  - `rescore_matches`: add the EXISTS corpus predicate (decisions table above); query,
    row-building, and bulk upsert otherwise unchanged.
  - New `rebuild_matches_for_profile(run_id: uuid.UUID)` background entry: fresh session
    from `app.core.db`, load run row + profile, status → `running`, call
    `embedding.refresh_profile_embedding(session, profile)` (readtime embedding refresh so
    the rebuild scores against the current profile text), `rescore_matches(...,
    invalidate_rationales=False)`, delete out-of-corpus matches
    (`DELETE FROM match WHERE profile_id = X AND job_posting_id NOT IN (scoped corpus
    SELECT)` — parameterized `delete()` with a scalar subquery, not a fetch-then-loop),
    `_rerank_top_matches`, stamp run row (`succeeded`, `corpus_count`, `scored_count` /
    `failed` + warning) with per-stage commits, mirroring `run_search`'s commit cadence.
- New `app/services/match_rebuild.py` (or fold into `matching.py` if it stays <200 lines
  after review): `start_rebuild(session, background_tasks, profile_id)` → run row +
  `add_task`; `get_latest_rebuild(session, profile_id)` → 404 `MatchRebuildNotFoundError`
  when the profile has never rebuilt.

### Schemas (`app/schemas/matching.py`)

- `MatchRebuildStatusResponse`: `id`, `profile_id`, `status`, `corpus_count`,
  `scored_count`, `warning`, `created_at`, `updated_at`.

### Router (`routers/profile.py`)

- `POST /api/profiles/{profile_id}/rebuild-matches` → 202,
  `response_model=MatchRebuildStatusResponse`, `BackgroundTasks` from the framework,
  session via `deps`.
- `GET /api/profiles/{profile_id}/rebuild-matches` → 200 latest run / 404 if none.
  Unknown profile → 404 (`ProfileNotFoundError`, shared helper).

### Errors

- New `MatchRebuildNotFoundError` (404). No new 400/409 classes needed
  (`ProfileNotFoundError` / `ProfileNotEmbedded` exist).

### Frontend

- `components/features/jobs/search-form-schema.ts`: signature gains `profileId`, payload
  gains `profile_id`, missing-profile included in the refusal path; callers
  (`JobsPageClient` → form component) updated.
- `lib/api/index.ts`: `startJobSearch` unchanged; `getJobSearchStatus`/`getSearchPostings`
  gain required `profileId` (fix the 422); new `startMatchRebuild(profileId)` +
  `getMatchRebuildStatus(profileId)` for the latest-run status.
- `app/jobs/page.tsx` + `JobsPageClient.tsx`: `?profile=` read/write (Suspense wrapper as
  on `/profile`); URL is the source of truth for the selected profile; profile switch
  resets `searchId` and dismissed-banner state; hooks stack profileId into poll keys.
- `RunBanner` + `hooks/use-job-search.ts`: thread `profileId` into the status/postings
  calls (dedupe-safe; TanStack keys already carry `searchId`, params now carry profile).
- New per-profile "Rebuild matches" button + `RebuildRunBanner` (status/corpus size/
  scored count/succeeded-failed footers, `aria-live` status), wired to the two new API
  client functions; disabled while active or `!activeProfileId`; a fresh rebuild POST
  clears the previous run's banner.
- Update the search form's submit gating so `missing: ["profile_id"]` renders the
  existing missing-field error pattern (no silent failures).

## Tests

Backend (scratch Postgres, migrations applied — never SQLite):

- `tests/services/test_matching.py`:
  - **Corpus scoping regression (the reported bug):** profile A runs a search finding
    postings P1, P2; profile B never searched; B's `refresh_matches_for_profile` scores
    **0** postings; A's scores P1+P2; a posting with an embedding but no association is
    invisible to both; association via A's `search_posting` rows only.
  - Rebuild lifecycle: `start_rebuild` creates a `pending` row; background run →
    `succeeded` with `corpus_count`/`scored_count` correct; out-of-corpus matches for the
    profile are deleted after rebuild; another profile's matches untouched; blending of
    existing rationale scores preserved (`invalidate_rationales=False` path);
    `failed` path stamps warning when the rerank stage raises.
  - Empty corpus: brand-new profile → scored 0, succeeded (not failed).
- `tests/test_profile_endpoints.py`: POST → 202 + `MatchRebuildStatusResponse`; GET →
  latest run; 404 before any rebuild; unknown profile → 404; unembedded profile → 409.
- Migration `0014` up/down round-trip on seeded data.
- `conftest.clean_tables` gains `match_rebuild`.

Frontend (mirror the repo's existing frontend test setup if present; lint/typecheck are
the gate regardless):

- `toSearchRequest` includes `profile_id` and reports it in `missing` when absent.
- URL-param wiring exercised in the component test if the infra supports it
  (`useSearchParams` mocking), otherwise verified at the live check.

## Definition of done

- `ruff check . && ruff format --check . && pytest` green in `backend/`; `npm run lint &&
  npm run build` green in `frontend/`.
- Migration `0014` generated, reviewed against this plan, up/down verified on scratch
  Postgres.
- Live check: two profiles with different target roles → search as profile A →
  profile B shows zero of A's matches; B's rebuild banner reports corpus size 0; A's
  rebuild re-scores A's corpus; status polling on `/jobs` succeeds again (422 gone).
- `frontend/lib/api/schema.d.ts` regenerated (`npm run generate:api`) — rebuild endpoints
  in the OpenAPI surface.
- Docs: `docs/guide/03-job-discovery-and-matching.md` — per-profile corpus explainer +
  rebuild affordance; `docs/architecture.md` — ER (`match_rebuild`), API table rows;
  `node scripts/render-diagrams.mjs` re-run.
- `.env.example`: no change (no new settings this issue).

## Out of scope (this issue)

Freshness/stale filtering (M2: #26/#27), per-source filter capabilities (M3: #28/#29),
deleting old matches at upgrade time (never — D7), pagination/search-run reuse beyond
status plumbing, retroactively rebuilding any profile automatically.
