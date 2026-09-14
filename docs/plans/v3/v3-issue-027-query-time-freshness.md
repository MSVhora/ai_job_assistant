# Issue #27 — Freshness at query time: `max_days_old` → Adzuna / `datePosted` → LinkedIn + form field

**Status:** Done (merged)
**Tracks:** GitHub issue #27 (milestone `v3`, M2 freshness — query-time part + M2 frontend)
**Plan of record:** [v3-implementation-plan.md](v3-implementation-plan.md) §2 D4 (layer a); §4 M2
**Depends on:** #26 (merged — `expires_at`/`is_closed` columns, LinkedIn `expireAt` mapper,
shared read-side freshness filter all exist).
**Blocks:** nothing in M2; #28/#29 must not invalidate the `{date_posted_bucket}` seam
(chosen so capability work can absorb it, see Locked decisions).

---

## Goal

The read-side freshness filter (#26) hides stale rows, but every search still **asks the
sources** for postings of any age: Adzuna has no query-time freshness param sent, and the
LinkedIn actor input hardcodes `datePosted: anyTime` (connectors.yaml). This issue adds
the shared `max_days_old` filter to the search request, maps it to each source's native
freshness parameter, and ships the M2 frontend: the "Posted within" select plus the
"Expires {date}" / "Stale" badges on match and result cards.

Two layers, both intentional (D4): query-time narrows what sources return (fewer
results, less scrape cost); read-time (#26) remains the safety net for closed/failed
freshness reporting. `MatchFilters.posted_within_days` is untouched and independent.

## Locked decisions

| Decision | Choice | Rationale |
|---|---|---|
| Shared field | `JobSearchRequest.max_days_old: int \| None = None` (`ge=1, le=90` — same bounds family as `posted_within_days`), carried into `JobSearchQuery` via `query_rendering.py` (single render seam) | D4 layer (a). One shared filter, not per-source options — per-source option plumbing is #28's `options` dict; duplicating it here would create two schemas for the same concept |
| Form values | Select options: Any time (→ absent) / "Last 24 hours" (`1`) / "Last week" (`7`) / "Last month" (`30`) | Mirrors LinkedIn's buckets exactly, 1:1 with the mapping table so both sources narrow identically; 1–90 kept for API callers who want Adzuna's exact day counts |
| LinkedIn mapping | `date_posted_bucket(max_days_old): ≤1 → "past24h", ≤7 → "pastWeek", ≤30 → "pastMonth", else "anyTime"`; `None → "anyTime"` — mapping helper lives in `app/adapters/job_sources/base.py`, so both the placeholder resolver and tests reach it | Bucket quantization is unavoidable (coarse actor field, v3 plan §3 risk table); documented mapping, Adzuna stays exact |
| LinkedIn wiring | `connectors.yaml` input gains `datePosted: "{date_posted_bucket}"`; `_resolve_value` resolves the new placeholder from `query.max_days_old` and `_PLACEHOLDER_KEYS` is extended | Keeps the config-driven input path intact (no bespoke overrides in `ApifyActorSource`); the placeholder rule survives #28 — options will reuse this pattern |
| Adzuna wiring | `_apply_search_terms`/new helper sets `params["max_days_old"] = str(query.max_days_old)` when set | Adzuna's native param is exact-day; no bucket mapping |
| Sources without support | Ignored silently (YAML sources with no placeholder get no freshness param; a customer's custom config simply omits it) | D4 "degrade gracefully per source"; the `JobSource` protocol stays unchanged in M2 (capability declarations land in #28) |
| Query-time vs read layer | Independent and additive: a search with `max_days_old=7` still passes its results through the #26 read filter (a posting whose scraper-reported `posted_at` is older is excluded there) | No special-casing "recent searches don't need the safety net"; the corpus stays uniformly clean |
| Stale badge cutoff | ⚠ Cosmetic "Stale" badge computed client-side with a 30-day constant (not the backend's `STALE_POSTING_DAYS`) — visual hint only, filtering authority stays backend | Exposing a backend-computed staleness flag would reopen the schema settled in #26 for a cosmetic hint; flagged for owner sign-off because the two numbers *can* drift |
| Data echo | `max_days_old` appears in the stored `query` JSONB echo automatically (whole-request dump) | No extra code; the run is reproducible |
| No migration | None — no schema change | `max_days_old` lives only in requests and the query echo |

## Scope

### Backend — schema & rendering

- `app/schemas/job_search.py`: `JobSearchRequest.max_days_old: int | None = Field(default=None, ge=1, le=90)`.
- `app/adapters/job_sources/base.py`:
  - `JobSearchQuery.max_days_old: int | None = None` (same bounds).
  - new `date_posted_bucket(max_days_old: int | None) -> str` helper per the mapping table.
- `app/services/query_rendering.py`: `build_connector_query` always includes
  `max_days_old` in the `JobSearchQuery` kwargs (like the salary fields — set for every
  source, consumed only by those that support it).

### Backend — connectors

- `app/adapters/job_sources/adzuna.py`: apply `max_days_old` param when set.
- `app/adapters/job_sources/connectors.yaml`: `datePosted: "{date_posted_bucket}"`.
- `app/adapters/job_sources/config.py`: resolver case + `_PLACEHOLDER_KEYS` extension;
  resolution omits the key when `max_days_old` is `None` (actor default `anyTime` is the
  YAML fallback — keep a literal default in YAML? No: the placeholder always resolves, to
  `"anyTime"` for `None`, so stale YAML state can't silently pin `anyTime`).

### Backend — tests

Backend (scratch Postgres not needed fixture-wise beyond connector/unit tests — no DB
schema change, but the vertical integration stays covered by existing read-filter tests):

- `date_posted_bucket`: `None→anyTime`, `1→past24h`, `7→pastWeek`, `30→pastMonth`,
  `90→anyTime`, off-bounds input clamped by schema.
- Adzuna: request params include `max_days_old=7`; absent when the field is `None`.
- Actor input: placeholder builds `datePosted: pastWeek` for `max_days_old=7` and
  `anyTime` for `None` (fixtures in `test_apify_adapter.py` updated off the hardcoded
  literal); unknown-placeholder validation still rejects typos.
- Schema bounds: `max_days_old=0`/`91` → 422; `max_days_old` survives into the stored
  query echo.
- Rendering: `build_connector_query` carries the field into `JobSearchQuery`.

### Frontend

- `frontend/lib/api/schema.d.ts` regenerated (`npm run generate:api`).
- `search-form-schema.ts`: `SearchFormValues.posted_within: string` (default
  `"any"`); zod enum `any|1|7|30`; `toSearchRequest()` emits
  `max_days_old: number | undefined`.
- `SearchForm.tsx`: labeled "Posted within" native `<select>` next to Min salary / results
  (single use here; `components/ui/select.tsx` is #29's scope — noted so it isn't done twice).
- Badges (reusing `components/ui/badge.tsx`, muted variant):
  - `MatchCard`, `SearchResults`, `JobDetailPanel`: "Expires {date}" when
    `expires_at` is set; "Stale" when `expires_at` is null and `posted_at` is older than
    30 days (⚠ cosmetic constant).
  - Expired postings never surface — that is the #26 read filter's contract; the badge
    assumes fresh-or-stale, never closed.

## Definition of done

- `ruff check . && ruff format --check . && pytest` green in `backend/`.
- `npm run lint && npm run build` green in `frontend/`.
- `npm run generate:api` run — types include `max_days_old`.
- Live check: search with "Last week" → the Adzuna request URL carries `max_days_old=7`
  and the Apify actor input carries `datePosted: pastWeek`; the stored run's query echo
  reflects the choice. A 40-day-old posting still appears for "Any time" only if it
  passes the read filter — outcomes match D4.
- Docs: `docs/guide/03-job-discovery-and-matching.md` — query-time freshness row added to
  the per-source table (mapping: day count → `datePosted` bucket); `docs/architecture.md`
  — API/request field note + sequence diagram touch. `node scripts/render-diagrams.mjs`.
- No migration (none needed) and no `.env.example` change (no new setting).

## Out of scope (this issue)

- Expiry columns, read-side freshness filter, `expireAt` mapper → #26 (done).
- Per-source filter capability declarations (`SourceFilterDecl`, `options` dict, generic
  form) → #28/#29.
- New sources, pagination, or a "Rebuild" interaction change.
- Backend-computed staleness flag / `STALE_POSTING_DAYS` exposure (⚠ above; revisit if
  the dashboard degrades).
