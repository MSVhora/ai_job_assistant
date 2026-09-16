# Issue #31 — Ground query generation in the full profile + content-hash cache (M1)

**Status:** Planned (owner decisions locked 2026-09-16 — see table)
**Tracks:** GitHub issue #31 (milestone `v4`, Phase A)
**Plan of record:** [v4-search-relevance-plan.md](v4-search-relevance-plan.md) Problem 1
**Depends on:** #30 (merged — single-source `JobSearchRequest`, wizard prefills shared fields from the profile)
**Blocks:** #32 (Adzuna dialect) and #33 (LinkedIn dialect) consume the enriched spec outputs; nothing blocks this issue

---

## Goal

Query specs are generated from a thin slice of the profile — `_candidate_context`
(`services/query_builder.py:86-98`) sends only `target_title`, `headline`, the
first 12 skills, and `seniority` to the LLM — and search execution
(`services/ingestion.py:100-136`) never reads the profile at all, so shared
filters (country, location, salary, currency) come only from the request payload.
Meanwhile every path that generates specs pays for a fresh LLM call even when the
profile hasn't changed since the last generation (e.g. re-extraction of the same
resume content, or repeated saves that don't touch query-relevant fields).

This issue:

1. Expands the generation context to the full profile (skills, preferences,
   country, summary) so the LLM writes better specs.
2. Adds a content-hash cache (`profile.queries_input_hash`, new column + Alembic
   migration) so generation fires only when the prompt-consumed inputs actually
   changed; profile edits trigger regeneration as a background task, not in the
   request path.
3. Makes `run_search()` resolve request defaults from the profile (request
   values always win), so a stale or minimal client still gets profile-grounded
   filters.

## Locked decisions

| Decision | Choice | Rationale |
|---|---|---|
| Regeneration on profile edit | **Background on save.** `save_profile()` schedules regeneration via `BackgroundTasks` when the stored hash no longer matches the recomputed one; the save response returns immediately with the (possibly stale) queries. On LLM failure the old queries and old hash stay, an error is logged | Owner decision 2026-09-16. A synchronous LLM call inside PATCH would add seconds to every profile save and violate "no blocking long-running work in request paths". Extraction already tolerates query-generation failure without failing the main operation — same contract here |
| Regeneration on chat (gap-fill) | **Background on turn completion.** `run_gap_fill_turn()` bypasses `save_profile` (it writes `structured_profile` directly, `gap_fill.py:305`), so it gets its own hook: when a turn both applied fields and returned `status == "complete"` (`missing_fields()` empty — the chat's built-in end signal), schedule `ensure_queries_fresh` via `BackgroundTasks`. No debounce needed: mid-conversation turns (`in_progress`) never trigger, and the hash check makes repeated identical completions free | Owner decision 2026-09-16 (follow-up). One regeneration per conversation instead of per turn answers; the `status == "complete"` flag is deterministic server-side state, so no client lifecycle event or timer heuristics are involved |
| Chat visibility | **Hide the gap-fill chat entirely** when the profile has no missing fields. `ProfileResponse` gains `missing_fields: list[str]` (field keys only, computed server-side by `gap_fill.missing_fields()` at response time); `GapFillChat`/`ProfileEditor` render the section only when that list is non-empty. No "start a turn just to hear nothing is missing" flow | The backend already owns the missing-fields definition (`services/gap_fill.py:123`); exposing it removes a wasted LLM-shaped probe turn and dead UI. Keys-only avoids a circular schema import (`GapFillResponse` imports `StructuredProfile` from the same module); labels arrive via the existing turn response badges |
| Request defaults | **Make `location`, `country`, `salary_min`, `salary_max`, `salary_currency` optional** in `JobSearchRequest`; `run_search()` resolves each omitted field from the profile before building connector queries. Explicit request values always win. Neither side provides a country → 400 `MissingSearchCountryError` | Owner decision 2026-09-16, faithful to issue scope. The wizard (#30) already prefills these, so the UI is unchanged; the schema relaxation makes the backend honor its own "profile-grounded" contract instead of trusting the client to echo profile data back. `results_wanted`/`max_days_old` keep their existing defaults (no profile counterpart) |
| Regenerate endpoint semantics | The manual regenerate endpoint **always forces a new generation** (ignores the hash) and overwrites the stored hash afterwards. It remains the "fresh variant" path: `previous` block + temperature 0.8 | v4 plan Problem 1.3 + 1.5: manual regenerate is the alternatives-freshness affordance; one-shot variance is acceptable only where the user explicitly asked for a change |
| Default-spec temperature | Generation **without** `previous` (extraction path, background-on-save) runs at temperature **0**; generation **with** `previous` (manual regenerate) keeps 0.8 | v4 plan Problem 1.5: persisted defaults must be reproducible; the previous-block variant prompt is the only place variance is wanted |
| Hash constant | Reuse the existing `PROMPT_VERSION` ("search_query_v2", stamped into `StoredSearchQueries.prompt_version`) as the query-builder version input — **no second `QUERY_BUILDER_VERSION` constant**; bump it to `search_query_v3` in this change | The issue text says "a `QUERY_BUILDER_VERSION` constant", but `PROMPT_VERSION` already plays exactly that role and is persisted with every generation — a second constant could drift out of sync. This is a deliberate minor deviation from the issue wording |
| Hash inputs | SHA-256 over: canonical JSON of `StructuredProfile` (model_dump, sort_keys) + sorted enabled source names + JSON-serialized filter declarations + `PROMPT_VERSION` | "Exactly the inputs the prompt consumes": profile content, which sources need specs, which options the prompt advertises, and the prompt itself. Enabling/disabling a source or changing connectors.yaml invalidates correctly. Source names are derived in-service, requiring no schema changes |
| Resume draft stage | No hash checks at extraction — a new resume upload always generates fresh draft queries (there is no prior hash to compare). The hash is computed and stored when a **profile** is created from the draft (`create_profile`) or regenerated | The hash is per-profile; extraction writes to `resume.search_queries` before any profile exists. Re-upload flows reach the profile via `save_profile(source_resume_id=...)`, where the hash check applies |
| Where defaults resolve | In `start_search()` after the profile is loaded; the **resolved** payload is what gets echoed into `run.query` and passed to the background `run_search` | The profile is already fetched by `_require_profile`; resolving up front means the status endpoint's `query` echo shows what actually ran, and `run_search` needs no new profile lookup |
| Remote handling | `remote_preference` enters the generation context (so specs reflect it), but **no run-time remote filter resolution** in this issue | No connector accepts a remote parameter (Adzuna has none; LinkedIn's classic workplace filter is gone post-AI-search). Remote-as-NL is Problem 5/#33 territory |
| `profile_embed_text` untouched | Sharing happens by extracting a `profile_digest_parts()` helper; the embedding text its output joins remains byte-identical | Changing the profile-digest text would silently change embedding inputs → stale vectors vs 768-dim retraining semantics. Embedding stability wins |
| Frontend | Type regeneration only (`npm run generate:api` after the schema change); no UI or behavior change | The wizard already prefills and sends all optional fields; `country` stays non-empty in practice. `queries_input_hash` is internal — not exposed in `ProfileResponse` |

## Scope

### Migration

- `backend/alembic/versions/0015_add_profile_queries_input_hash.py`:
  adds nullable `queries_input_hash VARCHAR(64)` to `profile`; downgrade drops
  it. No data migration (profiles without a hash treat it as "stale" — the
  next save schedules regeneration). Models change first (`models/profile.py`).

### Backend (`backend/app/`)

- `services/query_builder.py`:
  - `_candidate_context()`: expand with full skills, `preferences` (target
    title/location, seniority, remote preference, salary band, currency),
    `contact.country`, headline, truncated summary (cap chars — reuse the
    digest-cap pattern, not `MAX_EMBED_CHARS` blindly). Keep the "never include
    location or salary in title/skills/exclude" instruction.
  - Reuse the digest helpers from `services/embedding.py`:
    extract `profile_digest_parts(profile) -> list[str]` there (moved out of
    `profile_embed_text` unchanged in content) and consume it from both
    `profile_embed_text` and `_candidate_context`.
  - `compute_queries_input_hash(structured_profile_dump, source_names,
    declarations) -> str` — canonical-JSON SHA-256 per the locked hash inputs.
  - `generate_queries(..., temperature: float)`: parameterized; default 0.0.
    Callers with `previous` pass 0.8.
  - `regenerate_for_profile()`: unchanged contract (always forces), plus reads
    the profile row to overwrite `profile.queries_input_hash` after a
    successful generation.
  - New `ensure_queries_fresh(session, profile_id) -> bool`: compute the hash;
    if it matches the stored one → no-op, return False; else regenerate for all
    enabled sources, persist, store the new hash, return True. Swallows
    `LLMQueryGenerationError` (log warning, keep old state) — same
    never-fails-the-caller contract as `_generate_draft_queries`.
- `services/profile_service.py`:
  - `create_profile()`: after copying draft queries, compute + store
    `queries_input_hash` from `payload.structured_profile`.
  - `save_profile()`: when `structured_profile` changed, after the sync work
    (embedding refresh, rescore) compute the new hash; if it differs from the
    stored one, schedule `ensure_queries_fresh` via `BackgroundTasks`.
  - Needs a router-level `BackgroundTasks` dependency passthrough
    (`routers/profile.py` update endpoint).
- `services/gap_fill.py`:
  - `run_gap_fill_turn()`: when `applied` is non-empty **and** the response
    status is `"complete"`, schedule `ensure_queries_fresh` via
    `BackgroundTasks` (needs the same `BackgroundTasks` passthrough in
    `routers/profile.py`). In-progress turns schedule nothing.
- `services/ingestion.py`:
  - `start_search()`: after `_require_profile`, resolve defaults from
    `StructuredProfile.model_validate(profile.structured_profile)`:
    `country ← contact.country`, `location ← preferences.target_location`,
    `salary_min`/`salary_max`/`salary_currency` ← `preferences` — only fields
    the request left `None`. Persist the resolved payload as `run.query` echo
    and pass it to the background task.
  - Neither request nor profile has `country` → raise the new domain error.
- `schemas/job_search.py`:
  - `JobSearchRequest`: `location`, `country`, `salary_min`, `salary_max`,
    `salary_currency` become optional (`country: str | None` with the existing
    2-letter validator applied only when present). `_salary_range` validator
    tolerates half-bounds.
- `schemas/profile.py`:
  - `ProfileResponse`: new `missing_fields: list[str] = []` — keys from
    `gap_fill.missing_fields()` evaluated on the stored structured profile (no
    schema/migration change; pure response enrichment in
    `_profile_response`). Note the import direction: `schemas/gap_fill.py`
    imports from `schemas/profile.py`, so the field stays key-only to
    avoid a cycle.
- `core/errors.py`: new `MissingSearchCountryError` (status 400) — no country
  from either request or profile.
- `models/profile.py`: `queries_input_hash: Mapped[str | None]`.

### Frontend

- `ProfileEditor.tsx` / `GapFillChat.tsx`: render the gap-fill section only
  when the profile's `missing_fields` is non-empty. `applyGapFill()` keeps the
  local view in sync with each turn's `missing_fields` so the section collapses
  immediately on completion (not only after the next refetch); the
  "Start conversation" flow disappears entirely for complete profiles. No new
  components; no new fetch (the list rides on the existing profile response).
- Type regeneration only (`npm run generate:api` after the schema changes);
  no other UI or behavior change. The wizard (#30) already prefills and sends
  all optional fields; `country` stays non-empty in practice.
  `queries_input_hash` is internal — not exposed in `ProfileResponse`.

### Tests

Backend (`backend/tests/`):

- `test_query_builder.py`:
  - `compute_queries_input_hash`: deterministic for identical inputs;
    sensitive to profile content, source set, declarations, and
    `PROMPT_VERSION`.
  - `ensure_queries_fresh`: cache hit (hash match → no LLM call, specs kept,
    returns False) / miss (differs → generation, hash persisted, True);
    LLM failure → old queries + old hash kept.
  - `regenerate_for_profile` overwrites the hash; temperature 0.8 when
    `previous` is passed, 0.0 otherwise (assert on the fake `parse_structured`
    call kwargs).
  - `_candidate_context` includes the new fields (fake capture of the prompt).
- `test_profile_endpoints.py`:
  - `ProfileResponse.missing_fields` reflects the stored structured profile on
    get/create/save (empty for a complete profile).
  - `create_profile` persists `queries_input_hash` derived from the final
    structured profile (even when it diverged from the draft).
  - Save with changed `structured_profile` → background regeneration invoked
    (fake captures the scheduled task); save that only renames → no
    regeneration; save with unchanged content → no LLM call.
- `test_gap_fill.py`:
  - A turn that applies fields and completes → `ensure_queries_fresh`
    scheduled; an `in_progress` turn or a complete turn that applied nothing →
    nothing scheduled; a "complete" turn with unchanged hash → no LLM call.
- `test_profile_extraction.py`: default-path generation uses temperature 0;
  existing flow assertions keep passing.
- `test_ingestion.py` / `test_job_endpoints.py`:
  - Defaults resolved: request omits location/salary and sends minimal country
    fields → connector query carries profile values; explicit request values
    win per field.
  - `run.query` echo contains the resolved payload.
  - No country anywhere → 400 `MissingSearchCountryError`.
- Frontend (vitest):
  - `GapFillChat` (or `ProfileEditor`) hidden when `missing_fields` is empty;
    shown when non-empty; collapses after a turn whose `missing_fields` is
    empty; manual-save refetch path keeps it hidden.
- `test_migrations.py`: 0015 up/down.

### Gates

- Backend: `ruff check . && ruff format --check . && pytest` green (in
  `backend/`).
- Frontend: `npm run lint && npm run build` + `npm run generate:api` (types
  regenerated, never hand-edited).
- Migration ships in the same change as the model change; reviewed autogen
  output (column add only — trivial, but verify no spurious diff).
- Docs: `docs/guide/02-upload-and-profile.md` (queries regenerate
  automatically after profile edits; temperature/regenerate semantics),
  `docs/guide/03-job-discovery-and-matching.md` (backend resolves omitted
  search fields from the profile), `docs/architecture.md` query-generation
  flow. Re-run `node scripts/render-diagrams.mjs` if diagrams change.
- `.env.example`: unchanged (no new Settings; `PROMPT_VERSION` is a constant).

## Risks

| Risk | Mitigation |
|---|---|
| Background regeneration races a concurrent search that renders stale specs | Regeneration is per-profile idempotent; a search started mid-regeneration uses the last persisted specs — the same behavior the UI has today between edit and regenerate. Benign for a single-user app |
| Expanded context makes the LLM produce worse specs (more tokens, more drift) | Temperature 0 for default specs; skills/summary char-capped; `parse_structured`'s existing validate + one repair retry still guards malformed output; `test_query_builder` pins the prompt shape |
| Relaxing `country` weakens validation | `MissingSearchCountryError` keeps a hard 400 when neither side supplies one; optimistic relaxation only where the profile can actually backfill. Frontend sends country regardless (regenerated types make the optionality explicit but behavior is unchanged) |
| Hash over full structured_profile regenerates on cosmetically irrelevant edits (e.g. extra_sections tweak) | Accepted v1 trade-off — the hash must cover exactly what the prompt consumes, and summary/skills/experience all qualify. Bounding regeneration frequency (e.g. debounce) is deferred unless real cost shows up |
| Draft-vs-profile divergence: draft queries generated at extraction don't reflect post-review edits | Same as today; the user can regenerate manually, and the first profile *save* now self-heals via the hash check — strictly better than status quo |

## Out of scope (this issue)

- Pre-search generation checks (v4 plan Problem 1.2's "pre-search check" path) —
  no auto-generation at search start; extraction + save-time + manual cover the
  trigger points.
- Adzuna dialect work (`what_and`, `title_only` parallel pass,
  `salary_include_unknown`) — Problem 3 / #32.
- LinkedIn NL-brief composition, exclusions-in-NL, `limitPerSource`, geoId —
  Problem 5 / #33.
- Run-time remote-preference → connector filter mapping (no connector supports
  it; handled via generation context only).
- Exposing `queries_input_hash` or a "queries stale" flag in `ProfileResponse`.
- Years-of-experience parsing / seniority derivation — Problem 2 (#39?).
- Any change to `StoredSearchQueries` shape or router response models.
