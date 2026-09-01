# Issue #8 — Apify Connector Framework + Source Disclosure & Enable Flow

**Status:** Done (2026-09-01)
**Tracks:** GitHub issue #8 (Day 7, Week 2)
**Plan of record:** [v1-implementation-plan.md](v1-implementation-plan.md) §5 (Apify config + runner contract), §6 (`/api/sources/{name}/enable`, `/api/setup/check`), §8 Day 7; [UI plan](v1-ui-implementation-plan.md) §6.2 (`/setup`), §6.5 (`/jobs` search form + run banner), build order step 3
**Depends on:** Issues #1–#7 (done). Embeddings/vector column stay in #9.

---

## Carry-over review: gaps found in issues #1–#7 code

Checked every issue plan against the code before scoping this one. Everything marked Done
in #2–#7 is landed and tested (upload/extract/draft, profile + revisions + multi-profile,
gap-fill, ingestion run + Adzuna + dedupe, TanStack provider, generated API types). Four
items were missed or explicitly deferred here:

| Gap | Evidence | Resolution |
|---|---|---|
| `POST /api/setup/check` never built | Plan-of-record §6 lists it; UI plan §6.2 builds key-status cards on it; no `routers/setup.py`; not assigned to any of #1–#7 | **Lands in #8** (the `/setup` page needs it) |
| Disclosure/enable state has nowhere to live | Plan-of-record §6: `POST /api/sources/{name}/enable` + `acknowledged_disclosure: true`; today `registry.enabled_sources()` equates *configured* with *enabled* and nothing persists acknowledgment | **Lands in #8**: `source_state` table (migration `0008`) + enablement semantics |
| `connectors.yaml` deferred from #7 | #7 locked decision ("config-driven actors are #8's problem"); acceptance criterion §9 requires adding an actor via `connectors.yaml` + mapper without touching matching logic | **Lands in #8** (core of this issue) |
| App shell / top app bar never built | UI plan §2 locked "responsive top app bar"; `layout.tsx` has none — only in-page back-links exist | **Lands in #8**: `/setup` and `/jobs` need discoverable nav |

No other drift found: `JobSource` protocol matches the amended §5 shape (`is_configured`,
`disclosure_required` added in #7); `job_posting`/`job_search` match migration `0007`;
consent rule (explicit search only, editable query) is implemented backend-side and its UI
is assigned here per #7's out-of-scope note.

---

## Goal

Make the ingestion fan-out real: a config-driven Apify runner that executes the
`curious_coder/linkedin-jobs-scraper` actor under the user's own token, a mapper that
normalizes its dataset into `job_posting`, and the consent surface — `/setup` (key status,
source badges, disclosure modal, enable flow) and the `/jobs` search form with a live run
banner. A scraping source cannot run until its disclosure is acknowledged.

**Acceptance (issue):** both v1 sources (Adzuna + the LinkedIn actor) return normalized
postings through one search run; a new Apify actor can be added via `connectors.yaml` +
mapper without touching matching logic; scraping sources cannot be enabled without
acknowledging the disclosure; `/jobs` starts runs against enabled sources only and shows
per-source results/warnings live.

## Locked decisions (proposed — owner sign-off before build)

| Decision | Choice | Rationale |
|---|---|---|
| Apify HTTP client | **`httpx` direct against Apify REST v2** — no `apify-client` dependency | Same pattern as the Adzuna adapter; `MockTransport`-testable; the API surface used is 3 endpoints |
| Runner contract | **Async run + poll**, per plan-of-record §5: `POST /v2/acts/{actorId}/runs` → poll `GET /v2/actor-runs/{runId}` until terminal → `GET /v2/datasets/{datasetId}/items?clean=true` | §5 pins this contract. Not `run-sync-get-dataset-items`: its ~300 s wait ceiling can silently fail long scrapes |
| Poll budget | 5 s interval, 10 min cap → `ConnectorError("actor run timed out")` → source skipped with warning | Runs stay bounded; a hung actor degrades like any other failed source |
| Actor selection | **One actor in v1: `curious_coder/linkedin-jobs-scraper`** (`hKByXkMQaC5Qt9UMN`) — owner decision 2026-09-01. The runner/mapper framework stays generic; Google Jobs / Indeed actors were the plan-of-record's v1 choice but are deferred — **amends plan-of-record §1** (LinkedIn actors were listed as Phase 3+) **and §9** ("all 3 sources" → 2 sources) | Proves the config-driven framework with the source the owner actually wants; adding more actors later is YAML + mapper only |
| LinkedIn input mapping | `keywords` ← `{query}`, `location` ← `{location}` (omitted when null), `limitPerSource` ← `{results_wanted}`, defaults `datePosted: "anyTime"`, `autoConvertToAiSearch: true`, `scrapeCompany: false`, no `urls` (filters path). **`country` is not passed** — LinkedIn takes a free-text location; Adzuna stays the only consumer of the alpha-2 country | From the actor's documented input schema; `scrapeCompany: false` halves runtime and per-result cost — company blurbs aren't needed for matching |
| LinkedIn mapper | `id`→external_id, `title`→title, `companyName`→company, `link`→url, `location`→location, `employmentType` ("Full-time"… )→`job_type`, `workplaceTypes`/`workRemoteAllowed`→`remote_type`, `descriptionText`→description (HTML-strip fallback on `descriptionHtml`), `postedAt`/`postedAtTimestamp`→`posted_at`, `salaryInfo`/`salaryInsights`→`salary_min`/`salary_max` when confidently numeric (else null), full item→`raw_payload`; fixture = **real run sample captured at implementation start** (the actor's README warns its sample may be outdated) | Mappers stay pure + fixture-testable, same pattern as Adzuna |
| Actor cost | Paid per event, ~$1 / 1,000 results on the user's own Apify plan | Disclosure text and the guide must state this; results_wanted cap (50) bounds spend per search |
| `connectors.yaml` scope | YAML drives **`apify_actor` entries only**; Adzuna stays a code connector — **deviation from the §5 sketch**, which shows `adzuna` in YAML (flagged for plan-of-record review) | Adzuna has no config to externalize; YAML→class resolution for `native_api` adds indirection for zero configurability. Acceptance criterion ("new actor = YAML + mapper, no core changes") still holds |
| YAML loading | `pyyaml` (new dep — justified: stdlib has no YAML and the criterion mandates YAML) parsed into pydantic models at startup, fail fast on invalid config | Standards: required config fails at startup, not at first search |
| Enablement persistence | New `source_state` table (`source_name` pk text, `acknowledged_at` timestamptz null). **enabled = configured AND (not disclosure_required OR acknowledged)** | Acknowledgment must survive restarts (standards: DB is the state store); official-API sources stay auto-enabled when keys exist |
| Enable endpoint semantics | `POST /api/sources/{name}/enable` body `{acknowledged_disclosure: bool}`; 404 unknown source; 409 `DisclosureNotAcknowledgedError` if scraping source and flag not `true`; idempotent 200 otherwise; official-API sources no-op 200. **No disable in v1** | Plan-of-record §6 defines enable only; un-enabling is out of scope |
| Searching a disabled source | `POST /api/jobs/search` with an unacknowledged scraping source in `sources[]` → 409 `JobSourceNotEnabledError`; `sources: null` uses all enabled sources | Explicit rejection beats silently skipping a source the user asked for |
| `GET /api/sources` | Gains `enabled: bool` field on `SourceInfoResponse` | UI needs configured vs enabled vs disclosure-required to render the enable flow |
| Background re-check safety | `run_search` re-validates source selection on its fresh session; any selection failure now **marks the run `failed`** instead of raising out of the task | Closes a latent #7 edge (raise inside background task strands the run in `running`) |
| Setup check shape | `POST /api/setup/check` → `{llm_configured, embedding_configured, adzuna_configured, apify_configured, warnings: list[str]}`; embedding warning when the embedding model's provider can't embed (e.g. Anthropic-only key) | Plan-of-record §6 + risk table ("warn before first search, not at failure time"); flat booleans keep the UI dumb |
| Frontend disclosure dialog | **`@radix-ui/react-dialog`** (new dep — justified: focus trap, escape, `aria` modal semantics are the standards' hard requirements; #4's primitives are hand-rolled and cover none of that) wrapped as `components/ui/dialog.tsx` | UI plan §2 locked shadcn/Radix for exactly this modal; Radix alone is the minimal slice of that decision |
| `/jobs` results area in #8 | Search form + source multi-select + run banner (poll via `refetchInterval` while `pending/running`); after success a run summary with a "match ranking lands in the next release" placeholder — **no match cards** | UI plan build order puts match cards in #9–#11; #7's out-of-scope note puts the consent search form here |

## Scope

### Backend

**Migration `0008_add_source_state`**
- `source_state`: `source_name` text pk, `acknowledged_at` timestamptz nullable
- Downgrade drops the table

**Models** — `models/source_state.py` (SQLAlchemy 2.0 `Mapped[]`), exported from `models/__init__`

**Connector config — `app/adapters/job_sources/`**
- `connectors.yaml` (next to the package): per-actor `name`, `actor_id`,
  `external_id_field`, `input` template mapping actor-input keys → `{query}`/`{location}`/
  `{results_wanted}` placeholders; v1 ships one `apify_linkedin` entry
  (`actor_id: hKByXkMQaC5Qt9UMN`, `external_id_field: id`)
- `config.py`: `ActorConfig` pydantic model + loader; invalid/missing YAML fails startup
- `apify.py`: `ApifyActorSource` (generic, config-injected) — `is_configured()` checks
  `apify_token`; `search()` per the runner contract above (one retry on 429/5xx transport
  as in `adzuna.py`); terminal states `FAILED/ABORTED/TIMED-OUT` → `ConnectorError`
- `mappers/linkedin.py`: pure `dict → JobPostingData` per the mapper decision row;
  unmappable posting → `ConnectorError` (skipped + counted by ingestion, never fatal);
  full item → `raw_payload`
- `registry.py`: code sources + YAML actor sources merged; same accessor surface

**Source state service — `app/services/sources.py`**
- `list_sources_with_state(session)`, `enabled_sources(session)`,
  `enable_source(session, name, acknowledged)` — replaces the registry's
  `enabled_sources()` for request paths; registry stays persistence-free

**Ingestion changes — `app/services/ingestion.py`**
- `_selected_sources(session, payload)` becomes async, filters on DB-backed enablement;
  run-level re-check wrapped so selection failure marks the run `failed` (see decisions)

**Schemas** — `schemas/job_search.py`: `SourceEnableRequest {acknowledged_disclosure: bool}`,
`SourceInfoResponse` + `enabled: bool`; `schemas/setup.py`: `SetupCheckResponse`

**Errors** — `errors.py`: `DisclosureNotAcknowledgedError` (409), `JobSourceNotEnabledError` (409)

**Routers** — `routers/jobs.py` gains `POST /api/sources/{name}/enable`; new
`routers/setup.py` (`POST /api/setup/check`); both registered in `main.py`; HTTP layer only

**Config** — no new env vars (`apify_token` already exists in `Settings`/`.env.example`);
`.env.example` comment notes Apify token enables the scraper actors

### Frontend

**New dependencies:** `@radix-ui/react-dialog` (justified above); `pyyaml` on the backend.

- `components/ui/dialog.tsx` — Radix-wrapped primitive (focus trap, escape, aria)
- `components/ui/badge.tsx` — `official-api` / `third-party-scraper` variants (UI plan §4)
- App shell — top app bar in `layout.tsx` (server component) with Profile / Jobs / Setup links
- `app/setup/page.tsx` + `components/features/setup/` (`KeyStatusCards`, `SourceList`,
  `DisclosureDialog`): key status from setup/check with embedding warning; source list with
  badges always visible; enable on scraping source opens the dialog and the confirm button
  stays disabled until acknowledgment; loading skeleton per card, error + retry,
  all-configured empty state
- `app/jobs/page.tsx` + `components/features/jobs/` (`SearchForm`, `SourceMultiSelect`,
  `RunBanner`): RHF + zod form — query (seeded from active profile title/skills, editable),
  location optional, country (prefilled from profile, alpha-2 validated — backend requires
  it), results_wanted, source multi-select showing badges and enabled/disabled state;
  submit → `202` → banner polls `GET /api/jobs/searches/{id}` with `refetchInterval` while
  pending/running, then shows per-source counts/warnings; page usable during the run;
  `aria-live` status; navigating away and back doesn't break the run
- `lib/api/`: `getSetupCheck`, `listSources`, `enableSource`, `startJobSearch`,
  `getJobSearchStatus` + types; **`schema.d.ts` regenerated** (`npm run generate:api`)
- `hooks/`: `use-setup-check.ts`, `use-sources.ts`, `use-job-search.ts`

### Tests

- `tests/fixtures/`: `linkedin_dataset.json` (trimmed real run output),
  `connectors.valid.yaml` / `connectors.invalid.yaml`
- `tests/test_apify_adapter.py` — runner via `httpx.MockTransport`: input mapping, run
  creation, poll transitions, dataset fetch, `FAILED`/timeout → `ConnectorError`, 429 →
  retry → success; mapper correctness (`linkedin_dataset.json`: happy path, missing/odd
  fields, employmentType/workplaceType normalization, salary parsing)
- `tests/test_source_registry.py` — YAML load/merge, invalid config raises at startup
- `tests/test_source_endpoints.py` — `GET /api/sources` shape incl. `enabled`; enable: 404
  unknown, 409 unacknowledged, idempotent success; `POST /api/setup/check` shape
- `tests/test_ingestion.py` extended — disabled scraping source → 409 at request; ack'd
  source persists postings alongside Adzuna in one run; background selection failure → run
  `failed` (never stuck `running`)
- `conftest.clean_tables` gains `source_state`

### Doc impact

- `docs/plans/v1-implementation-plan.md`: amend §1 deferral table (LinkedIn actor moved
  into v1 via owner decision 2026-09-01), §5 sketch (one `apify_linkedin` entry; Google
  Jobs/Indeed deferred), §9 acceptance ("all 3 sources" → "both v1 sources")
- `docs/architecture.md`: `source_state` in the ER + endpoints table + connectors.yaml/Apify
  runner block; diagram labels change from "Google Jobs, Indeed scrapers" to the LinkedIn
  actor → re-render diagrams (`node scripts/render-diagrams.mjs`)
- `docs/guide/03-job-discovery-and-matching.md`: source table names the LinkedIn actor
  (Third-party scraper, paid per result on your Apify plan); disclosure/enable flow,
  `/setup`, `/jobs` search form + run banner marked live; match sections stay "planned"
- `docs/guide/01-getting-started.md`: Apify token + paid-actor note
- `.env.example` comment; frontend `schema.d.ts` regenerated
- The `adzuna`-in-YAML deviation is recorded here and flagged for the owner to accept or veto

## Definition of done

- `ruff check . && ruff format --check . && pytest` green in `backend/`
- `npm run lint && npm run build` green in `frontend/` (types regenerated)
- Migration `0008` generated, reviewed, applied; up/down verified
- Live check: real Apify token → acknowledge disclosure in `/setup` → one `/jobs` search
  returns normalized postings from Adzuna + LinkedIn with dedupe intact; unacknowledged
  source is rejected and cannot be enabled without the modal
- Responsive + a11y checklist (375/768/1280, focus trap, `aria-live`) done
- Docs updated; diagrams re-rendered

## Out of scope (this issue)

Embeddings + vector column + hard filters (#9), matching/rerank/rationale + match cards +
`GET /api/matches` (#10), priority slider (#11), filters UI (location/remote/type/date —
lands when the backend filters exist), disabling/un-enabling sources, cross-source fuzzy
dedupe, multi-page actor results, per-posting detail endpoint, Adzuna pagination.
