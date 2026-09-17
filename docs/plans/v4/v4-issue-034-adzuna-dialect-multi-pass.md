# Issue #34 — Adzuna dialect: what_and, title_only pass, salary_include_unknown, pagination + quota budget (M2)

**Status:** Implemented (branch `v4/34-adzuna-dialect-multi-pass`; implementation notes: the contract/type filter became a single optional `job_type` select after owner review — Adzuna ANDs its booleans, so four independently-checkable boxes could silently zero out a search; 396 tests green with `TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/ai_job_assistant_test`)
**Tracks:** GitHub issue #34 (milestone `v4`, Phase B / M2)
**Plan of record:** [v4-search-relevance-plan.md](v4-search-relevance-plan.md) Problem 3
**Depends on:** #31 (merged — grounded, hash-cached specs), #32 (merged — YOE/seniority in profile), #33 (merged — `TermPlan` transport with the `what_and` slot reserved, pinned `[]` until this issue)
**Blocks:** nothing in the v4 sequence (Problem 5 / LinkedIn dialect is independent)

---

## Goal

Adzuna supports far more than the connector uses today (`adzuna.py` sends only
`what`/`what_phrase` + `what_or` + `what_exclude`, salary, `max_days_old`).
This issue fills the reserved `what_and` slot from a new must-have skills spec
field, adds an automatic `title_only` second pass (deduped), stops silently
biasing results to salary-publishing companies, and paginates page 2 within the
free-tier quota — all inside the `JobSource` connector interface, with nothing
new required in the UI.

Budget formula (documented in the connector docstring, enforced by setting):
**calls per run = Σ (sub-queries × pages fetched)**. Default sub-queries = 2
(broad + title-only) and pages ≤ 2 ⇒ default cap 4 respects Adzuna's free tier
(25/min, 250/day, 1000/wk, 2500/mo).

## Locked decisions

| Decision | Choice | Rationale |
|---|---|---|
| `skills_all` spec field | `SourceQuerySpec` gains `skills_all: list[str] \| None` (same cap as `skills`: ≤ 3, strip/validate identical). Existing `skills` keeps its name and becomes explicitly the *nice-to-have* list (`skills_any` semantics, → `what_or`); no stored-data rename — the JSONB field name is unchanged | Renaming `skills` would churn every stored spec, the LLM contract, and the frontend for zero behavior gain. A new sibling field is additive and validated by the same helpers. `skills_all` (+`skills`) fill `what_and`+`what_or` respectively and pick up the empty-defaults contract #33 pinned |
| `what_and` mapping | `spec.skills_all` → `term_plan.what_and` (rendered space-joined at param-map time by the connector, as `what_or` already is). Legacy specs without `skills_all` → `what_and=[]`, no behavior change | The slot exists and is pinned by #33; this issue only populates it. Mapping stays mechanical in `adzuna.py` |
| Prompt update | `QUERY_SYSTEM` gains: `skills_all = up to 3 must-have stack keywords` / `skills = up to 3 nice-to-have or adjacent keywords`; both optional (`skills_all` empty when the resume shows no clear must-have core). `PROMPT_VERSION` → `search_query_v4` | Version bump is the mechanism to invalidate every stored `queries_input_hash` (the hash covers `prompt_version`), regenerating all specs with the new split at temperature 0 |
| Auto `title_only` pass | Connector `search()` runs **(a)** the broad pass (current params, page 1) then **(b)** a `title_only=true` pass — only when `term_plan.what_phrase` is set **and** the user did not explicitly set `options.title_only=true`. Results merged **dedupe by `external_id`, broad-pass winner** (first occurrence kept). Explicit `title_only=true` → single call, exactly today's behavior | Title matches are the highest-precision signal and are already an Adzuna param; auto-adding recall from the broad pass is the community multi-pass pattern. Keeping the explicit option authoritative avoids surprising power users with double calls. Dedupe by `external_id` mirrors ingestion's `(source, external_id)` uniqueness — no cross-source logic here |
| `salary_include_unknown` | Send `salary_include_unknown=1` when **`query.salary_min` is None** (shared filter, post-profile-resolution — so "profile has no salary floor" and "user chose not to set one" behave the same); omit whenever a floor is set | Gate on the resolved query, not the profile: `resolve_profile_defaults` (#31) already implements "request wins over profile", and the connector must not re-read profiles. This stops silently dropping postings whose `salary_min` is unknown whenever a floor exists — today those vanish from results |
| Contract/type filter | A single optional **`job_type` select** (`full_time`/`part_time`/`contract`/`permanent`; a selection sends the like-named Adzuna boolean param). **No auto-derivation** — no profile/request field carries a job-type preference today (owner decisions, this issue): select replaces the originally-proposed four booleans because Adzuna ANDs them and independently-checkable `full_time`+`part_time` checkboxes could silently zero out a search | Scope item 3 honored via the existing declared-options mechanism: power users get the knob, zero new required fields, zero UI work (the filters form renders `select` declarations generically from `SourceInfoResponse.filters` automatically) |
| Pagination | Fetch page 2 (`/search/{page}=2`) only when page 1 returned **exactly** `results_per_page` rows **and** `results_wanted > fetched-so-far`. Requires raising the cap: `JobSearchRequest.results_wanted` and `JobSearchQuery.results_wanted` `le=50` → `le=100` (frontend form max bumped, slider-free numeric field, no new fields). `results_per_page = min(results_wanted, 50)` unchanged | The issue's own trigger condition ("page 1 fills 50 rows and `results_wanted > 50`") is impossible under today's `le=50` cap — the cap raise is part of this scope, and the *only* schema-adjacent change (no DB rows touched). Conditional page 2 keeps below-quota runs at 1–2 calls |
| Quota budget | New `Settings.max_adzuna_calls_per_run: int = 4` (validated `ge=1 le=8`), documented in `.env.example`. Enforced inside `AdzunaJobSource.search()`: count every HTTP call in the run; before each additional sub-query/page, stop-and-log when the budget is exhausted (postings fetched so far are returned — degrade gracefully, never fail the search for a budget overflow) | Adapter-level enforcement honors "a failing source degrades gracefully" — a budget stop is not an error worth failing a run over. A per-run count also satisfies the ToS-visibility requirement (" surfaced in logs") without global mutable state — the count is local to `search()` and logged in the completion line |
| Budget landing place | All enforcement in `AdzunaJobSource.search()`; the call count computed there already equals Σ(sub-queries × pages) by construction, so the formula holds without bookkeeping elsewhere | The issue anchors the formula to the connector docstring; making `search()` the only caller of `_get_json` for the run keeps the count trivially correct |

## Scope

### Migration

None. No model changes; `queries_input_hash` needs no new column (#31 shipped
it), JSONB-stored specs are schemaless, and the schema cap change is
application-level validation.

### Backend (`backend/app/`)

- `schemas/job_search.py`:
  - `SourceQuerySpec`: add `skills_all: list[str] | None = Field(default=None, max_length=_MAX_SKILLS)`; add it to `has_content()` and to the `_strip_terms` validator; extend the skills comments to state the must-have vs nice-to-have split.
  - `JobSearchRequest.results_wanted`: `le=50` → `le=100`.
- `services/query_builder.py`: `QUERY_SYSTEM` updated per the locked decision; `PROMPT_VERSION = "search_query_v4"`. (Generation speaks `skills_all`/`skills` split; variant-generation `previous` block needs no change — specs dump their new field automatically.)
- `services/query_rendering.py`:
  - `_render_adzuna_plan`: `what_and=(spec.skills_all or [])`, `what_or=(spec.skills or [])`; comment/docstring precedence table updated (`what_phrase` + `what_and`/`what_or` combined; `what` only when no phrase — rule unchanged from #33).
- `adapters/job_sources/adzuna.py`:
  - `_FILTERS`: add the four boolean declarations (`full_time`, `part_time`, `contract`, `permanent`; help_text "Adzuna contract filter" style, ordered after `title_only`).
  - `_apply_options`: map the four booleans → same-named params when `True`.
  - `_apply_salary_filter`: add `salary_include_unknown=1` when `query.salary_min is None` (and `salary_max` absent does not suppress it — the param is about the floor).
  - `search()` restructured into a small run driver:
    1. Build params once (`_apply_search_terms` / salary / freshness / options).
    2. Pass sequence per the locked decisions (broad page 1 → optional `title_only` pass; each pass may extend to page 2 per the pagination trigger), every extra call gated on `max_adzuna_calls_per_run`.
    3. Merge pass results deduped by `external_id` (first wins), capped so the union never exceeds `results_wanted`.
    4. Completion log gains `calls=<n>` and `passes=<k>`; the class docstring documents the budget formula and call budget.
  - Keep `_MAX_RESULTS_PER_PAGE = 50`; per-pass page-2 uses the same `results_per_page`.
- `core/config.py`: `max_adzuna_calls_per_run: int = Field(default=4, ge=1, le=8)`.
- `.env.example`: document the setting with the free-tier limits + point at the connector docstring.

### Frontend

- Regenerate `lib/api/schema.d.ts` (`SourceQuerySpec` gains `skills_all`; `results_wanted` max changes are numeric only).
- Source filters form: no change needed (booleans render from declarations) — verify once, don't edit.
- Search form: cap the results-wanted input at 100 (was 50) to match the schema.
- Query-spec review UI: if it displays a spec's skills, show `skills_all` as must-haves (label) beside nice-to-haves; tolerate its absence (old stored specs).

### Tests (`backend/tests/`)

- `test_query_rendering.py`: `what_and` populated from `spec.skills_all` (title+both skill lists case); legacy spec (`skills_all` absent) → `what_and == []` (un-pin the #33 assertion, now asserted as the legacy-spec case).
- `test_adzuna_adapter.py` (per the issue DoD):
  - `what_and` param mapping (`"kotlin compose"` join) alongside `what_or`/`what_phrase`.
  - Two-pass behavior: with `what_phrase` + no explicit `title_only` → two calls, second has `title_only=true` + `what_phrase`; results deduped by `external_id`.
  - Explicit `options.title_only=True` → single call (no auto second pass).
  - No `what_phrase` (query-only) → single call.
  - `salary_include_unknown=1` present with no `salary_min`; absent with one.
  - Contract booleans mapped only when `True` in options.
  - Page 2 fetched when page 1 returns 50 rows and `results_wanted=100`; not fetched when page 1 < 50 or `results_wanted ≤ 50`; page-2 fixture with distinct ids.
  - Budget: `max_adzuna_calls_per_run=2` (monkeypatched settings) with a full page 1 → exactly 2 calls, partial results, no raise.
- `test_job_endpoints.py` / `test_ingestion.py`: `results_wanted=100` accepted end-to-end; fixture-driven flows keep passing on the restructured `search()` (results unchanged for single-pass path).
- `test_query_builder.py`: prompt-version bump effects (`skills_all` emitted field accepted; `_strip_undeclared_options` unaffected).

### Gates

- Backend: `ruff check . && ruff format --check . && pytest` green (in `backend/`).
- Frontend: `npm run lint && npm run build` green (in `frontend/`) — type regen + small form/UI touch.
- `.env.example` updated (`max_adzuna_calls_per_run`).
- Docs: `docs/guide/03-job-discovery-and-matching.md` (must-have vs nice-to-have split lands in stored specs; auto title-only pass; unknown-salary postings included when no floor set), `docs/architecture.md` (Adzuna multi-pass + budget note in the source-connector flow); re-run `node scripts/render-diagrams.mjs` only if a diagram actually changes.

## Risks

| Risk | Mitigation |
|---|---|
| Prompt-version bump regenerates every profile's specs (LLM cost on next search/regenerate) | Intended — the split needs real specs at temp 0; happens lazily on first use via the hash, one call per profile, bounded by existing `ensure_queries_fresh` behavior |
| New boolean filters let a user over-constrain (e.g. `full_time`+`contract`) into near-zero results | Values are optional power-user knobs like `title_only` today; Adzuna ANDs what it receives; source outcome already reports counts and the UI shows empty states |
| Auto second pass doubles quota burn per run | The budget setting (default 4 = 2 sub-queries × 2 pages) is the ceiling; stop-and-log keeps a run inside it even at full pagination |
| Two-pass dedupe differs from ingestion dedupe (external_id only here, not URL) | Correct layering: within-run dedupe is the connector's; cross-source dedupe stays ingestion's (Problem 9 territory, not this issue) |
| `what_and` + `what_or` + `what_phrase` together over-tighten Adzuna results | Community-backed combination (the params compose with AND/OR semantics precisely as Adzuna documents); covered by a mapping test pinning the join strings; the LLM is prompted to keep both lists ≤ 3 short keywords |

## Out of scope (this issue)

- Auto-derivation of contract/type booleans from profile data (needs a job-type preference field — deferred; this is connector-declared filters only).
- `category`, `what_exclude` in the prompt (only Friendship-level filters change), `location0..7` hierarchical places, `sort_by` defaults.
- LinkedIn dialect work — NL brief composition, exclusions-in-NL, `limitPerSource`, `geoId` (Problem 5 / #35).
- Run-concurrency guard and any run-model change (Problem 6).
- Scoring changes of any kind (Problem 7).
