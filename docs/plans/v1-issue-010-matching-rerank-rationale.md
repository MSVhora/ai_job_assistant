# Issue #10 — Matching: cosine ranking + LLM re-rank + rationale

**Status:** Done (2026-09-03)
**Tracks:** GitHub issue #10 (Day 9, Week 2)
**Plan of record:** [v1-implementation-plan.md](v1-implementation-plan.md) §3 (matching engine), §4 (`match`, owner amendment 2026-09-02: keyed on `profile_id`), §8 Day 9, §9 ("rationale for at least the top 10"); [UI plan](v1-ui-implementation-plan.md) §6.5 (match cards + filters UI land here, priority slider in #11)
**Depends on:** Issues #1–#9 (done). Builds directly on `ranked_postings_query()` + embeddings from #9.

---

## Carry-over review: what of this issue already exists

Checked the issue's four checkboxes against the code after #9:

| Checkbox | State | Resolution |
|---|---|---|
| Migration: `match` table | Not present (head is `0010`; no `match` model) | Lands here |
| Vector ranking + priority weights → final_score | Vector ranking exists (`services/matching.py::ranked_postings_query` from #9); no `final_score`, no weights | Lands here, wrapping the #9 query |
| LLM re-rank + "why this matches" rationale, top N only | Not present; `adapters/llm.py::parse_structured` (pydantic-validated + one repair round-trip, token logging) already exists | Lands here |
| `GET /api/matches` with filter/sort params | Not present; `MatchFilters` schema from #9 is reused | Lands here |

## Goal

Turn the #9 building blocks into the v1 matching pipeline: after every search run,
postings are vector-scored against the profile and stored in a `match` table; the top N
get one batched LLM re-rank that produces fit sub-scores and a "why this matches"
rationale; `GET /api/matches` serves stored matches with the #9 hard filters plus
sort/pagination. The jobs dashboard shows ranked match cards with expandable rationale.

**Acceptance (issue):** ranked matches with rationale for top 10; re-rank cost logged with
token counts (adapter logs already carry token counts; the run outcome surfaces them too).

## Locked decisions (proposed — owner sign-off before build)

| Decision | Choice | Rationale |
|---|---|---|
| When matching runs | Final stage of the ingestion background task (`run_search`), after all sources commit; matches are **profile-level**, upserted per run — not per search | Re-rank is LLM cost — never run it per GET request. `match(profile_id, job_posting_id)` unique: scores always reflect the latest run; postings dedupe globally already |
| Profile identity for a run | Optional `profile_id` on `JobSearchRequest` (validated → 404 if unknown). Omitted → most recently updated profile. No profiles → matching stage skipped with `MatchingOutcome.status = "skipped"` warning on the run results; the search itself still succeeds | Multi-profile since #6; explicit id keeps the dashboard honest, default keeps single-profile UX frictionless |
| Scoring inputs | `vector_score = clamp(1 - cosine_distance, 0, 1)` (pure SQL). Re-rank LLM returns per posting: `role_fit` 0–10, `company_fit` 0–10, `rationale` (≤ 60 words) | Vector score is the deterministic base; the LLM adds judgement signals a single vector can't express (description-level fit, employer signals) |
| `final_score` formula | Re-ranked: `w_v*vector_score + w_r*(role_fit/10) + w_c*(company_fit/10)`. Not re-ranked: `vector_score` unchanged. Weights live in `Settings` (`match_weight_vector/role_fit/company_fit`, defaults 0.4/0.4/0.2) until #11 moves them into preferences for the slider | Meets the issue's "priority weights → final_score" with config-level plumbing; #11's slider re-weights without touching scoring code. Caveat documented: re-ranked and unranked scores blend two scales, and top-N membership is chosen by vector score |
| Re-rank cost control | Top N by vector score **lacking a rationale**, capped at `Settings.rerank_top_n` (default 10). One batched `parse_structured` call per refresh (not N calls). If every top-N posting already has a rationale → **zero LLM calls** | Existing rationales stay valid while the profile is unchanged, so repeat searches cost nothing; new postings entering the top N trigger exactly one batched call |
| Re-rank failure degrades | Matches persist with vector scores, `rationale` null, `MatchingOutcome.status = "failed"` + warning on the run results; the search run itself still ends `succeeded`/`partial` | Same graceful-degradation rule as failed embeds in #9; a missing rationale must never lose ranked matches |
| Rationale staleness | Profile content change (save/gap-fill apply, after `refresh_profile_embedding`): re-score all matches in bulk SQL **and null all rationales** inline — no LLM call on the save path. Next search run re-ranks the top N | Keeps profile saves sub-second and cost-zero; a stale "why this matches" written against an old profile is worse than none. Guide documents that rationales refresh on the next search |
| Match pipeline triggers | (a) end of `run_search`; (b) profile save / gap-fill apply (re-score + rationale invalidation only). Gap-fill mutates `structured_profile` directly, so it needs its own call — same pattern as #9's `refresh_profile_embedding` wiring | Both paths change what "why this matches" means; the service is a single reusable entry point |
| `match` table shape | `id` uuid pk; `profile_id` fk `profile.id` **ondelete CASCADE**, indexed; `job_posting_id` fk `job_posting.id` **ondelete CASCADE**, indexed; `vector_score real`, `role_fit real null`, `company_fit real null`, `final_score real`, `rationale text null`; `created_at`, `updated_at` (timestamptz, conventions); unique `(profile_id, job_posting_id)`; index `(profile_id, final_score DESC)` | Stored `role_fit`/`company_fit` (beyond the ER sketch) let #11's slider re-weight instantly without re-calling the LLM — flagged as ER amendment for the owner. FK indexes + dashboard index per database standards |
| Run-results surface | `job_search` gains `matching JSONB null` (a `MatchingOutcome`: status ok/failed/skipped, scored_count, rationale_count, rerank token counts, warning) — same migration as the table | Acceptance requires re-rank cost visibility; token counts surface in the run results UI, not just server logs |
| `GET /api/matches` | `profile_id` required (404 unknown; **409** when the profile has a null embedding — can't rank, say so). Params: `MatchFilters` fields + `sort` (`final_score` default / `vector_score` / `posted_at`, nulls last) + `limit` (default 50, max 200) + `offset`. Filters/sort apply to stored match rows joined with posting columns at read time | Read-time filtering needs no re-scoring; 409 is actionable ("re-save the profile once the embedding provider works") instead of a silently empty dashboard |
| Re-rank prompt | Compact profile digest (headline, skills, seniority, target title/location, latest experience titles) + per posting: id, title, company, location, description truncated ~1,500 chars. Response mapped by posting id; unknown/missing ids ignored defensively | One call, bounded prompt size; map-by-id survives an LLM that drops or hallucinates an entry |
| New dependencies | None — pgvector, litellm, and all service primitives exist | |

## Scope

### Backend

**Migration `0011_add_match_table`**
- Creates `match` per the decision row and adds `job_search.matching JSONB null`
- Docstring records the profile-keying amendment (owner 2026-09-02), the `(profile_id,
  final_score DESC)` dashboard index, and CASCADE semantics (deleting a profile or
  posting deletes its matches). Downgrade drops the column and table
- Review the autogenerated file for the composite index (`final_score DESC`) and the
  unique constraint — autogenerate misses descending indexes

**Models — `app/models/match.py` (new, exported from `models/__init__`) + `job_search.py`**
- `Match` ORM model + `job_search.matching: Mapped[dict | None]`

**`app/schemas/matching.py` (extend)**
- `RerankItem` / `RerankResult` (LLM contract), `MatchingOutcome`, `MatchSort` literal,
  `MatchQueryParams` (filters + `profile_id` + sort + limit/offset), `MatchResponse`
  (match fields + nested `JobPostingSummary` — reuse the existing schema)

**`app/services/matching.py` (extend)**
- `refresh_matches_for_profile(profile_id, *, invalidate_rationales) -> MatchingOutcome`:
  bulk vector re-score (single upsert-from-select over non-null embeddings), optional
  rationale invalidation, top-N selection, one batched re-rank, application of sub-scores
  + rationale, outcome built with token counts from `StructuredResult`
- `matches_query(profile_id, params)` — read-time filtered/sorted select of
  `Match ⋈ JobPosting`
- Prompt composition helper (pure, unit-testable)

**`app/services/ingestion.py` + `app/services/profile_service.py` + `app/services/gap_fill.py`**
- `run_search`: resolve profile (explicit or latest), run the refresh as the final stage,
  persist `MatchingOutcome` onto the run; matching exceptions degrade to `failed` outcome,
  never fail the run
- Profile save / gap-fill apply: call the refresh with `invalidate_rationales=True`
  (re-score + null-out only)

**`app/routers/matches.py` (new) + `app/core/config.py` + `.env.example`**
- `GET /api/matches` per the decision row; router registered in `main.py`
- New settings: `match_weight_vector/role_fit/company_fit` (0.4/0.4/0.2),
  `rerank_top_n` (10) — documented in `.env.example`

### Frontend

- Regenerate `lib/api/schema.d.ts` from the new `openapi.json` (match responses never
  hand-typed)
- Jobs page: profile selector (default latest profile) feeding both the search request
  (`profile_id`) and the matches query; ranked match list becomes the dashboard view once
  matches exist — the run banner + per-source results view stay as-is
- New feature components (each < 200 lines): `MatchList` (loading skeleton / error retry /
  no-matches empty state with filter hints / no-profile empty state linking to profile
  creation), `MatchCard` (rank, score, title/company/location/salary, source badge,
  expandable rationale via accessible disclosure), `MatchFilterBar` (location, remote,
  job type, posted-within, sort)
- Matches fetched via TanStack Query (`lib/api` client only); filters/sort are query state;
  `aria-live` on list status changes

### Tests

- `tests/test_matching.py` (new) — vector score clamp math; final_score formula for
  re-ranked vs unranked rows; top-N selection (rationale-less only, cap respected);
  zero-LLM-call path when top N already rationaled; upsert dedupe (second run updates,
  never duplicates); re-rank response mapped by id, unknown ids ignored; LLM failure →
  rationale null + outcome `failed` + run still succeeds; prompt truncation + digest shape
- `tests/test_matches_endpoint.py` (new, httpx) — 404 unknown profile, 409 null embedding,
  filter combinations, sort orders incl. nulls-last `posted_at`, limit/offset bounds,
  response model shape (no ORM leak)
- `tests/test_ingestion.py` extended — run with profile → matches persisted + outcome `ok`;
  no profiles → outcome `skipped` warning, run `succeeded`; matching failure → outcome
  `failed`, run status unaffected
- Profile/gap-fill tests extended — save/apply re-scores and nulls rationales (no LLM call)
- `tests/test_matching_schema.py` extended — new request models' validation edges
- Migration up/down exercised by the existing `migrated_database` fixture

### Doc impact

- `docs/plans/v1-implementation-plan.md`: §4 `match` sketch gains `role_fit`/`company_fit`
  + `updated_at` and the `job_search.matching` column (amendments flagged here for owner
  acceptance); §8 Day 9 stays as-is
- `docs/architecture.md`: ER `match` entity — `candidate_id` → `profile_id`, new columns,
  CASCADE notes; "priority-weight column lands with the matching work" note updated to
  reflect weights-in-Settings-for-#10 / preferences-#11; sequence diagram verified against
  the shipped flow → re-render (`node scripts/render-diagrams.mjs`)
- `docs/instructions/database-postgres.md`: dashboard-index example corrected from
  `match(candidate_id, final_score DESC)` to `match(profile_id, final_score DESC)`
  (already mandated by the plan-of-record §4 amendment; doc hasn't caught up)
- `docs/guide/03-job-discovery-and-matching.md`: matching/re-rank/rationale sections marked
  live; document the scoring formula, top-N cap + zero-cost repeat behaviour, rationale
  refresh timing (next search after profile changes), degrade-on-LLM-failure, and the
  read-time filter/sort semantics
- `.env.example` + `schema.d.ts` regeneration; no frontend-only env changes

## Definition of done

- `ruff check . && ruff format --check . && pytest` green in `backend/`
- `npm run lint && npm run build` green in `frontend/`
- Migration `0011` generated, reviewed, applied; up/down verified
- Live check: one `/jobs` search produces ranked matches with rationale for top 10;
  `matching` outcome on the run shows non-zero rerank token counts; repeat search with no
  new top-N postings logs zero LLM calls
- Docs updated; diagrams re-rendered

## Out of scope (this issue)

Priority-weight slider + weight persistence in preferences (#11 — slider UI and re-weight
on change; stored sub-scores make it cheap), source multi-select as a matches filter,
ANN/HNSW index, posting detail endpoint, manual "re-run matching" trigger, pruning of
stale matches, match explanations beyond the text rationale.
