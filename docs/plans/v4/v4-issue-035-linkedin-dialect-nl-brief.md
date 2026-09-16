# Issue #35 — LinkedIn dialect: NL brief composition, NL exclusions, limitPerSource cap, geoId pass (M3)

**Status:** Planned
**Tracks:** GitHub issue #35 (milestone `v4`, Phase C / M3)
**Plan of record:** [v4-search-relevance-plan.md](v4-search-relevance-plan.md) Problem 5
**Depends on:** #31 (merged — profile-resolved request defaults, `location ← preferences.target_location`, `country ← contact.country`), #32 (merged — seniority parsed/derived on the profile), #33 (merged — `TermPlan` transport; LinkedIn keywords precedence pinned), #34 (merged — `le=100` results cap, multi-pass connector pattern)
**Blocks:** nothing in the v4 sequence (Problem 6 / run hygiene and Problems 7–9 are independent)

---

## Goal

Since Aug 2026 LinkedIn's forced AI (semantic) job search removed the
experience/job-type/workplace/salary URL filters; only `f_TPR`, `f_C`, `f_AL`,
`f_EA` survive, and `autoConvertToAiSearch` merely *appends* old filters to the
keywords as NL with no guarantee. Today (`query_rendering.py:92-109`,
`connectors.yaml`) we still:

- mix salary text (`", offering X or more"`) into the keywords — noise for the
  semantic engine and not a reliable LinkedIn filter;
- drop `spec.exclude` entirely (NL is the only exclusion channel left);
- omit any seniority signal even though #32 gives the profile a real one;
- ship `autoConvertToAiSearch: true`, which appends removed filters as NL on
  top of a brief we can now compose deliberately;
- leave `limitPerSource` mapped bare from `results_wanted` with no billed-results
  cap; location is free typeahead text (geoId only as a manual option).

This issue makes the keywords a deliberate semantic brief sourced from the
parsed profile, gives exclusions their only remaining channel, bounds actor
billing, and documents the geoId façade — all inside the `JobSource` connector
interface, with zero new required UI fields.

## Locked decisions

| Decision | Choice | Rationale |
|---|---|---|
| NL brief grammar | `"{title} with {skills joined ' and '}, {seniority} level"` — title and skills from the spec (rendering stays a pure spec+request mapping; the LLM already saw the grounded profile in #31, so spec content *is* parsed-profile content), seniority from the profile's `preferences.seniority` (#32, incl. derived fallback). No-title specs keep today's fallback chain (user query → `spec.query`) unchanged | The composition files stay mechanical; profile values reach rendering through the same `resolve_profile_defaults` path established in #31 rather than re-reading profiles in the rendering layer. The plan's "2–4 strongest skills" becomes "up to 3" because `SourceQuerySpec.skills` is capped at 3 by validation — no spec schema change just for count |
| Seniority transport | `JobSearchRequest` gains `seniority: str \| None = None` (bounded str, same constrained values as `preferences.seniority`); `resolve_profile_defaults` fills it from `structured.preferences.seniority` when None (request value wins, mirroring every other profile-resolved default). `_render_linkedin_plan` passes `request.seniority` into the brief; unset → the phrase is omitted entirely | Same override philosophy as #31 — the client *may* set it, the backend fills defaults from the profile, and pydantic validates either way. No new source-spec field, no stored-spec churn, no prompt change, so `PROMPT_VERSION` stays put and no hash-driven regeneration fires |
| Salary text removal | The `, offering X or more` suffix is deleted from `_natural_keywords` (salary band continues to flow to sources that actually filter on it, e.g. Adzuna in #34) | Plan-of-record wording: "drop salary text from keywords entirely — salary in NL queries adds noise; it isn't a reliable LinkedIn filter either" |
| NL exclusions | `spec.exclude` (≤ 3, existing validation) is appended to the rendered keywords as ` not {' and '.join(exclude)}` — appended **after** the brief is composed, in both the synthesized-brief and user-override cases (override keywords + ` not …`) | NL is the only exclusion channel post-Aug-2026; dropping exclusions silently loses the user's signal. Appending in the override case too keeps one rule and stays testable; wording kept short so the AI search doesn't over-negate |
| `autoConvertToAiSearch` | `connectors.yaml`: `true` → `false` | We now compose the NL brief ourselves; the actor's append-a-removed-filters behavior duplicates and unpurposes it (plan evidence: "merely appends old filters as NL with no guarantee") |
| `limitPerSource` cap | Keep the existing `{results_wanted}` mapping; add `Settings.max_apify_results_per_run: int = Field(default=250, ge=1 le=1000)` and clamp in `config.py`'s `results_wanted` token resolution: `min(query.results_wanted, setting)`. `.env.example` documents it (actor bills per result) | Today's `results_wanted ≤ 100` cap makes 250 a safety guard, not a live clamp — exactly the issue's "set it and cap ~250 to bound cost". Enforced at the one place every actor input is built, connector-agnostic |
| geoId | No behavior change in this issue: the optional `geo_id` filter stays the deterministic override; the default remains free-text location already profile-resolved (`preferences.target_location`) by #31. The location-lookup-actor + cached-`geoId` variant is explicitly deferred | Plan item 4 scopes the cheap v1 to text-as-is; building the lookup actor call + DB cache is a separate, cost-bearing step nobody has asked for yet (`splitByLocation` likewise deferred, per plan item 5) |
| `supports_exclusions` | `ApifyActorSource.supports_exclusions` flips to `True` — NL exclusion now genuinely supported by the source | The flag exists to state what the source honors; the NL channel makes the claim true. No UI contract hangs off LinkedIn `-exclusions` today, so no frontend churn |
| TermPlan docstring / precedence tables | `TermPlan` (base.py) and the `_render_linkedin_plan` comment updated: keywords = composed NL brief (title + skills + seniority) or user-typed override; exclusions appended to both; no salary text | Precedence stays locked in the rendering layer (#33's contract); the connector (`apify.py`) keeps zero decision-making — only its `_require_terms` docstring references the moved rules |

## Scope

### Migration

None. No model changes: seniority is a new optional field on the
`JobSearchRequest` schema (application-level validation only, no DB column), and
nothing else operates on stored rows.

### Backend (`backend/app/`)

- `schemas/job_search.py`:
  - `JobSearchRequest.seniority: str | None = Field(default=None, max_length=50)` (docstring: profile-resolved by default; values mirror `preferences.seniority`'s allowed set — reuse that validator/enum).
- `services/ingestion.py`:
  - `resolve_profile_defaults`: fill `seniority ← structured.preferences.seniority` when the payload omits it (guard `preferences is not None` and `preferences.seniority` non-empty, same shape as the salary block).
- `services/query_rendering.py`:
  - `_natural_keywords` rewritten per the locked grammar: title → `" with …"` skills → `", {seniority} level"`; salary suffix deleted; returns `None` when there is no title (transparent to `_render_linkedin_plan`).
  - `_render_linkedin_plan`: pass `request.seniority` in; append the ` not …` clause to whichever keywords won (synthesized or override).
  - Precedence comment/docstring rewritten to the locked table (and the "composition is reworked in the LinkedIn-dialect issue" note retired — this is that issue).
- `adapters/job_sources/base.py`:
  - `TermPlan` docstring precedence bullet for linkedin updated (NL brief grammar, exclusion clause, no salary text).
  - `date_posted_bucket` / everything else untouched.
- `adapters/job_sources/apify.py`:
  - `supports_exclusions = True`.
  - `_require_terms` docstring precedence note refreshed (no logic change).
- `adapters/job_sources/config.py`:
  - `results_wanted` token case clamps via `get_settings().max_apify_results_per_run` (`config.py` already imports app config indirectly via base — keep it through `get_settings()` like `apify.py` does; no engine/session logic here).
- `adapters/job_sources/connectors.yaml`:
  - `autoConvertToAiSearch: false`; `geo_id` filter help_text gains "preferred deterministic form; location text is the fallback".
- `core/config.py`: `max_apify_results_per_run: int = Field(default=250, ge=1, le=1000)` with a one-line comment (actor bills per result).
- `.env.example`: document the setting.

### Frontend

- Regenerate `lib/api/schema.d.ts` (`JobSearchRequest` gains optional `seniority`; no UI field is added — the profile review UI remains where seniority is corrected).
- Search form: no change required (seniority stays optional/hidden). Verify the form still serializes without it.

### Tests (`backend/tests/`)

- `test_query_rendering.py`:
  - NL brief composition: title + 2 skills → `"Backend Engineer with Python and Rust, Senior level"` (seniority present).
  - No seniority on the request → level phrase omitted (title + skills only).
  - Salary no longer appears in keywords with `salary_min`/`salary_currency` set (replace the existing suffix assertion; un-pin the old contract).
  - Exclusions: synthesized brief + `spec.exclude` → ` not X and Y` appended; user-typed query override also gets the appended clause; empty exclude → no clause.
  - No-title spec: user query → keywords, else `spec.query`; unchanged precedence (regression).
- `test_config.py` (actor-input building): `limitPerSource` equals `results_wanted` (≤100) and the clamped setting value when `max_apify_results_per_run` is monkeypatched below the request.
- `test_apify_adapter.py`: `supports_exclusions` is `True`; composed brief passes through `build_actor_input` to the `keywords` input key; `autoConvertToAiSearch` absent (it is YAML-authored, covered by config validation, not actor tests — assert input shape as today).
- `test_ingestion.py`: `resolve_profile_defaults` fills `seniority` from `preferences`; explicit payload value wins.
- `test_job_endpoints.py`: `seniority` accepted (and ignored when absent) end-to-end.

### Gates

- Backend: `ruff check . && ruff format --check . && pytest` green (in `backend/`).
- Frontend: `npm run lint && npm run build` green (in `frontend/`) — type regen only.
- `.env.example` updated (`max_apify_results_per_run`).
- Docs: `docs/guide/03-job-discovery-and-matching.md` (LinkedIn keywords become a semantic NL brief: seniority included from the profile, salary text dropped, exclusions honored in the NL string, billed-results cap), `docs/architecture.md` (LinkedIn dialect note in the source-connector flow); re-run `node scripts/render-diagrams.mjs` only if a diagram actually changes.

## Risks

| Risk | Mitigation |
|---|---|
| `autoConvertToAiSearch: false` changes result mix | Intended and evidence-backed: the flag appended legacy filters as NL after the Aug-2026 migration; our own brief is the deliberate replacement. Covered by an input-building test pinning the new shape |
| NL exclusions (` not …`) can over-negate if the LLM emits long exclusion lists | Existing spec validation caps `exclude` at 3 short terms; wording is a single fixed clause; behavior pinned by rendering tests |
| New `seniority` request field is client-settable | Same contract as every #31-resolved default: pydantic-validated, request value wins, the profile review UI is the correction surface the plan names |
| `limitPerSource` clamp touches every Apify actor generically | The clamp is per-run upper bound on billed results, which is correct actor-agnostically; default 250 sits above the schema cap so current behavior is byte-identical until a user raises the limit |
| Removing salary text visibly changes stored LinkedIn results | That is the point (semantic noise removal); no schema or stored-spec change means rollback is a one-line rendering revert |

## Out of scope (this issue)

- Location-lookup actor call + `geoId` cache in the DB (plan item 4's "later")
- `splitByLocation` (plan item 5 — deferred, multiplies billed results)
- The cookie-based `linkedin-jobs-search-scraper` alternative connector (plan item 6)
- Run-concurrency guard (Problem 6), scoring changes (Problems 7–9), feedback loop (Problem 10)
