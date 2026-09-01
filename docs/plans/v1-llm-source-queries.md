# LLM per-source search queries + structured search filters (follow-up to issue #8)

**Status:** Done (2026-09-01)
**GitHub issue:** to be filed by the owner
**Plan of record:** [v1-implementation-plan.md](v1-implementation-plan.md) §6 (API surface), §10 (LLM via wrapper, rate limits)
**Depends on:** Issue #8 (done) — sources, enablement, `/jobs` form. Builds on #3 (extraction), #5 (preferences), #6 (profiles).
**Owner feedback folded in:** generate at extraction; `/jobs` shows persisted queries with **Regenerate**; regeneration must observably change the output; staleness must tell the user to press Regenerate; exclusions only where a source actually supports them; the owner's worked example (senior Android engineer, Bangalore, >50 LPA) must map to *filters first, query second*.

---

## Research findings

**Adzuna** (official docs, verified):
- `what` is fuzzy/OR-ish — long strings flood noise. Prefer structured params:
  `what_phrase` (exact title phrase), `what_or` (space-separated any-of terms),
  `what_exclude` (**exclusions are first-class**), `title_only`, `where` + `distance`,
  **`salary_min`** (native min-salary filter), `max_days_old`, `sort_by`.
- `full_time=1`/`permanent=1` silently discard most postings (ads are usually untagged) —
  never filter on them.

**LinkedIn (via `curious_coder/linkedin-jobs-scraper`, `autoConvertToAiSearch: true`)**:
- LinkedIn is **retiring classic keyword job search (announced for Sept 2026)**; AI-powered
  search is natural-language ("type details you'd normally use as a filter directly into
  your search") and matches intent, not exact keywords.
- Its remaining filter set has **no salary and no exclusion filter**, and the actor's input
  schema has **no salary/exclusion field either** → structured exclusions or salary filters
  are pointless for this source. The supported pattern is putting such details in the
  natural-language query text (e.g. "offering ₹50 LPA or more", "excluding internships" —
  the latter best-effort, not sent by default per the owner's rule).

**Capability table (drives everything below):**

| Capability | Adzuna | apify_linkedin |
|---|---|---|
| Exact title phrase | `what_phrase` | in NL query text |
| Skills (any-of) | `what_or` | in NL query text |
| Exclusions | `what_exclude` ✅ | ❌ not sent (unsupported) |
| Min-salary filter | `salary_min` ✅ | ❌ filter → NL mention only |
| Location | `where` (+`distance`) | actor `location` input |
| Freshness | `max_days_old` (deferred, #9) | `datePosted` (deferred, #9) |

## Goal

Search queries become **profile data**, generated at extraction, persisted, regenerated on
demand. Searches become **filter-first**: location, salary, and per-source title/skills/
exclude are structured fields mapped to each source's native capabilities; the query text
carries only what the source cannot filter. The owner's example — "senior Android engineer
jobs in Bangalore, min salary 50 LPA" — maps to: `where=Bangalore` + `salary_min=5000000`
(Adzuna) and `"Senior Android Engineer role with Kotlin and Java, offering ₹50 LPA or more"`
(LinkedIn NL) — never a chopped token blob.

## Locked decisions (proposed — owner sign-off)

| Decision | Choice | Rationale |
|---|---|---|
| Generation trigger | **Automatic at extraction** — after the draft persists, a second LLM call generates per-source specs from the draft. Extraction never fails because of it (log + continue, queries stay null). Skipped when no source is enabled. Re-running `/extract` regenerates | Owner decision; keeps the extraction schema untouched |
| Persistence | `resume.search_queries` + `profile.search_queries` jsonb (migration `0009`), stamped `{queries, generated_at, generated_by, prompt_version}`. Profile creation from a draft copies the draft's queries | Owner decision; provenance stamps make staleness computable |
| Generation output | One **source-agnostic structured spec per source**: `{title: str (exact title phrase), skills: [≤3 short terms], exclude: [≤2 terms]}`. Same schema for every source; **rendering is per source** | One dialect-neutral LLM call; the per-source dialect lives in deterministic renderers (see next rows) |
| Adzuna rendering | `title`→`what_phrase`, `skills`→`what_or`, `exclude`→`what_exclude`, shared `salary_min`→`salary_min`, `location`→`where`. Plain `query` (fallback/seed) still goes to `what` | Uses the API's precise params per research; live-verify the `what_phrase`+`what_or` composition during implementation, fall back to `what` if the combination misbehaves |
| LinkedIn rendering | `keywords` = deterministic NL build: `"{title} role with {skills joined}"` + salary mention when the min-salary filter is set ("offering ₹50 LPA or more"). `exclude` **dropped** — unsupported (capability table) | Matches LinkedIn's AI-search guidance; no structure it can't consume |
| Exclusions | Generated only for sources that support them (`adzuna`); UI hides the exclude input elsewhere | Owner's rule: no point sending exclusions a source can't use |
| Regeneration variability | Generation runs at **temperature 0.8** (extraction stays 0.2); on regenerate, the previous queries are included in the prompt with the instruction "produce a fresh, equally strong variant — do not repeat the previous text" | Owner's "same input → same output" concern: sampling variation + explicit anti-repeat instruction make Regenerate observably change the query |
| Staleness | `/jobs` compares `profile.updated_at` vs `queries.generated_at` → hint: **"Queries are stale — the profile changed after generation. Press Regenerate."** No auto-regen on save | Owner decision; saves are frequent, auto-calls would spam LLM spend |
| Manual edits | Per-run only; only Regenerate persists. Submitted values are the final queries (echoed by the run status) | Owner decision |
| Shared salary filter | `JobSearchRequest.salary_min: float \| None` (+ nullable `salary_max`) — prefilled on `/jobs` from `preferences.salary_min`; **used as-is** (Adzuna expects local currency per country; a profile currency ≠ country-currency skew is documented as a v1 caveat for the single user) | The owner's 50 LPA example is a *filter*, not query text |
| Request schema | `JobSearchRequest.query` optional; `source_queries: dict[str, SourceQuerySpec]` with `SourceQuerySpec {title?, skills?, exclude?, query?}` (length-capped, keys = known sources → 400); service requires non-empty effective content per selected source (spec title/query) → 400 `MissingSearchQueryError` | Connectors receive `JobSearchQuery` with the new optional fields; plain-string path unchanged for back-compat |
| Fallback | No generated queries → deterministic seed fills Title/Skills fields (current seed logic); search never blocked by the LLM | Graceful degradation |
| LLM access | Only via `adapters/llm.py` `parseStructured` (pydantic `GeneratedQueries`), one repair retry → `LLMQueryGenerationError` 502 | Standards |
| Prompt content | Profile fields only: target title/headline, top skills, seniority, target location (context only — **never rendered into queries**, location is a filter field), min salary (LinkedIn-NL context only). Never raw resume text | Privacy rule |

## Scope

### Backend

**Migration `0009_add_search_queries_columns`** — `resume.search_queries` jsonb nullable,
`profile.search_queries` jsonb nullable; downgrade drops both.

**Models** — `Resume.search_queries`, `Profile.search_queries` (`Mapped[dict | None]`)

**`services/query_builder.py`** — `generate_queries(profile_or_draft, sources, previous=None)`:
- sources default to currently enabled sources (unknown → 400)
- one `parseStructured` call at temperature 0.8 → `GeneratedQueries {queries: dict[str, QuerySpec]}`;
  every requested source present; caps enforced (title ≤80, skills ≤3×40, exclude ≤2×40)
- previous specs included when regenerating (anti-repeat instruction)
- stamps `{queries, generated_at, generated_by: llm_model, prompt_version: "search_query_v1"}`
- failure → one repair retry → `LLMQueryGenerationError`

**Per-source rendering — `services/query_rendering.py`** (pure, fixture-tested): spec +
shared filters → per-source `JobSearchQuery` (Adzuna structured params / LinkedIn NL build /
plain-`query` fallback for any source without a renderer)

**Extraction integration** — `services/profile_extraction.py`: draft persisted → generate
specs → `resume.search_queries`; failure isolates (null + warning log). `DraftProfileResponse`
gains `search_queries`.

**Profile creation** — `services/profile_service.py`: copies the draft's queries into the
new profile.

**Regenerate endpoint** — `routers/profile.py`: `POST /api/profiles/{id}/search-queries`
(`{sources?}` default = enabled sources) → generate from current content, persist, return
`{queries, generated_at, generated_by}`. 404 / 400 / 502 (stale persisted queries untouched
on 502). No revision row.

**Search request** — `schemas/job_search.py`: `query` optional; `source_queries` as
`dict[str, SourceQuerySpec]`; `salary_min`/`salary_max` optional shared filters.
`services/ingestion.py`: effective-content check per selected source; builds each
connector's `JobSearchQuery` via the renderer (shared filters included).

**Adzuna connector** — map `title_phrase`→`what_phrase`, `skills_any`→`what_or`,
`exclude_any`→`what_exclude`, `salary_min`→`salary_min`; keep `what` fallback; live-verify
param composition. **LinkedIn input builder** — build NL `keywords` from the spec (+ salary
mention); `location` input unchanged; salary/exclude have no actor fields.

**Errors** — `LLMQueryGenerationError` (502), `MissingSearchQueryError` (400)

### Frontend — `/jobs`

```
┌────────────────────────────────────────────────────────────────┐
│ Searching as profile  [▾ Senior Android Engineer             ] │
├────────────────────────────────────────────────────────────────┤
│ Search queries                                [ ↻ Regenerate ] │
│ ⚠ Queries are stale — the profile changed after generation.    │
│   Press Regenerate.                                            │
│                                                                │
│ adzuna  [Official API]                                         │
│  Title     [ Senior Android Engineer                        ]  │
│  Skills    [ Kotlin, Java                                   ]  │
│  Exclude   [ intern                                         ]  │  ← shown: source supports exclusions
│                                                                │
│ apify_linkedin  [Third-party scraper]                          │
│  Title     [ Senior Android Engineer                        ]  │
│  Skills    [ Kotlin, Java                                   ]  │
│  (no exclude input — this source does not support it)          │
│                                                                │
│ Generated 12 min ago · gemini-2.5-flash                        │
├────────────────────────────────────────────────────────────────┤
│ Location [ Bangalore ]  Country [ in ]  Min salary [ 5000000 ] │  ← prefilled from preferences
│ Results wanted [ 50 ]   Sources ☑ adzuna ☑ apify_linkedin      │
│ [ Start search ]                                               │
└────────────────────────────────────────────────────────────────┘
```

- States: generated (+provenance caption) / stale (amber hint, nothing auto-overwritten) /
  no-generated-yet (seed fills Title+Skills, hint "Regenerate fills it") / regenerating
  (button spinner, fields editable, success updates fields+caption, 502 → toast, fields
  unchanged) / no profile (manual entry, Regenerate hidden) / profile switch (refill from
  that profile's persisted queries, no LLM call)
- Form: RHF + zod; Title/Skills/Exclude per source via a dynamic record; shared filters
  labeled; Min salary prefilled from `preferences.salary_min`; Exclude input only rendered
  for exclusion-capable sources with a "supported by this source" affordance
- Submit: `source_queries` per source + shared filters; run banner echoes everything
- A11y: labeled fields, `aria-live` on regenerate status, focus rings, badges always visible

### Tests

- `test_query_builder.py` — fake `acompletion`: prompt has profile fields (never resume
  text), temperature 0.8, previous-variant instruction on regenerate; caps; repair retry;
  502/400/404 paths
- `test_query_rendering.py` (new) — spec→Adzuna params (`what_phrase`/`what_or`/
  `what_exclude`/`salary_min`/`where`), spec→LinkedIn NL keywords (+salary mention, exclude
  dropped), plain-`query` fallback
- `test_adzuna_adapter.py` — new params sent; `what` fallback when no title_phrase
- `test_apify_adapter.py` — input builder includes NL keywords + salary mention; no salary/
  exclude actor fields invented
- `test_profile_extraction.py` — draft carries queries; failure isolation; re-extract
  regenerates
- `test_profile_endpoints.py` — copy-on-create; regenerate persists + returns; 404/400;
  502 leaves persisted queries untouched
- `test_ingestion.py` / `test_job_endpoints.py` — per-source specs + salary filter reach
  each fake source; missing effective content → 400; run status echoes the full request

### Doc impact

- Plan-of-record §4 (two jsonb columns), §6 (endpoint rows + salary filter)
- `docs/architecture.md`: query-builder + renderer blocks, ER columns, API table
- `docs/guide/02-upload-and-profile.md`: extraction also drafts search queries (2 LLM calls)
- `docs/guide/03-job-discovery-and-matching.md`: filter-first searches, per-source
  capability table, Regenerate + staleness, currency caveat
- `schema.d.ts` regenerated; diagrams re-rendered

## Definition of done

- Backend + frontend gates green; migration `0009` up/down verified
- Live check: extract → draft carries specs → save profile (copied) → `/jobs` prefilled
  (title/skills/exclude/salary from preferences) → edit profile → stale hint → Regenerate
  produces a visibly different, dialect-correct query set → run sends structured Adzuna
  params (`what_phrase`+`what_or`+`what_exclude`+`salary_min`) and NL LinkedIn keywords →
  status echoes everything
- Docs + diagrams updated

## Out of scope

`max_days_old` / `datePosted` freshness mapping (lands with hard filters, #9);
auto-regenerate on save; editing queries on the profile review page; LinkedIn exclusions
(unsupported); salary currency conversion.

## Open question for the owner

1. Exclude terms are generated from profile context (e.g. avoid internship when seniority is
   senior). OK to let the LLM propose them for Adzuna, or keep the Exclude field strictly
   user-entered (LLM leaves it empty)?
