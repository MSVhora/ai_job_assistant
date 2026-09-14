# Issue #28 — Source filter capabilities: declarations, validation, connector mapping (M3)

**Status:** Planned
**Tracks:** GitHub issue #28 (milestone `v3`, M3 advanced filters — backend part)
**Plan of record:** [v3-implementation-plan.md](v3-implementation-plan.md) §2 D5, D6; §3 (capability tables); §4 M3
**Depends on:** #27 (merged — `max_days_old`, `date_posted_bucket` seam, `{date_posted_bucket}` placeholder all exist and are designed to be absorbed by this issue)
**Blocks:** #29 (capability-driven search UI consumes `/api/sources` `filters` and the `options` dict)

---

## Goal

Every source declares the filters it supports; the backend validates per-source
`options` against the declaring source's declaration; connectors map validated
options to their native params. New sources then need only a declaration +
mapper (config + mapper rule, non-negotiable #3) — zero search-logic changes —
and #29's UI renders the declarations generically instead of hand-written
per-source form fields.

The frontend code side is out of scope here except the regenerated OpenAPI
types; the generic form is #29.

## Locked decisions

| Decision | Choice | Rationale |
|---|---|---|
| Declaration model | `SourceFilterDecl` pydantic model in `app/adapters/job_sources/base.py`: `{key, label, type: text\|number\|select\|multiselect\|boolean, options: list[{value,label}] \| None, required, placeholder, help_text}`; `options` required (non-empty) for `select` | One model both for validation and for the `/api/sources` response, so validation and UI can never drift |
| Protocol change | `JobSource` gains `filters() -> list[SourceFilterDecl]` as a **method** returning a list (may be empty) | Method over attribute so YAML-configured sources can pull from config; an empty list is a valid "no advanced filters" declaration — graceful degradation per D4/D5 style |
| Adzuna code declarations | Class constant `_FILTERS` in `adzuna.py` declaring `title_only` (boolean), `distance_km` (number), `sort_by` (select: relevance/date/salary) | Adzuna is a code connector; declarations live next to the mapping (v3 plan §8 risk-mitigation: declarations asserted in tests with fixture payloads) |
| ⚠ `salary_max` NOT redeclared | The issue body lists `salary_max` (number) as a new Adzuna option — **stale**: the shared `JobSearchRequest.salary_max` already exists and `_apply_salary_filter` (adzuna.py:72) already sends the native param. Declaring it again as an option would create two sources of truth for one param | Deviation from the issue body, flagged for owner sign-off instead of silent drift (AGENTS rule). If the owner prefers option-form instead, the follow-up is removing the shared field — more churn, no gain |
| LinkedIn YAML declarations | `connectors.yaml` sources gain a `filters:` list key; `ActorConfig` gains `filters: list[SourceFilterDecl] = []`; `ApifyActorSource.filters()` returns the config declaration | Keeps the config-only-addition rule: a future YAML source that declares filters gets validation + params for free |
| Declared filter set (per v3 plan §3, re-verified) | LinkedIn: `date_posted` (select: anyTime/past24h/pastWeek/pastMonth), `distance_miles` (number), `under_10_applicants` (boolean), `company_ids` (multiselect-text), `geo_id` (text). Adzuna: `title_only`, `distance_km`, `sort_by` (see ⚠ above for salary) | Capability tables §3; `multiselect-text` = free-text entries (no fixed enum — LinkedIn company IDs), hence `options: None` |
| Option value type | `SourceQuerySpec.options: dict[str, str \| int \| bool \| list[str]] = {}` capped at 12 keys (mirrors `_MAX_SKILLS`-style caps); same dict on `JobSearchQuery` | D6: one schema for AI-generated and user-edited filters. `list[str]` only for multiselect |
| Validation | New `validate_source_options(decls, options, source_name)` in `app/adapters/job_sources/base.py`, raising `InvalidSourceFilterError` (new `DomainError`, 400): unknown key, wrong type (numbers must be `type(v) is int` — bool is not a number; booleans must be real bools; select values must be declared ones), bad enum value, over-cap — error detail always names the offending key | D5 "backend validates per source"; message naming the key is the contract the tests assert and the UI surfaces |
| Validation point | `ingestion._validate_queries` (it already receives the `selected` sources) — runs in both the request path and the background re-validation | Exists already for source-name checks; one more loop there keeps validation in exactly one service |
| Options-only spec | `SourceQuerySpec.has_content()` extended: a spec with any option key set counts as content | Advanced filters without text (e.g. LinkedIn `geo_id` + `under_10_applicants`) are legitimate searches; without this the request dies on `MissingSearchQueryError` |
| `date_posted` merge | The existing `{date_posted_bucket}` resolver case merges: `query.options["date_posted"]` overrides when present, else falls back to `date_posted_bucket(query.max_days_old)` (#27 mapping). YAML unchanged (`datePosted: "{date_posted_bucket}"`) | #27's seam was chosen so capability work could absorb it; explicit user choice wins over the derived bucket because it is more specific; quantization stays documented in #27 |
| YAML option placeholders | `_PLACEHOLDER_KEYS` extended with `option:<key>` placeholders (`{option:date_posted}` form not needed — `date_posted` rides the merge above). `{option:distance_miles}`, `{option:under_10_applicants}`, `{option:company_ids}`, `{option:geo_id}` resolve from `query.options`, keeping native types (int stays int, bool stays bool, list stays list), `_OMIT` when the key is absent | The #27 pattern (config-driven input, resolver + `_PLACEHOLDER_KEYS`) survives; no bespoke overrides in `ApifyActorSource`; unknown `{option:...}` placeholders are rejected by the existing `_validate_placeholders` |
| Adzuna native mapping | New `_apply_options(params, query)` in `adzuna.py`: `title_only` → `params["title_only"] = "true"` only when truthy; `distance_km` → `params["distance"]` only when `query.location` is set (Adzuna requires `where` for radius) — silently skipped otherwise; `sort_by` → `params["sort_by"]` | Params dict is `str`-valued today (adzuna.py:102); bools/lists don't fit, so Adzuna maps in code while the Apify path keeps native types via YAML. Skipping `distance_km` without `location` mirrors D4 "degrade gracefully"; `help_text` on the declaration tells the UI |
| `query_rendering` seam | `build_connector_query` passes `spec.options or {}` into `JobSearchQuery` kwargs; no per-source logic added | Single render seam preserved (v3 plan §4 M3 + D5) |
| LLM generation | `query_builder.py` prompt lists each source's declared option fields and permitted select values; after parsing, option keys not in the source's declaration are **silently dropped** (not a 400 — regeneration must not fail on LLM invention). `PROMPT_VERSION = "search_query_v2"`; stored v1 specs still validate (options default empty, no migration needed) | D6: "LLM may fill only declared option fields, never invents undeclared keys" enforced mechanically, not just by prompt. v2 stamp marks which stored specs were generated with declaration awareness |
| Strict vs lenient | User/API-submitted options: strict (400). LLM-generated: lenient (strip). Stored-spec echo: unparsed (returned as stored) | Same schema, different trust levels — consistent with "never trust the client" |
| `/api/sources` response | `SourceInfoResponse.filters: list[SourceFilterDecl] = []`; `supports_exclusions` kept for back-compat (removed in #29 when the UI stops reading it) | D5; back-compat per v3 plan §4 M3 |
| No migration | None — `options` lives in request bodies, the `job_search.query` JSONB echo (whole-request dump, automatic), and `profile.search_queries` JSONB (versioned by `prompt_version`) | `max_days_old` set the precedent in #27 |

## Scope

### Backend — declarations & validation

- `app/adapters/job_sources/base.py`:
  - `SourceFilterOption` and `SourceFilterDecl` models (types above; `key`
    pattern `^[a-z][a-z0-9_]+$`, string fields length-capped).
  - `JobSearchQuery.options: dict[str, str | int | bool | list[str]] = Field(default_factory=dict)`.
  - `validate_source_options(decls, options, source_name) -> None` per the
    validation decision (per-type checks, `type(v) is bool` guards, enum
    membership, key cap; errors name the offending key).
- `app/core/errors.py`: `InvalidSourceFilterError(DomainError)` — 400.
- `app/schemas/job_search.py`:
  - `SourceQuerySpec.options: dict[str, str | int | bool | list[str]] = Field(default_factory=dict, max_length=12)`;
    `has_content()` also true when any option key is set.
  - `SourceInfoResponse.filters: list[SourceFilterDecl] = []`.

### Backend — declarations on sources

- `app/adapters/job_sources/adzuna.py`: `_FILTERS` constant; `filters()` method.
- `app/adapters/job_sources/config.py`:
  - `ActorConfig.filters: list[SourceFilterDecl] = []`.
  - `_resolve_value` case `option:<key>` → `_OMIT` when absent else the native value;
    `_PLACEHOLDER_KEYS` validation extended accordingly.
  - the `date_posted_bucket` case gains the `date_posted` option override (merge point).
- `app/adapters/job_sources/connectors.yaml`: `filters` list for
  `apify_linkedin`; input gains the four `option:` placeholders (native field
  names `distance`, `under10Applicants`, `companyIds`, `geoId`).
- `app/adapters/job_sources/apify.py`: `filters()` returns `self._config.filters`.
- No protocol change beyond `filters()`; connectors without options keep working
  (YAML sources may declare no filters).

### Backend — plumbing

- `app/services/ingestion.py`: `_validate_queries` also calls
  `validate_source_options(source.filters(), spec.options, source.name)` for each
  selected source's spec (covers both request-time and background re-validation
  since the run path re-invokes it).
- `app/services/query_rendering.py`: pass `spec.options` into `JobSearchQuery`
  kwargs (like the salary fields — set for every source, consumed only by
  declarers).
- `app/adapters/job_sources/adzuna.py`: `_apply_options` per the mapping above,
  invoked from `search()`.
- `app/services/sources.py`: `_source_info` populates `filters=source.filters()`.
- `app/services/query_builder.py`:
  - Prompt lists declared options per requested source (name + type + allowed
    values) with "options are optional; only use declared keys".
  - Post-parse: for each source, drop undeclared option keys before storing.
  - `PROMPT_VERSION = "search_query_v2"`; `generate_queries` signature gains the
    per-source declaration map (built by `regenerate_for_profile` from
    `enabled_sources`).

### Backend — tests

- `validate_source_options`: unknown key → 400 error naming the key; string for
  `number`; `True` passed for `number` rejected (bool guard); int for `boolean`;
  undeclared select value; `list` for `text`; `str` for `multiselect`; >12 keys;
  valid dict passes through unchanged.
- `has_content()`: options-only spec counts as content; empty options do not.
- Adzuna: `title_only: true` → `title_only=true` param; `distance_km` with
  location → `distance` param, without location → omitted; `sort_by=date` →
  param; no options → unchanged params (existing fixtures stay green).
- YAML/Apify: declared filters surface via `ApifyActorSource.filters()` and
  `/api/sources` (with `supports_exclusions` still present); actor input built
  from options preserves native types and omits absent keys; `datePosted`
  override (option present) and fallback (option absent + `max_days_old=7` →
  `pastWeek`); unknown `{option:...}` placeholder → config error.
- `query_builder`: declared options survive generation Echo/fixtures, invented
  keys dropped, `prompt_version: search_query_v2` written.
- Endpoints: search request with bad option → 400 detail naming the key;
  well-formed options appear in the stored `job_search.query` echo.
- Lint gates: `ruff check . && ruff format --check . && pytest` in `backend/`.

### OpenAPI / types

- `frontend/lib/api/schema.d.ts` regenerated (`npm run generate:api`) —
  `SourceInfoResponse.filters`, `SourceQuerySpec.options`. No other frontend
  change (form work is #29).

## Definition of done

- `ruff check . && ruff format --check . && pytest` green in `backend/`.
- `npm run lint && npm run build` green in `frontend/` (types-only change).
- `npm run generate:api` run — types include `filters` and `options`.
- Live check (wire verification, both sources): a search with Adzuna
  `title_only=true, distance_km=25, sort_by=date` produces the corresponding
  query params in the outgoing Adzuna request; a search with LinkedIn
  `date_posted=pastWeek, under_10_applicants=true` produces `datePosted:
  pastWeek, under10Applicants: true` in the actor input; an undeclared or
  badly-typed option is rejected with a 400 naming the key.
- Docs: `docs/guide/03-job-discovery-and-matching.md` — per-source filter tables
  become the living filter reference (replacing the stale "salary max new" row);
  `docs/architecture.md` — `/api/sources` API table row gains the `filters`
  field. `node scripts/render-diagrams.mjs`.
- No migration (none needed); `.env.example` unchanged (no new setting).

## Out of scope (this issue)

- Generic `SourceFiltersForm`, `select.tsx`/`checkbox.tsx`/`accordion.tsx`
  primitives, zod client schema, removal of `supports_exclusions` reliance → #29.
- New sources, pagination (`results_wanted` cap stays), experience/job-type/
  workplace filters for LinkedIn (no dedicated actor fields — folded into NL
  keywords, documented in §3).
- Per-source bounds (min/max) on number options — declarations gain bounds only
  when a real filter needs them.
- Re-declaring `salary_max` as an option (⚠ deviation flagged in Locked decisions).
