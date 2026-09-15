# v3 plan — profile-scoped search, freshness, advanced per-source filters

**Status:** Proposed plan for v3 (owner sign-off pending on decisions marked ⚠)
**Depends on:** v1 (#1–#12) and v2 (#13–#23) — all done.
**Plan of record:** this file; per-milestone issue plans (`v3-issue-NNN-*.md`) written
**before** implementation (v1 retro lesson), one GitHub milestone `v3`.

---

## 1. Why v3 — problems being fixed

1. **Jobs leak across profiles (bug).** A search run "as" the Senior Android profile
   produces matches on every profile. Three compounding causes, all in code today:
   - `toSearchRequest()` never sends `profile_id` (search-form-schema.ts:114–123), so the
     backend falls back to the most recently **updated** profile
     (`matching.py:192`, `latest_profile_id`).
   - `job_search` has no `profile_id` column — profile association lives only inside the
     `query` JSONB echo. Nothing can enforce scoping at the DB level.
   - `rescore_matches` scores the **entire global postings corpus** against whichever
     profile triggered it (`matching.py:121–170`) — every profile adopts every posting
     ever ingested.
   - Bonus hazard: `job_posting.job_search_id` is overwritten by the upsert on every
     re-fetch (`ingestion.py:246`), so "results of this run" is a mutable, shared pointer.

2. **Closed/stale jobs surface as results.** No expiry handling anywhere: no
   `expires_at`/`is_closed` on `job_posting`, no `max_days_old` on the search request,
   Adzuna's supported `max_days_old` param unused (deferred in
   [v1-llm-source-queries.md](../v1/v1-llm-source-queries.md)),
   the LinkedIn actor pinned to `datePosted: anyTime`. Only read-side
   `posted_within_days` (1–90) exists on matches.

3. **Search is basic and source-blind.** `SourceQuerySpec` is only
   `{title, skills≤3, exclude≤2, query}`; `SourceInfoResponse` exposes only
   `supports_exclusions`. Each source actually supports more (Adzuna: `title_only`,
   `distance`, `sort_by`, `max_days_old`, `salary_max`; LinkedIn actor: `datePosted`,
   `distance`, `under10Applicants`, `companyIds`, `geoId`). Every new source would
   otherwise need hand-written form fields — the UI must instead render each source's
   filter set from a capability declaration.

## 2. Locked decisions (⚠ = needs owner sign-off)

| # | Decision | Choice | Rationale |
|---|---|---|---|
| D1 | Matching corpus | **Scope to the profile's own searches.** A profile's match corpus = distinct postings linked to searches whose `profile_id` = that profile. Cross-profile discovery is not a feature for a single user with multiple career tracks | Direct fix for the reported symptom; corpus stays explainable ("jobs found by your searches for this profile") |
| D2 | Posting ↔ search link | **New association table `search_posting (search_id, posting_id)` many-to-many, append-only.** A posting found again in any later search gains a row; nothing is overwritten. `job_posting.job_search_id` is backfilled into the table then **dropped** (replaces the mutable pointer) | Fixes both the overwrite hazard and "which searches found this posting" queries; dedupe stays on `(source, external_id)` |
| D3 | `profile_id` on search | **Required** in `JobSearchRequest` (400 when missing/unknown profile) — no `latest_profile_id` fallback anymore. `job_search.profile_id` FK, NOT NULL after backfill | A search without an owner profile is meaningless under D1 |
| D4 | Stale-job policy | **Two layers:** (a) query-time: shared `max_days_old` filter passed to sources that support it (Adzuna `max_days_old`, LinkedIn `datePosted`); (b) read-time: postings excluded from matches/search results when `expires_at < now()` (LinkedIn provides `expireAt`) or when `posted_at` is older than a configurable grace window (default 45d) for sources that report no expiry | Never show a closed job; degrade gracefully per source |
| D5 | Per-source filters | **Capability-declared filters.** Each `JobSource` declares its filter schema (typed fields + options). Backend validates `SourceQuerySpec.options` against the declaring source (unknown key → 400); connectors map validated options to native params. `/api/sources` returns the declarations; the UI renders forms generically | New sources (config + mapper, per non-negotiable #3) automatically get correct UI + validation with zero search-logic changes |
| D6 | LLM query generation | Unchanged in shape (`profile.search_queries` per-source specs) but the stored spec gains the same `options` dict, so AI-generated and user-edited filters are one schema. Regenerate fills options only for fields the source declares | One schema everywhere; D5 validation applies regardless of who produced the values |
| D7 | Re-scoring trigger | Matching remains per-search-run (unchanged), but scores only the D1 corpus. Existing global matches for a profile are **not** deleted on upgrade; a `Rebuild matches` affordance is provided per profile | Avoids silent data loss; owner can opt in per profile |

## 3. Capability tables (researched, drives M2/M3)

### Adzuna (official API — verified in v1 research, unchanged)
| Filter | Param | Notes |
|---|---|---|
| Title phrase | `what_phrase` | already used |
| Skills any-of | `what_or` | already used |
| Exclusions | `what_exclude` | already used |
| Salary min/max | `salary_min`/`salary_max` | min used; **max new** |
| Freshness | `max_days_old` | **new** (M2) |
| Location radius | `where` + `distance` (km) | **new** |
| Title-only search | `title_only` | **new** |
| Sort | `sort_by` (`relevance`/`date`/`salary`) | **new** |
| Pagination | page param | v1 shipped page 1 only; cap stays `results_wanted` ≤ 50 for v3 |
| `full_time`/`permanent` | ❌ never filter on | silently discards most postings (v1 research) |

### Apify LinkedIn (`curious_coder/linkedin-jobs-scraper` — re-verified 2026-09-14)
Actor input (AI-search mode, `urls` empty):
| Filter | Input field | Notes |
|---|---|---|
| Keywords (NL) | `keywords` | already used; carries title/skills/salary NL |
| Location | `location` / `geoId` | location used; **`geoId` new** |
| Radius | `distance` (miles) | **new** |
| Freshness | `datePosted` (`anyTime`/`past24Hours`/`pastWeek`/`pastMonth`) | **new** (M2); replaces hardcoded `anyTime` |
| Under 10 applicants | `under10Applicants` | **new**; survives LinkedIn's AI search as a real filter |
| Company targeting | `companyIds` | **new**; advanced (user supplies IDs) |
| Experience / job type / workplace | ❌ no dedicated fields since Aug 2026 — folded into NL keywords via `autoConvertToAiSearch` (already true) | documented, not a filter field |
Result fields usable for freshness: `postedAt`/`postedAtTimestamp`, **`expireAt`**, `applicantsCount`.

## 4. Milestones

Order fixed by owner (2026-09-14): M1 → M2 → M3 (advanced filters and their UI ship as
one milestone; no separate UI milestone).

### M1 — Profile-scoped searches & matching (bug fix)

Backend:
- Migration `00NN_add_job_search_profile_and_search_posting`:
  - `job_search.profile_id` FK → `profile.id` (CASCADE), nullable first.
  - Backfill: `query->>'profile_id'` where present; rows with no backfillable owner →
    adopt the single most-recently-updated profile (single-user app) — recorded in the
    migration docstring.
  - New table `search_posting(id, search_id FK CASCADE, posting_id FK CASCADE,
    created_at)`, unique `(search_id, posting_id)`, index `(posting_id)`,
    index `(search_id)`; backfill from `job_posting.job_search_id`; then **drop**
    `job_posting.job_search_id` (destructive downgrade documented).
  - Set `job_search.profile_id` NOT NULL.
- `JobSearchRequest.profile_id: UUID` (required → 400 when absent; 404 unknown profile).
  Delete `latest_profile_id` fallback.
- Ingestion: `_upsert_posting` stops touching `job_search_id`; inserts/ignores a
  `search_posting` row per hit (idempotent).
- Matching: `rescore_matches` corpus query joins `search_posting → job_search` filtered
  by `job_search.profile_id = profile.id` (postings must also have embeddings). No
  global corpus scoring.
- `GET /api/jobs/searches/{id}` + `/postings`: 404 unless the search belongs to the
  current profile (single-user app: verify ownership, don't leak across profiles).

Frontend:
- `toSearchRequest()` sends the selected `profile_id`; form refuses submit without one.
- `/jobs` reads `?profile=` URL param (mirrors `/profile` page convention); profile
  switch resets search/run state (searchId, banner, results) and refetches matches.
- Per-profile "Rebuild matches" action (calls a new `POST /api/profiles/{id}/rebuild-matches`
  → background rescore over the D1 corpus; status via existing run-banner pattern).

Tests: migration up/down + backfill; 400/404 on missing/unknown profile; corpus scoping
(posting found by profile A's search never enters B's matches); association idempotency;
`job_search_id` drop verified.

### M2 — Freshness & closed-job handling

Backend:
- Migration `00NN_add_posting_expiry`: `job_posting.expires_at timestamptz nullable`,
  `job_posting.is_closed boolean not null default false` (downgrade drops both).
- Mappers: LinkedIn → `expires_at` from `expireAt`, `posted_at` from
  `postedAtTimestamp` (fall back `postedAt`); Adzuna → no expiry field (stays null).
  Both mappers set `posted_at` consistently for D4 grace checks.
- `JobSearchRequest.max_days_old: int | None` (1–90, shared filter) → `JobSearchQuery`;
  Adzuna sends `max_days_old`; LinkedIn maps to nearest `datePosted` bucket
  (≤1 → `past24Hours`, ≤7 → `pastWeek`, ≤30 → `pastMonth`, else `anyTime`).
- Read-side freshness service filter (shared by matches and search results):
  exclude `is_closed` or `expires_at < now()`; when `expires_at` is null, exclude
  `posted_at < now() - settings.stale_posting_days` (default 45, in `Settings`,
  documented in `.env.example`).
- `MatchFilters.posted_within_days` kept, now stacked on top of the expiry filter.

Frontend:
- Search form gains "Posted within" select (Any time / 24h / week / month) wired to
  `max_days_old`.
- Match/search-result cards show a subtle "Expires {date}" / "Stale" badge when known;
  expired items never render (no dead links).

Tests: mapper expiry extraction (LinkedIn fixture with/without `expireAt`);
`max_days_old`→Adzuna param and→`datePosted` bucket mapping; read filter matrix
(closed / expired / stale / fresh); settings default.

### M3 — Advanced per-source filters + capability-driven UI

Backend:
- `JobSource` protocol gains `filters() -> list[SourceFilterDecl]` where
  `SourceFilterDecl = {key, label, type: text|number|select|multiselect|boolean,
  options: list[{value,label}] | None, required, placeholder, help_text}`.
  Adzuna declares: `title_only` (bool), `distance_km` (number), `sort_by` (select),
  `salary_max` (number). Apify LinkedIn declares: `date_posted` (select — merges with
  M2 `max_days_old` mapping), `distance_miles` (number), `under_10_applicants` (bool),
  `company_ids` (multiselect-text), `geo_id` (text). YAML-driven sources declare filters
  in `connectors.yaml` (kept consistent with the config-only-addition rule).
- `SourceQuerySpec` gains `options: dict[str, str | int | bool | list[str]]` (capped);
  validated per selected source against its declaration (unknown key or bad type/enum →
  400 listing the offending key). `JobSearchQuery` gains the same validated `options`.
- Connectors map validated options → native params (tables in §3). Adzuna also honors
  `sort_by`. `query_rendering.py` stays the single render seam.
- `/api/sources` response gains `filters: list[SourceFilterDecl]` (and keeps
  `supports_exclusions` for back-compat during the transition).
- `query_builder.py` prompt: LLM may fill option fields the source declares (e.g. pick
  `sort_by: relevance`), never invents undeclared keys; stored `profile.search_queries`
  schema stamped `prompt_version: search_query_v2` (stale queries regenerate cleanly).

Frontend:
- New `components/ui/` primitives: `select.tsx`, `checkbox.tsx`, `accordion.tsx`
  (currently hand-rolled inline) — reusable, a11y-correct, theme-consistent.
- Generic `SourceFiltersForm`: renders declared fields per source inside the existing
  per-source accordion (`SearchQueriesCard`), driven entirely by `/api/sources` data —
  **zero per-source components**; new sources appear with their filters automatically.
- Zod schema generated from the declarations (validated client-side; backend remains
  source of truth). Values ride in `source_queries[name].options`.
- `MatchFilterPanel` (read-side filters) untouched except for the M2 badge work.

Tests: declaration-driven validation (unknown key / bad type / bad enum → 400 with key
name); connector mapping for every declared option; YAML-declared filters reach the
renderer; generic form renders fields for both sources; regenerate fills only declared
options; OpenAPI types regenerated (`npm run generate:api`).

## 5. Doc impact (every milestone)

- `docs/architecture.md`: ER (`job_search.profile_id`, `search_posting`, expiry columns),
  sequence (scoping + freshness), API table rows.
- `docs/guide/03-job-discovery-and-matching.md`: per-profile corpus explainer, freshness
  policy, per-source filter tables (§3 becomes the living reference).
- `.env.example`: `STALE_POSTING_DAYS`.
- `schema.d.ts` regenerated each milestone; diagrams re-rendered
  (`node scripts/render-diagrams.mjs`).

## 6. Issue breakdown (GitHub milestone `v3`; issues numbered from #24)

| Issue | Title | Milestone |
|---|---|---|
| #24 | Profile-scoped searches: `job_search.profile_id`, required `profile_id`, `search_posting` join table (M1) | v3 |
| #25 | Scoped matching corpus + rebuild-matches affordance + frontend sends profile & URL param (M1) | v3 |
| #26 | Posting expiry: model + mappers + read-side freshness filter (M2) | v3 |
| #27 | Freshness at query time: `max_days_old` → Adzuna / `datePosted` → LinkedIn + form field (M2) | v3 |
| #28 | Source filter capabilities: declarations, validation, connector mapping (M3) | v3 |
| #29 | Capability-driven search UI: ui primitives + generic per-source filter form (M3) | v3 |
| #30 | Search initiation stepper (one source per run, parallel runs OK) + profile country persistence fix | v3 |

### Scope addition (owner, 2026-09-15 — issue #30)

Post-plan addition, owner-approved in
[v3-issue-030-search-stepper-ui-and-country-persistence.md](v3-issue-030-search-stepper-ui-and-country-persistence.md):

1. **Search initiation as a stepper, one source per run.** The Global configuration
   dialog (delivered through #29) is replaced by a Start-search button + 4-step
   wizard (profile → source → details → advanced filters). `JobSearchRequest`
   moves from `sources: list[str]` to a required single `source`; parallel runs on
   different sources remain allowed (no concurrency guard). All capability-driven
   filter UI from #28/#29 is reused unchanged in step 4.
2. **Bug fix:** chat-set `contact.country` is silently wiped by any manual profile
   save — the frontend form model (`profile-schema.ts`) omits the field, so
   `toProfilePayload()` rebuilds `contact` without it and the backend defaults it
   back to `None`. Fix is frontend-only; no migration.

Process fixes adopted from the v1/v2 retro: each issue's plan doc
(`v3-issue-0NN-*.md`) is written and reviewed **before** implementation; each GitHub
issue is filed once with the `v3` milestone attached immediately.

## 7. Definition of done (per milestone)

- Backend: `ruff check . && ruff format --check . && pytest` green (in `backend/`).
- Frontend (where touched): `npm run lint && npm run build` green (in `frontend/`).
- Migration milestones: up/down verified against scratch Postgres.
- Live check: two profiles with different target roles → search as profile A → profile B
  shows zero of A's matches (M1); a 60-day-old posting stops appearing (M2); both
  sources' advanced filters reach the wire correctly (M3).
- Docs/diagrams/types updated in the same change.

## 8. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Dropping `job_posting.job_search_id` loses "first seen" context | Backfill preserves it in `search_posting`; `raw_payload` retained per non-negotiable pattern |
| Stricter corpus shrinks a profile's matches after upgrade | D7: nothing auto-deleted; explicit per-profile rebuild; run banner shows corpus size |
| LinkedIn `datePosted` buckets are coarser than `max_days_old` | Document the bucket mapping (§3); Adzuna stays exact |
| Capability declarations drift from actor/API reality | Declarations live next to connectors (code/YAML), asserted in tests with fixture payloads; `raw_payload` aids debugging |
| Backfill ambiguity (old searches with no `profile_id`) | Single-user app → adopt most-recent profile; recorded in migration docstring; ⚠ owner sign-off |
