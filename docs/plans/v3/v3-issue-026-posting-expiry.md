# Issue #26 — Posting expiry: model + mappers + read-side freshness filter

**Status:** Done (branch `v3/26-posting-expiry`)
**Tracks:** GitHub issue #26 (milestone `v3`, M2 freshness — backend part)
**Plan of record:** [v3-implementation-plan.md](v3-implementation-plan.md) §2 D4; §4 M2
(backend model/mapper/read-filter part)
**Depends on:** #24/#25 (merged — `search_posting` join table, owned-search guards,
scoped corpus all exist; mapper changes touch the same `_upsert_posting` path).
**Blocks:** #27 (query-time `max_days_old` + frontend freshness UI builds on these
columns and the shared read filter). M3/#28 untouched.

---

## Goal

Closed and stale postings never surface as matches or search results. Today nothing
protects against a LinkedIn posting that expired days ago or an Adzuna hit from eight
months ago: there is no `expires_at`/`is_closed` on `job_posting` and no read-side
staleness cutoff. This issue adds the expiry data model, wires the sources that report
expiry into it, and installs one shared freshness filter used by both read paths.

Explicitly backend-only. The M2 frontend work ("Expires {date}" / "Stale" badges and the
"Posted within" form control) ships with #27; this issue exposes the fields it needs.

## Locked decisions

| Decision | Choice | Rationale |
|---|---|---|
| Expiry columns | `job_posting.expires_at timestamptz nullable`, `job_posting.is_closed boolean not null default false` (migration `0015`) | D4's two-layer policy needs the raw facts on the row. `is_closed` has no producing source today (LinkedIn's dataset doesn't expose a closed flag) — the column exists as the single read-filter seam so a future source/mapper (or manual curation) can close a posting without a migration |
| `JobPostingData` shape | Two new fields on the connector DTO: `expires_at: datetime \| None`, `is_closed: bool = False` | One shared DTO for all connectors; sources that don't report expiry leave defaults (Adzuna: `expires_at=None`, `is_closed=False`) |
| LinkedIn mapper | `expires_at` from `expireAt` via the existing `parse_datetime` (absent/malformed → `None`); `posted_at` already extracted from `postedAtTimestamp` falling back to `postedAt` — unchanged | `expireAt` is the only freshness signal the actor dataset provides (v3 plan §3, re-verified 2026-09-14). `parse_datetime` already handles ISO strings and epoch seconds/millis; no new parsing code |
| Adzuna mapper | No changes — `expires_at=None` (no API field), `posted_at` already set from `payload["created"]` | Adzuna's supported `max_days_old` (query-time) is #27's scope; read-side staleness alone covers it here per D4's "degrade gracefully per source" |
| Upsert | `_upsert_posting` gains both fields in insert values and `on_conflict_do_update.set_` (re-fetch refreshes expiry when the source now reports it) | Same upsert path as every other column; dedupe stays `(source, external_id)` |
| Shared freshness filter | One service-level predicate helper used by **both** read paths — matches (match list / rebuild discrepancy counting) and search results (`get_search_postings`): exclude `is_closed OR expires_at < now()`; when `is_closed=false` and `expires_at IS NULL`, exclude `posted_at < now() - settings.stale_posting_days` | D4 read layer. One helper means the policy can't drift between the two surfaces. Expressed as SQL conditions composed into `Select` (composition-friendly), not a post-filter on fetched rows |
| `stale_posting_days` setting | `Settings.stale_posting_days: int = 45` (+ `ge=1` validation), documented in `.env.example` | Grace window for sources that report no expiry (D4 default 45d). `lru_cache`d `Settings` means no runtime cost |
| `MatchFilters.posted_within_days` | Kept unchanged, stacked on top of the freshness filter (additive WHERE clauses) | It is the user's intentional narrowing, not a safety net; the expiry filter is always applied first and independently |
| Rescore/rebuild corpus | The freshness filter applies at **read time only**, not to the scoring corpus or the out-of-corpus deletion count | Per issue scope ("read-side"). Matches for expired postings may persist in the DB after upgrade but never render. Consequence, accepted: `MatchRebuildStatusResponse.stale_count` (#25) counts out-of-corpus rows unchanged — it is a corpus concept, not a freshness concept, and the dashboard API refetches nothing on rebuild |
| Schema exposure | `JobPostingSummary`/`JobPostingDetail` (`schemas/job_search.py`) gain `expires_at: datetime \| None` (and `is_closed: bool`) so #27's badges have typed data without a second backend change | Cheap now, avoids reopening the OpenAPI surface in #27 |

⚠ Owner sign-off points: (a) `is_closed` ships unused-by-sources (future seam);
(b) read-filter-only scope (no rescore corpus change, matches for expired postings linger
invisibly until rebuilt).

## Scope

### Migration `0015_add_posting_expiry`

- `job_posting.expires_at timestamptz nullable`.
- `job_posting.is_closed boolean not null default false`.
- No new index (single-user scale; `posted_at` is already indexed for the existing
  `posted_within_days` and sort paths — the same filter family uses it).
- Downgrade drops both columns (data-loss downgrade documented in the docstring).
- Backfill: none available — existing rows have neither field in history;
  `expires_at` stays null for them (grace window handles staleness until refetched).

### Models & DTOs

- `app/models/job_posting.py`: two `mapped_column`s per §Migration, `expires_at`
  following the `posted_at` `DateTime(timezone=True)` convention.
- `app/adapters/job_sources/base.py`: `JobPostingData.expires_at`, `is_closed`.

### Mappers

- `app/adapters/job_sources/mappers/linkedin.py`: new `_expires_at(payload)` helper
  (`parse_datetime(payload.get("expireAt"))`), passed into `JobPostingData`.
- Adzuna (`adzuna.py`): untouched (defaults).
- YAML-driven sources: no non-default expiry fields exist — nothing to declare yet;
  revisited if a new source lands in M3.

### Services

- `app/services/ingestion.py` `_upsert_posting`: add both fields to insert + conflict
  `set_` (when a source stops reporting `expireAt`, the reset to null on refresh is
  correct — the source says it's no longer listed with an expiry).
- `app/services/matching.py`: a new public service-level predicate helper producing the
  SQL freshness conditions (reads `get_settings()` internally so the grace window is
  honored from `.env`). Returns composable WHERE conditions — not a post-filter —
  implementing the decision table above: closed → excluded; `expires_at < now()` →
  excluded; `expires_at IS NULL` → excluded when `posted_at < now() -
  stale_posting_days`.
- Apply to: the matches read path (`_apply_posting_filters` gains the freshness block,
  applied **before** `posted_within_days` so stacking is deterministic) and
  `ingestion.get_search_postings` (join + where unchanged, freshness added).
- `schemas/job_search.py`: `JobPostingSummary` / `JobPostingDetail` / `from_posting`
  gain `expires_at` (+ `is_closed`).

### Config

- `app/core/config.py`: `stale_posting_days: int = 45` with `ge=1`.
- `.env.example`: `STALE_POSTING_DAYS=45` with a comment line.

## Tests

Backend (scratch Postgres, migrations applied — never SQLite):

- Mapper: LinkedIn fixture with `expireAt` (ISO string) → parsed; without/malformed →
  `None`; `is_closed` default `False`; epoch-millis also accepted. Adzuna fixture →
  `expires_at is None`.
- Upsert: re-fetch with a new `expires_at`' updates the row; `search_posting`
  idempotency unaffected.
- Read filter matrix (fixture rows across `posted_at`/`expires_at`/`is_closed` with
  `MOCK_NOW`-style injected clock or relative `posted_at` datetimes):
  - closed → excluded regardless of dates;
  - `expires_at < now()` → excluded;
  - `expires_at` in the future → included even if `posted_at` is old;
  - `expires_at IS NULL` + `posted_at` inside grace window → included;
  - `expires_at IS NULL` + `posted_at` older than 45d → excluded;
  - `stale_posting_days` override honored (e.g. 10d moves the cutoff).
- Stacking: `posted_within_days=7` on top of the freshness filter still applies.
- Surfaces: `get_search_postings` and the matches list endpoint both honor the filter
  (fresh posting present in search results post-filter).
- Settings default: `Settings()` → 45.
- Migration `0015` up/down round-trip (downgrade drops columns, restores previous
  schema).
- `conftest.clean_tables`: no new table — nothing to add.

## Definition of done

- `ruff check . && ruff format --check . && pytest` green in `backend/`.
- Migration `0015` generated, reviewed against this plan, up/down verified on scratch
  Postgres.
- Live check: a fixture/search containing an already-expired LinkedIn posting and a
  60-day-old no-expiry posting → neither appears in search results nor matches; a fresh
  posting from the same run does.
- `frontend/lib/api/schema.d.ts` regenerated (`npm run generate:api`) — summary/detail
  fields in the OpenAPI surface (no frontend behavior change; no lint/build impact
  expected but run the gates if the generated types touch compiled code).
- Docs: `docs/guide/03-job-discovery-and-matching.md` — freshness policy section
  (expiry vs grace window, per-source signal table); `docs/architecture.md` — ER
  (`expires_at`, `is_closed`) + API note; `node scripts/render-diagrams.mjs` re-run.
- `.env.example`: `STALE_POSTING_DAYS` documented.

## Out of scope (this issue)

- Query-time freshness (`max_days_old` → Adzuna, `datePosted` → LinkedIn, frontend
  form select) → #27.
- Frontend badges ("Expires {date}" / "Stale") → #27.
- Filter-capability declarations and their UI → #28/#29.
- Deleting matches for expired postings, or rescoring the corpus against freshness →
  read-filter-only by design (see ⚠ b); revisited only if the dashboard degrades.
- Any new job source.
