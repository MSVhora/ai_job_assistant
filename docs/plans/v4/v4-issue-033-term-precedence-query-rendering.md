# Issue #33 — Deterministic term precedence per source in query rendering (M1)

**Status:** Implemented (branch `v4/33-term-precedence-query-rendering`; implementation notes: LinkedIn precedence keeps the legacy spec.query pass-through when no title exists (user-typed > title+skills NL synthesis > spec.query) — the plan's "query-only" family covers both user-typed and spec-only cases; `{query}` remains a generic placeholder untouched by plans, `{keywords}` is the plan-resolved one; `TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/ai_job_assistant_test` runs the full suite green (384 tests))
**Tracks:** GitHub issue #33 (milestone `v4`, Phase A / M1)
**Plan of record:** [v4-search-relevance-plan.md](v4-search-relevance-plan.md) Problem 4
**Depends on:** #32 (merged — YOE/seniority land in the spec context; not consumed here but shares the M1 branch); #31 (merged — specs arrive grounded and cached; rendering consumes them unchanged)
**Blocks:** #34 (Adzuna dialect — `what_and` mapping slots into the TermPlan introduced here) and #35 (LinkedIn dialect — NL-brief composition content builds on the moved composition). The TermPlan shape below is #34's first consumer contract

---

## Goal

`title_phrase` and the free-text query are mutually exclusive per source in the
connector layer, not the rendering layer:

- Adzuna `_apply_search_terms` (`adapters/job_sources/adzuna.py:60-71`): with a
  title → `what_phrase` + `what_or`(skills) + `what_exclude`, and the
  effective query (`spec.query`, else the request's `query`) is discarded; with
  no title → the effective query becomes `what`.
- Apify LinkedIn (`adapters/job_sources/apify.py:44-67`): `_natural_keywords`
  always synthesizes `"{title} with {a and b}, offering X or more"` and
  `_with_effective_query` overrides `query` with it — so the LLM-composed
  `spec.query` never reaches LinkedIn when a title exists (and a user-typed
  request query is clobbered too).

The per-source dialect decisions (what combines with what, what overrides
what) live half in the connectors, against the layering rule. This issue
centralizes them in `services/query_rendering.py` as a per-source **term
plan**, makes the precedence deterministic, and turns both connectors into
mechanical mappers.

## Locked decisions

| Decision | Choice | Rationale |
|---|---|---|
| TermPlan shape | New `TermPlan` model in `adapters/job_sources/base.py` (next to `JobSearchQuery`): `what_and: list[str]`, `what_or: list[str]`, `what_phrase: str \| None`, `what_exclude: list[str]`, `what: str \| None` (Adzuna slots) + `keywords: str \| None` (LinkedIn NL string), `location: str \| None`, `date_posted: str \| None` (bucket) | The issue names exactly these slots per source. One flat model keeps the rendering dispatch table-driven; `what_*` slot names intentionally mirror Adzuna's param names so the connector map is 1:1. The `keyword`/date slots are simply left unset for Adzuna plans and vice versa — model-level unused ≠ dead code, the two dialects share the type |
| Transport | `JobSearchQuery` gains `term_plan: TermPlan \| None = None`; the scalar term fields (`title_phrase`, `skills_any`, `exclude_any`) are **removed** (cut over, not duplicated); `query` stays as the generic free-text field for adapters that don't get a plan | "Connector interface unchanged" holds: the `JobSource` protocol signature (`search(query: JobSearchQuery)`) is untouched; `JobSearchQuery` is the transport model, not the interface. Keeping both the legacy scalars and the plan would be double bookkeeping with two sources of truth |
| Precedence — Adzuna (locked table) | `what_phrase` ← spec.title when set; `what_or` ← spec.skills when set (space-joined at param-map time); `what_and` ← **empty until #34** (spec gains `skills_all` there); `what_exclude` ← spec.exclude when set; `what` ← spec.query else request `query`, sent **only when `what_phrase` is None** | The issue text locks this exact combination ("Adzuna combines what_phrase + what_and/what_or + what only when no phrase"). It preserves today's Adzuna behavior but moves the decision out of the connector where it can be unit-tested without HTTP mocking. Note: with a title, `spec.query` still doesn't reach Adzuna — now as an explicit, documented rule rather than an accident |
| what_and slot pre-#34 | Slot exists, always `[]` until #34 populates it | The issue text defines the plan shape including `what_and`; #34 lands days later and fills it from `skills_all`. Adding it here avoids #34 re-churning the TermPlan/connector contract |
| Precedence — LinkedIn (locked table) | `keywords` ← request `query` (**user-typed**) when set — the override; else NL string `"{title} with {a and b}"` joined from spec.title + spec.skills; salary suffix (`, offering X or more`) kept verbatim from today's composition; title-less and query-less → `ConnectorError` (unchanged) | The issue/v4-plan wording is precise: "joins title + skills into the NL string but a user-typed `query` overrides". The *composition content* (which skills, seniority phrasing) is #35's job — moving the composition code verbatim into rendering is all that happens here, so LinkedIn behavior changes only in the user-override case |
| LinkedIn + spec.query | **spec.query is not rendered into the NL string** (unchanged from today: when a title exists, the synthesis wins over any stored spec.query) | v4 plan says "LinkedIn joins title + skills" — the LLM's spec.query consciously doesn't compound into the keywords; reworking which spec fields feed the NL brief is Problem 5.1 / #35 |
| Where the guard lives | Connectors keep a dumb empty-guard ("no terms at all → `ConnectorError`") because hand-constructed queries bypass rendering; the *conditional* logic has no place outside rendering | The do-not-crash contract for direct `JobSearchQuery` construction is preserved; rendering additionally never produces an empty plan |
| Source dispatch in rendering | By source name — `"adzuna"` exact, `"apify_"` prefix (LinkedIn is whichever actor source); any other source → `term_plan=None` and today's generic pass-through | The dialect tables are per-source by definition (Adzuna API params vs LinkedIn AI-search NL); prefix dispatch matches `ApifyActorSource` naming. The `supports_exclusions`-style capability flag machinery stays untouched; a generic TermPlan-capability surface is deferred unless a third source arrives |
| `date_posted` in the plan | Rendering computes the bucket with the existing `date_posted_bucket(max_days_old)` helper into `term_plan.date_posted` for `(apify_)linkedin`; `connectors.yaml` placeholder resolution reads the plan first, with the legacy compute-from-`max_days_old` fallback for plan-less queries | The issue lists `date_posted` as part of the LinkedIn plan; keeping the helper's computation exactly where all term decisions now live makes the precedence single-sourced. The `{date_posted_bucket}` placeholder keeps its name so `connectors.yaml` only changes where it's consumed |
| `{query}` placeholder | For apify actors, `connectors.yaml` changes `keywords: "{query}"` → `keywords: "{keywords}"`; `_PLACEHOLDER_KEYS` gains `keywords`; config.py `case "query"` keeps resolving `query.query` as the generic fallback | After the cut-over, LinkedIn's effective text lives in the plan, not in `query.query` — pointing the placeholder at the plan makes `build_actor_input` truly mechanical. `{location}` resolution adds a plan-first branch (`term_plan.location`) with the existing fallback |
| Request-side semantics | No `JobSearchRequest` / `SourceQuerySpec` schema change; `base_query` keeps meaning "the user-typed request query" (delivery in `ingestion._run_source:194` unchanged) | The fix is layering + precedence, not new inputs; spec shapes were just re-locked in #31 and should not churn |

## Scope

### Migration

None. Rendering/adapter-only change; no model, schema, or connector-config
shape change (`connectors.yaml` placeholder rename is config, not schema).

### Backend (`backend/app/`)

- `adapters/job_sources/base.py`:
  - New `TermPlan` model (slots per the locked decision, char/list caps
    aligned with `SourceQuerySpec` limits — reuse them, don't re-invent).
  - `JobSearchQuery`: add `term_plan: TermPlan | None = None`; remove
    `title_phrase` / `skills_any` / `exclude_any` (and the `_strip_title`
    validator with them); `query` stays.
- `services/query_rendering.py` — the whole precedence layer:
  - `build_connector_query()` dispatches: adzuna →
    `_render_adzuna_plan(...)`; `source_name.startswith("apify_")` →
    `_render_linkedin_plan(...)`; other → no plan (legacy kwargs only).
  - Both helpers return a `TermPlan`; the connector-docstring precedence
    table lives here too as the single normative source.
  - `_effective_query()` keeps the spec.query-else-base_query rule for the
    Adzuna `what` slot; the LinkedIn user-override check happens in
    `_render_linkedin_plan` (base_query first, then synthesis).
- `adapters/job_sources/adzuna.py`:
  - `_apply_search_terms` → mechanical map from `query.term_plan`
    (`what_phrase`, `what_and`, `what_or`, `what_exclude`, `what`; empty-plan
    guard preserved). Members hold the (now-migrated) precedence table in
    the class docstring, pointing at `query_rendering.py` as the normative
    copy. No other behavior.
- `adapters/job_sources/apify.py`:
  - Delete `_natural_keywords` and `_with_effective_query`; `search()` keeps
    composing via `build_actor_input` and never rewrites the query object
    (`effective = _with_effective_query(query)` call removed). Empty-guard
    preserved ("search needs a query or a title phrase").
  - Class docstring gains the LinkedIn precedence table (user query >
    title+skills NL synthesis; spec.ignore rule stated).
- `adapters/job_sources/config.py`:
  - `_PLACEHOLDER_KEYS`: add `"keywords"`; `{date_posted_bucket}` /
    `{location}` resolve plan-first (`term_plan` present) with the legacy
    computation as fallback.
- `adapters/job_sources/connectors.yaml`:
  - `keywords: "{query}"` → `keywords: "{keywords}"` (apify_linkedin).

### Tests

Backend (`backend/tests/`):

- `test_query_rendering.py` — the DoD's precedence matrix, one case family
  per source (title+query, title-only, query-only) plus the no-terms guard:
  - adzuna title+query → plan has `what_phrase` + `what_or` + `what_exclude`,
    `what` **None**.
  - adzuna title-only → same minus `what`.
  - adzuna query-only → `what` = spec.query; fallback: `what` = base_query
    when spec.query absent (existing `_effective_query` cases retained).
  - adzuna neither → `ConnectorError` from rendering (and the connector's
    own guard asserted once via a hand-built empty plan).
  - adzuna plan always sets `what_and == []` (until #34) — pinned so #34's
    diff is visible.
  - (apify_)linkedin title+query → `keywords` = user-typed query (override
    wins over synthesis).
  - linkedin title-only → `keywords` = `"{title} with {a and b}"` + salary
    suffix when salary_min/currency set (composition verbatim as today).
  - linkedin query-only (no title) → `keywords` = user-typed query.
  - linkedin neither → `ConnectorError`.
  - linkedin `date_posted` bucket present and matches `date_posted_bucket()`.
  - unknown source name → no plan, legacy pass-through (regression lock for
    the dispatch default).
- `test_adzuna_adapter.py`: term-table tests build `JobSearchQuery` with
  `term_plan=TermPlan(...)` instead of the removed scalars (line ~245-250);
  param mapping (`what_phrase`/`what_or`/`what_and`/`what_exclude`/`what`
  space-joins) asserted mechanically; empty-plan guard.
- `test_apify_adapter.py`: same cutover (~line 278-282); actor input
  `keywords` equals the plan's keywords; the old "synthetic NL always
  overrides" assertion is replaced by the user-query-override assertion;
  empty-guard preserved.
- `test_ingestion.py` (~303-305) / `test_job_endpoints.py` (~299):
  end-to-end assertions move to `term_plan` fields; the run flow's
  "requires effective query" 400 cases unchanged.
- New coverage for `config.py`: `{keywords}` placeholder validation +
  resolution; `{date_posted_bucket}` plan-first fallback.

### Gates

- Backend: `ruff check . && ruff format --check . && pytest` green (in
  `backend/`).
- Frontend: untouched — `npm run lint && npm run build` still green but no
  type regen needed (no OpenAPI shape change; `TermPlan` never crosses the
  HTTP boundary, it's internal connector transport).
- `.env.example` / README: unchanged (no new Settings).
- Docs: `docs/architecture.md` query-rendering step mentions the per-source
  term plan + precedence table; `docs/guide/03-job-discovery-and-matching.md`
  notes the user-visible deltas (user-typed query now wins on LinkedIn;
  Adzuna combination rule). Re-run `node scripts/render-diagrams.mjs` only
  if a diagram actually changes.

## Risks

| Risk | Mitigation |
|---|---|
| Cutting over `JobSearchQuery` term fields touches every connector test at once | Mechanical rename (`title_phrase=…` → `term_plan=TermPlan(what_phrase=…)`); no logic in test bodies; pytest green is the gate |
| A third source (or a new Adzuna-style param) regresses the precedence silently | The precedence matrix in `test_query_rendering.py` is per-source and exhaustive over populated-slot combinations; new sources inherit the plan=None pass-through, so behavior is unchanged by default |
| `what_and` = [] until #34 could tempt reordering #34 first | Accepted — one dead slot for days; the plan pins it so the contract is explicit |
| User-typed-query override changes LinkedIn results vs today | It's the issue's intent (request queries were silently clobbered); single short string left as-is in the change docs; composition content untouched, so only the override case differs |
| Adzuna `what_phrase` + `what_or` combination semantics | Already shipped today (`adzuna.py:61-66`) — unchanged here; `what_and` combination quality is #34's test burden |

## Out of scope (this issue)

- `what_and` population from must-have skills / `skills_all` spec field —
  Problem 3 / #34.
- Composing the LinkedIn NL brief from the parsed profile (seniority, YOE
  lines), salary-text removal, exclusions-in-NL — Problem 5 / #35.
- `salary_include_unknown`, `title_only` parallel pass, pagination/quota —
  #34.
- Rendering-side `run.query` echo shape changes (`JobSearchQuery` dumps
  through the status echo only as `source_queries` already persisted).
- Any change to `SourceQuerySpec`, `JobSearchRequest`, registry, or the
  `JobSource` protocol.
