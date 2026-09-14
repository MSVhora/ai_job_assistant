# Issue #24 — Profile-scoped searches: `job_search.profile_id`, required `profile_id`, `search_posting` join table

**Status:** Planned (not started)
**Tracks:** GitHub issue #24 (milestone `v3`, M1 backend part)
**Plan of record:** [v3-implementation-plan.md](v3-implementation-plan.md) §1.1 (problem), §2 D1–D3, §4 M1 (backend)
**Depends on:** nothing. **Blocks:** #25 (scoped corpus + rebuild affordance + frontend).

---

## Goal

Fix the cross-profile job leak **at the data layer**: a search run for profile A is owned
by profile A in the database (not just echoed inside `query` JSONB), the API refuses to
search without an owner profile, results-view endpoints never expose another profile's
search, and "which searches found this posting" is an append-only association instead of
a mutable `job_posting.job_search_id` pointer that upserts overwrite
(`ingestion.py:246` today).

The bug chain being closed: postings found by profile A's search currently become part of
every profile's corpus (`rescore_matches` scores the global corpus),
`toSearchRequest()` never sends `profile_id` (frontendFB — #25), and
`latest_profile_id()` (`matching.py:192,332`) silently picks the most-recently-updated
profile. This issue removes the backend enablers of the leak; the matching-corpus scoping
itself and the frontend (`profile_id` in the request, URL-param profile switching,
rebuild-matches) land in #25.

## Locked decisions

| Decision | Choice | Rationale |
|---|---|---|
| `job_search.profile_id` | FK → `profile.id` `ON DELETE CASCADE`, nullable in migration → backfill → `NOT NULL`. Backfill order: (1) `job_search.query->>'profile_id'` where it parses to an existing profile; (2) rows with no backfillable owner adopt the **most-recently-updated profile** (single-user app) — recorded in the migration docstring | ⚠ owner sign-off on the adoption fallback (v3 plan §8 risk). The `query` echo is the only per-search association that exists today |
| `profile_id` in `JobSearchRequest` | Presentation/type stays `uuid.UUID \| None` in the pydantic schema; **absence → 400** via a domain error raised in `ingestion.start_search` (not a 422 from pydantic). Unknown profile → 404 `ProfileNotFoundError` | Issue body says "400 absent". A required pydantic field would 422 before any handler can map it to 400; keeping it optional in the schema and validating in the service honors the contract while still being server-enforced. Backend re-validates regardless of the frontend (#25 makes the form always send it) |
| Delete `latest_profile_id` | `refresh_matches_for_search` (`matching.py:189–195`) uses `payload.profile_id` only (now guaranteed present by the service-level check); `latest_profile_id()` is deleted with its test | The fallback is the reported bug's silent path; D3 forbids a search without an owner |
| `search_posting` table | Append-only many-to-many: `search_posting(id uuid pk, search_id FK → job_search.id CASCADE, posting_id FK → job_posting.id CASCADE, created_at server now)`, unique `(search_id, posting_id)`, index `(posting_id)`, index `(search_id)`. `job_search_id` on `job_posting` is backfilled into the table, then **dropped** (downgrade = destructive; documented) | D2. Fixes the overwrite hazard (`ingestion.py:246` re-stamps the pointer every re-fetch) and answers "which searches found this posting". Dedupe stays on `(source, external_id)`; PK stability is untouched |
| Association insert | `_upsert_posting` stops touching `job_search_id`; after the posting upsert resolves the stable posting PK, `INSERT … ON CONFLICT (search_id, posting_id) DO NOTHING` for `search_posting` (idempotent across re-searches) | Append-only semantics; re-running a search adds nothing new after the first hit |
| Results-view scoping | `GET /api/jobs/searches/{id}` and `GET /api/jobs/searches/{id}/postings` gain a **required `profile_id` query param**; unknown or mismatched profile vs `job_search.profile_id` → **404** (never 403 — do not reveal the search's existence) | ⚠ owner sign-off: there is no auth/session in this single-user app, so the backend needs the caller to state which profile it is operating as (the `/jobs` page knows it after #25's URL-param convention and passes it). Also leak-proof by default: an old client that doesn't pass the param gets a 404-style failure, not a leak |
| `run_search` payload reuse | `start_search` validates presence of `profile_id` before creating the run row; `run_search` re-validates and stamps the run row with `profile_id` | Background task re-uses the stored `JobSearchRequest`; the migration backfill guarantees historical rows have an owner |
| Corpus scoping of `rescore_matches` | **Not in this issue** (data layer only) | Belongs to #25 per the v3 issue split; nothing here breaks #25's join (`search_posting → job_search.profile_id`) |

## Scope

### Migration `0013_add_job_search_profile_and_search_posting`

- `job_search.profile_id`: FK → `profile.id` `ON DELETE CASCADE`, **nullable first**;
  `profile_id` column indexed (FK-index standard).
- Backfill (`server_default`-free, bulk SQL via `exec_driver_sql` for the data step,
  schema via `op.*`):
  1. `UPDATE job_search SET profile_id = (query->>'profile_id')::uuid WHERE … AND profile exists` — parameterized (`sqlalchemy.text` with params, no f-strings).
  2. Remaining orphan rows adopt the most-recently-updated profile (single `UPDATE … FROM (SELECT id FROM profile ORDER BY updated_at DESC LIMIT 1)`).
  3. `ALTER … SET NOT NULL`.
- New table `search_posting` as decided above.
- Backfill `search_posting` from `job_posting.job_search_id` (`INSERT INTO search_posting (search_id, posting_id) SELECT job_search_id, id FROM job_posting WHERE job_search_id IS NOT NULL ON CONFLICT DO NOTHING`).
- Drop `job_posting.job_search_id` (and its index).
- Downgrade: recreate `job_posting.job_search_id` (nullable, indexed, `SET NULL` FK),
  repopulate from `search_posting` (first `created_at` per posting), drop `search_posting`,
  drop `job_search.profile_id` NOT NULL then the column. **Destructive** in the sense that
  search-ownership and (on downgrade) association rows are reconstructed lossily — noted
  in the docstring.

### Models (`app/models/`)

- `job_search.py`: `profile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("profile.id", ondelete="CASCADE"), index=True)`; relationship `profile` optional.
- `job_posting.py`: delete the `job_search_id` mapped column.
- New `SearchPosting` (in `job_search.py`, following the one-file-per-domain convention; export in `models/__init__.py`): `id`, `search_id`, `posting_id`, `created_at`; table-level unique + indexes.

### Schemas (`app/schemas/job_search.py`)

- `JobSearchRequest.profile_id` stays `uuid.UUID | None` (validation of absence moves to
  the service; unknown → 404 from the service).
- No response-schema change required — `JobSearchStatusResponse.query` already echoes the
  stored request and will now include `profile_id`.

### Services

- `ingestion.py`:
  - `start_search`: raise `MissingProfileIdError` (400) when `payload.profile_id is None`; verify the profile exists — `await session.get(Profile, …)` — else raise `ProfileNotFoundError` (404, reuse existing error); stamp `JobSearch(profile_id=payload.profile_id, …)`.
  - `run_search`: same validation before `_run_matching` (defensive; task payload == stored query).
  - `_upsert_posting`: no `job_search_id` in either insert or update set; after the upsert, resolve the posting PK (`stmt.returning` or select by `(source, external_id)`) and execute the `search_posting` idempotent insert.
  - `get_search_postings`: query → `select(JobPosting).join(SearchPosting, …).where(SearchPosting.search_id == search_id)` (append-only semantics: a posting re-found in a later search stays listed on the earlier search too).
  - New `_require_owned_search(session, search_id, profile_id)` helper: `JobSearchNotFoundError` (404) when the run is unknown **or** `run.profile_id != profile_id`; used by both GET-path services.
- `matching.py`: `refresh_matches_for_search` drops the `latest_profile_id()` fallback (function + import removed); corpus filtering itself is #25.

### Router (`routers/jobs.py`)

- `GET /api/jobs/searches/{search_id}` and `GET /api/jobs/searches/{search_id}/postings` gain required `profile_id: uuid.UUID` query param, forwarded to the service.

### Errors (`errors.py` + central handlers)

- `MissingProfileIdError` (400): "profile_id is required".

### Frontend impact

None in this issue beyond API surface: `lib/api/schema.d.ts` regenerated — `profile_id`
required on `/api/jobs/search` and the two GET endpoints. No UI work (#25 owns it).

## Tests (tests mirror `app/`)

- Migration (scratch Postgres, migrations applied — never SQLite):
  - up/down round-trip on a seeded dataset; backfill correctness: search row with valid `query->>'profile_id'` → that profile; search row with a stale/absent echo → most-recent-updated profile; zero NULLs after up; `search_posting` row exists per non-null backfilled `job_search_id`; after up, `job_posting.job_search_id` gone.
- `tests/services/test_ingestion.py`:
  - `start_search` without `profile_id` → 400 `MissingProfileIdError`; with unknown → 404; run row persisted with `profile_id`.
  - Two same-source runs (same + different profile): `search_posting` idempotent (no duplicate `(search_id, posting_id)`); posting found again in a later search gains a **new** association row, and a prior search's association row is untouched (overwrite hazard regression test).
  - `get_search_postings` returns postings joined via `search_posting` (including those re-found by another search); 404 when `profile_id` mismatches the run's owner.
- `tests/test_job_endpoints.py`: status + postings endpoints require `profile_id` param; mismatch → 404; matching values → 200.
- `conftest.clean_tables` gains `search_posting`; fixtures for two profiles.

## Definition of done

- `ruff check . && ruff format --check . && pytest` green in `backend/`.
- Migration `0013` generated (autogenerate), reviewed against this plan, up/down verified on scratch Postgres.
- Live check: two profiles; search as profile A → `job_search.profile_id` = A; `GET …/searches/{id}?profile_id=B` → 404; same posting re-found by B's search → `search_posting` has two rows, A's view unchanged.
- `docs/architecture.md` ER + API table rows updated; `docs/guide/03-job-discovery-and-matching.md` notes per-search profile ownership; `node scripts/render-diagrams.mjs` re-run.
- `frontend/lib/api/schema.d.ts` regenerated (`npm run generate:api`) — `profile_id` required on `/api/jobs/search` and the two GET endpoints.

## Out of scope (this issue)

Scoped matching corpus + `rescore_matches` rewrite + `POST /api/profiles/{id}/rebuild-matches` (#25), all frontend form/URL-param/rebuild work (#25), expiry & freshness (M2: #26/#27), capabilities & per-source filters (M3: #28/#29, including `SourceQuerySpec.options`), deleting matches on upgrade (nothing scored today is deleted; D7's rebuild affordance lands in #25).
