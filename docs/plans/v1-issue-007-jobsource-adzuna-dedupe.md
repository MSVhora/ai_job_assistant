# Issue #7 — JobSource Interface + Adzuna Adapter + Dedupe

**Status:** Done (2026-09-01)
**Tracks:** GitHub issue #7 (Day 6, Week 2 — first ingestion issue)
**Plan of record:** [v1-implementation-plan.md](v1-implementation-plan.md) §4 (data model), §5 (connector interface), §8 Day 6
**Depends on:** Issues #1–#6 (done). pgvector extension already exists (`0001`); embeddings land in #9.

---

## Goal

Lay the connector foundation and prove it end-to-end with one real source: a `JobSource`
protocol + registry, an Adzuna adapter (official API, free key), and a background
ingestion run that normalizes postings into `job_posting` with `(source, external_id)`
dedupe. A failing source is skipped with a warning recorded on the run — it never fails
the search.

**Acceptance (issue):** Adzuna search persists normalized postings; dedupe works; connector
testable with fixture payloads.

## Locked decisions

| Decision | Choice | Rationale |
|---|---|---|
| Country source | **Parsed from the resume into the profile + required for search** — owner decision 2026-09-01. `StructuredProfile.contact` gains `country` (ISO-3166-1 alpha-2); extraction prompt captures it, gap-fill asks for it when missing; `POST /api/jobs/search` requires a valid `country` in the body — no search until filled | Adzuna API needs a country code in the URL path; profile is the natural home (multi-profile ready); backend never trusts the client to have pre-filled it |
| Re-search dedupe | **Upsert + refresh**: `ON CONFLICT (source, external_id) DO UPDATE` refreshes mutable fields (title, url, location, type, description, salary, posted_at, raw_payload) and stamps `job_search_id`/`fetched_at`; PK stays stable | Re-runs stay idempotent and fresh; stable PKs keep future `match` FKs valid across re-searches |
| `GET /api/sources` | **Included in #7** — registry + source listing ship together; the disclosure acknowledgment + `/api/sources/{name}/enable` flow stays in #8 | Registry is a #7 checklist item; #8's UI needs the listing |
| Search consent | **Explicit only, never automatic** — owner decision 2026-09-01. Runs start solely from `POST /api/jobs/search`; no auto/implicit triggers (no page-load, profile-completion, or gap-fill-completion searches — ever). The exact query to be sent is always shown and **editable** before submitting (UI lands in #8 per [UI plan §6.5](v1-ui-implementation-plan.md), which already mandates a seeded, editable search bar); the run status response echoes the exact stored query so the UI can show what was searched | User consent + transparency: searching costs the user's API quota and contacts third parties — it must never happen without a deliberate action on a reviewed query |
| Run status tracking | New `job_search` table (`pending → running → succeeded \| partial \| failed`) + `GET /api/jobs/searches/{id}`; per-source outcomes stored as jsonb on the run | Standards: long-running work must be DB-queryable; the run banner (#8+) and per-source warnings need a home. Maps to plan-of-record `search_query_id` (renamed `job_search_id`) |
| `source` column | Plain `text`, not a native enum | New sources must be config-only additions; an enum would need `ALTER TYPE` per connector |
| `job_type` / `remote_type` | Named native PG enums, **nullable** (values: `full_time, part_time, contract, internship, temporary` / `remote, hybrid, on_site`) | DB standards; sources rarely populate both — mapper sets null over guessing |
| `url` column | Added to `job_posting` (nullable text) — **amends the §4 sketch** | A listing without a click-through link is useless; trivial additive change |
| Adzuna pagination | Page 1 only, `results_wanted` default 50 / cap 50 (Adzuna per-page max) | Demo-scale; multi-page loop deferred until a need shows up |
| Registry form | Code-level registry dict (`registry.py`); `connectors.yaml` deferred to #8 | Config-driven actors are #8's problem; one native source doesn't need YAML yet |
| Connector shape | `search()` → `list[RawJobPosting]`, `normalize(raw)` → `JobPostingData` (pydantic); plus `is_configured()` on the protocol (addition to §5 sketch) | Keep §5's two-step shape; mappers stay pure and fixture-testable; registry needs a configured-check to pick enabled sources |
| HTTP client | `httpx.AsyncClient` promoted from dev dep to runtime dep | Async HTTP for connectors; `MockTransport` powers adapter tests without network |

## Scope

### Backend

**Migration `0007_add_job_search_and_job_posting`**
- `job_search`: `id` uuid pk, `status` enum `job_search_status`, `query` jsonb (validated
  request), `results` jsonb (per-source `{source, status, count, warning?}`), `created_at`,
  `updated_at`
- `job_posting`: `id` uuid pk, `source` text, `external_id` text, unique `(source, external_id)`,
  `title`, `company`, `url` (nullable), `location` (nullable), `job_type` enum (nullable),
  `remote_type` enum (nullable), `description` text (nullable), `posted_at` timestamptz
  (nullable), `salary_min`/`salary_max` numeric (nullable), `currency` text (nullable),
  `raw_payload` jsonb, `fetched_at` timestamptz server default now, `job_search_id` uuid FK
  nullable + indexed, index on `posted_at`
- Downgrade drops tables + enums; note: embedding vector column intentionally deferred to #9
  (dimension pinned there with the embedding model choice)

**Models** — `models/job_search.py`, `models/job_posting.py` (SQLAlchemy 2.0 `Mapped[]` style)

**Connectors — `app/adapters/job_sources/`**
- `base.py`: `JobSource` protocol, `JobSearchQuery` {query, location?, country, results_wanted},
  `RawJobPosting` {external_id, payload}, `JobPostingData` (pydantic, job_posting columns),
  `ConnectorError`
- `adzuna.py`: `GET {base}/v1/api/jobs/{country}/search/1` with `app_id`/`app_key`/`what`/
  `where`/`results_per_page`; mapper: `id`→`external_id`, `title`, `company.display_name`,
  `location.display_name`, strip HTML from `description`, `contract_time`→`job_type`
  (falls back to `contract_type` map), `salary_min`/`salary_max` (`currency` left null —
  Adzuna search results carry no currency field; derivable from country later if needed),
  `created`→`posted_at`, `redirect_url`→`url`, full response item → `raw_payload`.
  `remote_type` stays null (no Adzuna signal). One retry on 429/5xx with short backoff,
  else `ConnectorError`; bad key → `ConnectorError`
- `registry.py`: `name → instance`; `list_sources()` → `{name, is_official_api,
  disclosure_required, is_configured}`; `enabled_sources()` filters on `is_configured()`

**Ingestion — `app/services/ingestion.py`**
- `start_search(session, request) -> 202`: validate source names (unknown → 400), at least
  one enabled source (else 400 `NoJobSourcesConfiguredError`), insert `job_search`
  (`status=pending`), `BackgroundTasks.add_task(run_search, search_id)`
- `run_search(search_id)`: **fresh session** from `session_factory` (background task
  outlives the request; DbCommitMiddleware already committed the row); status→running;
  per source: search → normalize → upsert, record count; any failure → record warning,
  continue; final status `succeeded` / `partial` / `failed`. Never raises
- `get_search_status(session, search_id)`: 404 if unknown

**Schemas** — `schemas/job_search.py`: `JobSearchRequest {query, location?, country (required,
alpha-2, lowercased), results_wanted (default 50, ≤50), sources? (list[str])}`,
`JobSearchStartResponse {search_id, status}`, `JobSearchStatusResponse {search_id, status,
query, results}`, `SourceInfoResponse`

**Country lands in the profile (owner decision — minimal amendments to #3/#5 surfaces)**
- `StructuredProfile.contact` gains `country: str | None` with alpha-2 normalization
  validator; extraction prompt instructed to output ISO alpha-2 from address/location
- Gap-fill completeness includes `country` when missing (text input, validated)
- `fakes.VALID_PROFILE` + extraction/gap-fill tests updated

**Router** — `routers/jobs.py`: `POST /api/jobs/search` (202), `GET /api/jobs/searches/{id}`,
`GET /api/sources`. HTTP layer only; tags/prefix per conventions

**Errors** — `errors.py`: `NoJobSourcesConfiguredError` (400), `JobSearchNotFoundError` (404),
`UnknownJobSourceError` (400). Connector failures are run warnings, not domain errors

**Config** — no new env vars (`adzuna_app_id`/`adzuna_app_key` exist; no `ADZUNA_COUNTRY` —
country comes from the profile/request). `.env.example`: comment that Adzuna keys enable job
search

### Tests

- `tests/fixtures/adzuna_search_response.json` — trimmed real-shaped payload
- `tests/adapters/test_adzuna.py` — mapper correctness (happy path, missing/odd fields,
  HTML strip, `contract_time` precedence) via `normalize(fixture)`; `search()` via
  `httpx.MockTransport` (params + auth, 429 → retry → success, 401 → `ConnectorError`)
- `tests/services/test_ingestion.py` — fake sources injected into registry
  (`fakes.FakeJobSource`, scripted results/exceptions): postings persisted; run twice → same
  PKs, refreshed fields (dedupe); one source fails → `partial` + warning, other source still
  persists; all fail → `failed`; unknown source / none configured → 400 paths
- `tests/test_job_endpoints.py` — 202 start + status flow (status echoes the stored query);
  `GET /api/sources` shape; 404
  unknown run; request validation (country, unknown source)
- `conftest.clean_tables` gains `job_posting, job_search`

### Doc impact

- `docs/plans/v1-implementation-plan.md`: §4 job_posting sketch annotated (`url` column,
  `search_query_id` → `job_search_id`/`job_search` table)
- `docs/architecture.md`: connector registry block + ER (job_search, job_posting) + API table
- `docs/guide/03-job-discovery-and-matching.md`: mark search/ingestion/dedupe as landed;
  document the consent behaviour (search runs only when the user submits a reviewed,
  editable query; embeddings/re-rank sections stay "planned")
- `docs/guide/01-getting-started.md` + `.env.example`: Adzuna key note
- Frontend `lib/api/schema.d.ts` regenerated (`npm run generate:api`) — backend surface changed

## Definition of done

- `ruff check . && ruff format --check . && pytest` green in `backend/`
- `npm run lint && npm run build` green in `frontend/` (types regenerated)
- Migration `0007` generated, reviewed, applied; up/down verified
- Live check: real Adzuna key → search persists postings; second identical search hits
  dedupe (same PKs, updated `fetched_at`)
- Docs updated; diagrams re-rendered (`node scripts/render-diagrams.mjs`)

## Out of scope (this issue)

Embeddings + vector column + hard filters (#9), Apify framework + Google Jobs/Indeed actors +
disclosure/enable flow (#8), matching/rerank/rationale + `GET /api/matches` (#10), priority
weighting (#11), **all `/jobs` UI including the consent + editable-query search form (built
with #8's frontend)**, multi-page Adzuna pagination, cross-source fuzzy dedupe, per-posting
detail endpoint, filters UI.
