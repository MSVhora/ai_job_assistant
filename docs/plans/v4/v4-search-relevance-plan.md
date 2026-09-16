# v4 plan — search relevance: profile-grounded queries, source-dialect optimization, hybrid scoring

**Status:** Proposed plan for v4 (owner sign-off pending on decisions marked ⚠)
**Depends on:** v1 (#1–#12), v2 (#13–#23), v3 (#24–#30) — all done.
**Plan of record:** this file; per-milestone issue plans (`v4-issue-NNN-*.md`) written
before implementation (v1 retro lesson), one GitHub milestone `v4`,
issues merged sequentially into a `v4/milestone` branch (see AGENTS.md git workflow).

Goal: the user gets *relevant* matches, not just matches. This plan is grounded in
(a) how the code works today, (b) what Adzuna's API actually supports, and (c) how
the Apify LinkedIn actors are best driven. Each problem states evidence first, then
a solution scoped to our non-negotiables (JobSource connector interface, LiteLLM
wrapper, Alembic migrations, response models).

Sources consulted:

- Adzuna: developer.adzuna.com overview + `/docs/search` + interactive OpenAPI docs;
  ToS rate limits (25/min, 250/day, 1000/wk, 2500/mo free tier); community usage
  (jobsearchagent budget formula, jobs-adzuna PHP client param coverage, MCP servers
  exposing `what_and`/`title_only`/`category`/`salary_include_unknown`).
- Apify LinkedIn: `curious_coder/linkedin-jobs-scraper` input schema (keywords,
  location, geoId, distance, datePosted, companyIds, under10Applicants,
  autoConvertToAiSearch, limitPerSource, splitByLocation/splitCountry), the Aug 2026
  LinkedIn "AI search" migration notes (classic filters f_E/f_JT/f_WT removed;
  only f_TPR/f_C/f_AL/f_EA survive as URL filters), `linkedin-jobs-search-scraper`
  (cookie-based, boolean search), and community write-ups (width.ai n8n workflow:
  boolean queries, pre-AI title filtering, cross-run dedupe).

---

## Problem 1 — Queries are generated once, from a thin slice of the profile

**Evidence.** `SourceQuerySpec`s are produced at extraction time (or on explicit
regenerate) by `services/query_builder.py:117-207`. The LLM prompt context
(`query_builder.py:86-98`) contains only `target_title`, `headline`, first 12
skills, and `seniority`. It never sees: `preferences.target_location`,
`contact.country`, `remote_preference`, `salary_min/max`, the full skills list,
summary, or parsed experience. Search execution (`services/ingestion.py:165-176`)
never reads the profile at all — shared filters (location, country, salary,
`max_days_old`) come purely from the request payload, so the user retypes what the
resume already told us.

**Solution — ground query generation in the full profile, and only regenerate when inputs actually change.**

Clarification: "re-render" here means two different things, and only one of them
runs per search:

- **Rendering** (already exists, `services/query_rendering.py`): the cheap,
  deterministic mapping of a stored `SourceQuerySpec` → `JobSearchQuery`. This
  runs on every search and never involves the LLM. No change needed beyond the
  precedence fix in Problem 4.
- **Generation** (the expensive LLM step): this must **not** run every time the
  user visits a page or hits search. It runs only when inputs change.

1. Extend the query-builder prompt context to include: full skills (not 12),
   `preferences` (target title/location, seniority, remote preference, salary band,
   currency), `contact.country`, headline, and a truncated summary. Cap tokens with
   the existing digest helpers (`services/embedding.py:23-47` already builds a
   compact profile digest — reuse it).
2. **Content-hash cache for generation.** Store a `queries_input_hash` on
   `profile` alongside `search_queries` — a SHA-256 over exactly the inputs the
   prompt consumes (structured_profile JSONB + preferences + source configs
   version). On any path that would generate (extraction, explicit regenerate,
   pre-search check): if the hash matches the stored one, skip the LLM call and
   keep the existing specs. Generation fires only when the resume was re-uploaded,
   the user edited the profile, or the query-builder prompt/config changed (bump a
   `QUERY_BUILDER_VERSION` constant into the hash). One Alembic migration for the
   new column.
3. The "regenerate" button stays manual and always forces a new generation (it
   overwrites the hash afterwards).
4. Make `run_search()` resolve defaults from the profile when the request omits
   them: `country ← contact.country`, `location ← preferences.target_location`,
   `salary_min ← preferences.salary_min`, remote handling from
   `remote_preference`. Request values still win (never trust the client, but do
   let it override).
5. Keep generation at temperature 0 for the persisted default specs (0.8 is fine
   only for the "regenerate alternatives" endpoint) — one-shot variance in the
   stored default hurts reproducibility.

## Problem 2 — The profile has no parsed years-of-experience or seniority signal for retrieval

**Evidence.** Experience dates are stored verbatim strings
(`schemas/profile.py`, `experience`), so neither query building nor scoring can
use "8 years, mid-senior backend". `final_score` has no seniority component, and
LinkedIn's classic experience-level filter is gone (see Problem 5) — the only way
to signal level is via query text.

**Solution — parse experience at extraction time.**

1. Extend the extraction schema (pydantic, `schemas/profile.py`) with
   `years_of_experience: int | None`; LLM computes it from the date strings during
   the existing extraction call (no extra LLM round-trip).
2. **Derive seniority from years of experience.** If the user hasn't explicitly
   set `preferences.seniority`, fill it from YOE using a simple deterministic
   mapping (e.g. 0–1 → entry, 2–4 → mid, 5–7 → senior, 8–11 → staff/lead,
   12+ → principal/director; exact bands configurable in `Settings`). The
   user-set value always wins; the derived one is a fallback and marked as such
   in the review UI so the user can correct it at review time.
3. Store on `StructuredProfile` JSONB — no schema change needed (JSONB
   is the documented home for flexible payloads), but version the field and
   backfill opportunistically on next profile edit. If we later want to filter by
   it in SQL, promote to a real column (per DB standards: queryable ⇒ column).
4. Feed it into: the query-builder context (Problem 1), the profile embedding
   digest (already includes seniority — now with real values), and the rerank
   prompt.

## Problem 3 — Adzuna's rich query parameters are mostly unused

**Evidence.** Adzuna supports `what`, `what_and`, `what_phrase`, `what_or`,
`what_exclude`, `title_only`, `category`, `salary_include_unknown`, full_time/
part_time/contract/permanent booleans, `sort_by`/`sort_dir`, `location0..7`
hierarchical places, `distance`, `max_days_old`, pagination via `/search/{page}`.
Our adapter (`adzuna.py:60-78`) only uses `what_phrase`, `what_or` (space-joined
skills), `what_exclude`, salary, `max_days_old`. Community best practice
(jobsearchagent) is multi-pass searching: one call per (location × keyword
variant) + a remote pass, deduped by URL.

**Solution — exploit the dialect, stay inside the JobSource interface, keep the UX simple.**

Principle: the user fills one search form. Everything below is what the backend
does with that single form; nothing here adds required fields to the UI.

1. **Use `what_and` for must-have skills.** Today `skills_any` → `what_or` only.
   Split the spec's skills into `skills_all` (map → `what_and`) and `skills_any`
   (→ `what_or`). This directly mirrors the resume: must-have stack goes in
   `what_and`, nice-to-haves in `what_or`.
2. **Use `title_only` in parallel.** `title_only` is currently a manual option.
   Auto-issue two sub-queries per Adzuna run: (a) `what_phrase`/broad, (b)
   `title_only=<title>` — deduped by `external_id`. Title matches are the highest
   precision signal; description matches add recall.
3. **Map contract/type preferences silently.** If the profile or request already
   implies a job type (e.g. salary band, seniority), pass the matching
   `full_time`/`permanent` booleans automatically; otherwise don't send them.
   Power users can override via the existing declared options — but nothing new
   is required.
4. **`salary_include_unknown=1`** when the profile has no salary floor; omit when
   it does. Currently unknown-salary jobs are silently dropped whenever
   `salary_min` is set, biasing results to companies that publish salaries.
5. **Pagination within quota.** Fetch page 2 when page 1 returns a full 50 rows
   and `results_wanted > 50`, subject to the free-tier ToS limits (25/min,
   250/day). Add a tiny per-process call counter surfaced in logs so a
   multi-source/multi-page run can't burn the daily quota silently.
6. **Multi-pass budget formula** (adopted from community usage): calls per run =
   Σ(sub-queries × pages). Document it next to the connector and enforce a
   `max_adzuna_calls_per_run` setting (default ~4).

## Problem 4 — Adzuna drops the free-text query when a title exists (and vice versa)

**Evidence.** `_apply_search_terms` (`adzuna.py:60-71`) treats `title_phrase` and
`query` as mutually exclusive: with a title, the richer `query` text is discarded.
The LinkedIn actor gets the opposite treatment — a synthetic natural-language
string overrides `query`. So the LLM's carefully composed `spec.query` often never
reaches either source.

**Solution — define precedence per source, deterministically.** In
`query_rendering.py`, produce a per-source *term plan* rather than a single
string: `{what_and, what_or, what_phrase, what_exclude, query}` for Adzuna;
`{keywords (NL string), location, date_posted}` for LinkedIn. Adzuna combines
`what_phrase` + `what_and`/`what_or` + (only if no phrase) `what`. LinkedIn joins
title + skills into the NL string but keeps a user-typed `query` as an override.
Write the precedence table in the connector docstring and lock it with tests
(`test_query_rendering.py` gains a precedence case each).

## Problem 5 — LinkedIn (Apify) queries ignore the new AI-search reality

**Evidence.** Since Aug 2026 LinkedIn's forced AI search removed experience/job
type/workplace/salary URL filters; only `f_TPR` (date), `f_C` (company), `f_AL`,
`f_EA` remain, and `autoConvertToAiSearch` merely *appends* old filters to keywords
as natural language with no guarantee. Our actor config
(`connectors.yaml`) uses `autoConvertToAiSearch: true` and builds keywords as
`title_phrase + " with " + skills + ", offering X or more"` (`apify.py:44-67`).
Exclusions are silently dropped; `country` is ignored (location is free text the
user must type); the 1000-per-search cap and `splitByLocation` are unused;
`limitPerSource` is not set from `results_wanted`.

**Solution — write LinkedIn queries for the AI search engine, on purpose.**

1. **Compose the keywords string as a semantic brief, not a keyword soup.** The
   AI search is natural-language-first (LinkedIn's own engineering talks about
   semantic/conversational search). Build: `"{target_title} with {2–4 strongest
   skills}, {seniority} level"` — drop salary text from keywords entirely (salary
   in NL queries adds noise; it isn't a reliable LinkedIn filter either). Keep the
   existing natural-language builder but source the pieces from the parsed profile
   (Problems 1–2) instead of the raw spec only.
2. **Put exclusions into the NL string** (`"not {exclude_any}"`) instead of
   dropping them — post-Aug-2026, URL-level exclusion doesn't exist and NL is the
   only channel.
3. **Set `limitPerSource = results_wanted`** and cap at ~250 to bound cost (the
   actor bills per result). Today nothing bounds it.
4. **Use `geoId` when we can resolve it.** Free-text location is resolved by
   LinkedIn's typeahead and can silently match the wrong region; a `geoId` pins
   it deterministically. Cheap v1: map the profile's `contact.country` +
   `preferences.target_location` text as-is; later: a one-time location-lookup
   actor call (reefapi actor has a `Location search` action) cached in the DB.
5. **`splitByLocation` (later).** For country-wide searches the actor can split by
   city to beat the 1000/search cap. Defer until users actually hit the cap; note
   it multiplies billed results.
6. **Consider `curious_coder/linkedin-jobs-search-scraper` (cookie variant) as an
   alternative connector** if keyword precision matters more than
   convenience: it supports true boolean keywords (`"data scientist" AND (Python
   OR SQL) NOT intern`) and returns skills/applicant insights. Cost: requires the
   user's LinkedIn cookies (a secrets-handling problem — keep out of scope unless
   requested).

## Problem 6 — No guard against duplicate concurrent runs of the same profile + source

**Evidence.** One source per search run is **intentional** (per owner decision) —
`JobSearchRequest` takes exactly one `source` (`schemas/job_search.py:67-74`).
But nothing stops the user from firing the same (profile, source) search twice
while the first is still running: double Apify spend, double quota burn, two
ingestion runs racing to upsert the same postings.

**Solution — in-flight run lock per (profile, source).**

1. Before `start_search()` creates a run, check for an existing non-terminal run
   (status in `queued`/`running`) with the same `(profile_id, source)`; if one
   exists, return **409 Conflict** with the active run's id so the UI can point
   the user at it instead of starting a duplicate.
2. Enforcement must survive multi-worker deployments, so the check-and-set is
   done atomically in SQL (e.g. an `advisory lock` keyed on hash(profile_id,
   source), or a partial unique index on `job_search (profile_id, source) WHERE
   status IN ('queued','running')`) — not a naive SELECT-then-INSERT. One
   Alembic migration for the partial index (or none, if advisory locks are used).
3. Different sources for the same profile may still run concurrently — only the
   same (profile, source) pair is restricted.
4. On crash/restart, a run stuck in `queued`/`running` must be reclaimable
   (existing stale-run handling, if any, applies; otherwise a
   `max_run_age` sweeper marks abandoned runs failed so the lock releases).

## Problem 7 — Ranking ignores everything except embeddings + LLM vibes

**Evidence.** `final_score = 0.4*vector + 0.4*role_fit/10 + 0.2*company_fit/10`
(`matching.py:381-387`). No skill-overlap signal, no salary fit, no recency
weight (only a 45-day staleness hard filter), no cross-source dedupe at match
level, and postings without embeddings are excluded entirely (`matching.py:69`).

**Solution — hybrid scoring, computed in SQL where possible.**

1. **Skill overlap score.** Postgres trigram or simple ILIKE hit count of the
   profile's top-N skills in `title + description`, normalized → `skill_score`.
   Compute in the same `rescore_matches()` SQL pass (no row-by-row ORM).
2. **Recency score.** Exponential decay on `posted_at` (e.g. `exp(-days/14)`),
   computed in SQL. Fresh jobs surface; stale-but-relevant don't vanish.
3. **Salary fit.** `1.0` if unknown, else scaled proximity of
   `[salary_min, salary_max]` to the profile's preference band. Prevents the
   current bias where unknown-salary jobs rank blindly.
4. **Weights in `Settings`** (like today's `vector/role/company` weights), e.g.
   `0.35 vector, 0.25 skill, 0.15 recency, 0.15 role_fit, 0.10 company_fit,
   0.0–0.1 salary`. Migration: add columns to `match` (`skill_score`,
   `recency_score`, `salary_score`) — one Alembic migration, model first.
5. **Fallback for un-embedded postings:** score by `skill_score` + recency alone
   (weight-scaled) instead of excluding, so ingestion hiccups don't hide jobs.

## Problem 8 — Rerank is a blind one-shot top-10

**Evidence.** `_rerank_top_matches()` (`matching.py:293-374`) sends only the top
10 by raw cosine to one batched LLM call; everything below rank 10 never gets a
rationale; the rerank sees a 1500-char posting digest and 400-char profile digest
— it never sees parsed skills overlap or the profile's preferences.

**Solution — candidate pool + informed rerank.**

1. Rerank the top `rerank_top_n` (keep 10) **after** the new SQL signals exist,
   so the pool is chosen by hybrid score, not cosine alone.
2. Include in the prompt: profile digest **+ explicit must-have skills +
   seniority + salary band + remote preference**; per posting: digest +
   `skill_score` overlap list. Keep the one batched call (cost discipline).
3. Optional (flagged setting): a second pass for ranks 11–20 if the user clicks
   "why not this one?" — rationale on demand instead of paying to rerank deep.

## Problem 9 — Cross-source duplicates are double-counted

**Evidence.** Dedupe is `(source, external_id)` on `job_posting` only — the same
job on Adzuna and LinkedIn becomes two rows and two matches, diluting the
dashboard.

**Solution — canonical-company-title dedupe.** In ingestion, after normalize:
match on `(normalized_company, normalized_title, location_bucket)` with
trigram similarity ≥ 0.92 on title (pg_trgm) and same metro/country; merge
posting records (`source_urls: list`), keep the freshest `posted_at`. Schema:
new `job_posting.canonical_id` self-FK or a `canonical_group` column — one
Alembic migration, indexed. Matches dedupe on the canonical id.

## Problem 10 — No feedback loop: relevance never improves

**Evidence.** Nothing records whether the user opened, saved, or dismissed a
match; query specs only change when manually regenerated.

**Solution — lightweight signals now; applied/not-applied as its own feature plan.**

Design principles: zero required user effort (signals must come from behavior the
user already exhibits), one click max for explicit signals, and never block a
user action to ask why.

1. **Implicit signals (no user effort, track server-side):**
   - `first_opened_at` / `opened_count` on `match` — fires when the user opens
     the job detail (the redirect/apply-link endpoint is the natural hook).
   - `dwell_ms` on the detail view (optional; only if the frontend already has a
     page-lifecycle event to hang it on — don't build new instrumentation).
   - Search→match-list→detail funnel completion is itself a signal: matches
     listed but never opened across many searches are weak positives at best.
2. **Explicit signals (one click, from behavior that already exists):**
   - `saved_at` — the existing save/bookmark action.
   - `dismissed_at` — the existing hide/dismiss action (if present in UI; if not,
     it's a small card-menu addition).
   - `clicked_apply_at` — fires when the user clicks through the external apply
     URL. This is our best proxy for "applied" without building an application
     tracker.
3. **Use the signals (cheap, monthly or on-demand):** a "tune my queries" action
   whose LLM prompt receives aggregated counts (which skills/titles/companies
   appear in clicked+saved vs never-opened vs dismissed matches) and rewrites the
   profile's `search_queries` + embedding digest. Via LiteLLM wrapper,
   cost-estimated like every batch op. Respect the Problem 1 hash: tuning
   overwrites the hash so the change isn't silently reverted.
4. **Schema:** nullable timestamps on `match` (`first_opened_at`, `saved_at`,
   `dismissed_at`, `clicked_apply_at`) — one Alembic migration. Counters later if
   needed.
5. **Out of scope here — "did they actually apply / application status tracking"
   is a feature in its own right** (application pipeline states, reminder UX,
   maybe email parsing) and needs a detailed separate implementation plan before
   any work starts. For now, `clicked_apply_at` is the honest, zero-burden proxy.

---

## Sequencing

| Phase | Problems | Why first |
|---|---|---|
| A — profile-grounded queries | 1, 2, 4 | Biggest relevance win, zero new deps, no scraping changes |
| B — Adzuna dialect | 3 | Cheap API-only wins (`what_and`, `title_only` pass, `salary_include_unknown`, pagination+quota) |
| C — LinkedIn dialect | 5 | NL brief composition, exclusions, `limitPerSource`, geoId |
| D — run hygiene | 6 | 409 on duplicate (profile, source) runs before fan-out of anything else |
| E — scoring | 7, 8, 9 | Needs one migration (score columns + canonical dedupe) |
| F — feedback loop | 10 | Implicit + one-click signals; applied-tracking gets its own plan |

Definition of done per problem: ruff + pytest green; connector changes covered in
`test_adzuna_adapter.py` / `test_apify_adapter.py` / `test_query_rendering.py`;
scoring changes covered in `test_matching*.py`; any schema change ships with its
Alembic migration; `.env.example` updated for new Settings; user-facing behavior
changes update `docs/guide/` + `docs/architecture.md` and re-render diagrams.
