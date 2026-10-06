# Issue #37 — Hybrid scoring signals + refreshed rerank pool (M5 / Phase E)

**Status:** Implemented (branch `v4/37-hybrid-scoring-signals`; implementation notes: the
skill-signal SQL went with per-skill `CASE ~* '\m…\M'` sums instead of a bound text-array
`unnest` lateral — the alias's column name was flaky and 25 inline CASE whens keep the code
transparent; salary-fit gaps normalize by `max(width, 1.0)` (not the 1e-9 floor) so a
zero-width preference band can't turn a £1 miss into score 0; scoring-signal values are
renormalized for fallback rows, which can outscore embedded rows on equal signals — the
v1 "two scales" caveat now runs in both directions; `_signal_final` and reranked blends
cap at 1.0; the rerank pool roughly kept the old cosine ordering on identical fixtures
plus a `posted_at desc` tiebreak; `_profile_digest` now wraps the shared
`profile_digest_parts` and appends rerank-only salary/remote lines (embedding inputs
untouched); `.env`/`.env.example` migrated to the new `MATCH_WEIGHT_*` block with the
startup sum-1.0 validator; full suite green (424 tests), frontend lint+build green.
Follow-ups in the same branch: doubled percent sign fixed on the match card / detail
panel (`scorePercent` already appends `%`); priority slider now commits the match-list
refetch 250ms after the drag settles (`usePrioritySetting.listValue`), instant visual only.
**Tracks:** GitHub issue #37 (milestone `v4`, Phase E — scoring, Problems 7 + 8)
**Plan of record:** [v4-search-relevance-plan.md](v4-search-relevance-plan.md) Problems 7–8
**Depends on:** #31–#36 as merged (one source per run, hash-cached queries, YOE/seniority on
`StructuredProfile`); no hard code dependency beyond `matching.py` current shape
**Blocks:** Phase F (#39 feedback signals) and #38 canonical dedupe interplay — matches now carry
five sub-scores; dedupe (#38) should land on top of the same migration-cost category, not before

---

## Goal

`final_score = 0.4*vector + 0.4*role_fit/10 + 0.2*company_fit/10`
(`backend/app/services/matching.py:381-387`) ignores skill overlap, recency, and salary fit, and
the rerank pool (`matching.py:297-304`) is the top-10 by raw cosine among rationale-less rows.
Postings without embeddings never even score (`matching.py:180`),
and `_profile_digest` (`matching.py:390-411`) is a stale duplicate of the shared
`services/embedding.py:profile_digest_parts()` — the #32 comment on the issue recommends
switching it onto the shared helper so YOE/seniority reach the rerank prompt for free.

## Locked decisions

| Decision | Choice | Rationale |
|---|---|---|
| New weights (defaults) | `match_weight_vector=0.35`, `match_weight_skill=0.25`, `match_weight_recency=0.15`, `match_weight_role_fit=0.15`, `match_weight_company_fit=0.05`, `match_weight_salary=0.05` — sum exactly 1.00 | The issue's example (`0.35/0.25/0.15/0.15/0.10 + salary`) sums to 1.0 only with salary 0, which would ship the salary signal dead by default and contradict scope item 3 (unknown-salary bias is the *point* of the salary score). Scale kept: skill+recency+salary = the cheap deterministic signals get the mass LLM vibes (role/company) lose |
| Weight-sum guard | One `field_validator` on `Settings` asserting the five weights sum to `1.0 ± 0.01` (fast-fail at startup) | Wrong `.env` weights today distort every score silently; validation beats silent re-normalization |
| Priority slider semantics unchanged | The slider still distributes **only the role/company judgment mass** (0.15 + 0.05 = 0.20): read-time `w_role = 0.20 * priority`, `w_company = 0.20 * (1 - priority)`; skill/recency/salary stay fixed from Settings | Keeps the one-knob UX ("employer vs role") from #11 intact; `default_priority()` = 0.15/0.20 = 0.75 reproduces Settings defaults exactly. The other four weights are precision instruments, not user opinion |
| Skill signal | `skill_score`: fraction of the profile's top-N skills (`match_skill_signal_skills`, N=25, Settings) that hit word-boundary, case-insensitive regex (`\m<skill>\M`, regex-escaped) in `coalesce(title,'') \|\| ' ' \|\| coalesce(description,'')`; skills array passed as a query bind parameter, computed in the same bulk SQL pass as vector scoring — NOT row-by-row, NOT pg_trgm | Zero-overlap postings still score 0, so no echo of the old "excluded entirely" failure for odd profiles. ILIKE/regex needs no extension: pg_trgm is planned for #38's dedupe, not here — holding the schema surface at 3 columns + one nullability change. Denominator is the number of skills the profile supplied (skilled profiles get normalized scores, not inflate-by-count) |
| SQL ↔ Python mirror | One helper `skill_hit_terms(text, list[str]) -> bool` semantics implemented **in Python** for rerank prompt lists, and as SQL regex matching in `rescore_matches` | Scope item 7 wants a per-posting *overlap list* in the rerank prompt — a bulk SQL pass can only return counts. Both implementations share word-boundary/escaping rules; `test_matching.py` pins them to identical behavior on fixture postings so they can't drift |
| Recency signal | `recency_score = exp(-max(0, days)/match_recency_decay_days)`, `match_recency_decay_days: int = 14` (Settings, ge=1); `posted_at` NULL → **0.5** neutral | Plan-of-record's `exp(-days/14)` verbatim, with a Settings knob. NULL posted_at rows stay surfaced by `freshness_condition()` (D4) so they keep a neutral mid-score instead of 0, consistent with "unknown keeps it visible" |
| Salary signal | `salary_score`: unknown posting band → **1.0**; no preference band → **0.5** neutral; bands overlap (`posting_max >= pref_min and posting_min <= pref_max`) → 1.0; else `max(0, 1 - gap/band_width)` where gap = distance between the nearer edges and band width = max(pref width, 1e-9); currency differs or posting currency known while preference is unset → treat posting band as unknown | Overlap-first (not midpoints) matches how salary ranges are used; decay is linear in multiples of the preference width so a £50k-wide preference doesn't punish a £1k miss like a £5k-wide one would. Currency mismatch must not compare numbers per unit — unknown is the honest answer. Computed in the same SQL CASE pass |
| Fallback scoring (un-embedded postings) | Included in the scored corpus. `vector_score` becomes **nullable**: fallback rows persist `vector_score=NULL`, `final_score = (w_skill*s + w_rec*r + w_sal*sal) / (w_skill + w_rec + w_sal)` (weight-renormalized to full scale). Rerank-blend and priority blends treat NULL vector as **0** | Scope item 5 word-for-word ("weight-scaled"). Renormalizing keeps fallback finals on the same 0–1 display scale as embedded rows instead of a 0.45-capped scale. Making `vector_score` nullable (instead of storing 0) keeps "no embedding" distinguishable from "terrible cosine match" in the API |
| Hybrid blend helper | One shared SQL expression builder `_hybrid_score_expression(vector_col, role_col, company_col, skill_col, recency_col, salary_col, weights)` in `matching.py`, used by: rescore upsert (final_score for un-reranked + re-blended reranked rows), rerank-pool selection ORDER BY, `_priority_sort_expression`, and `_final_score()` write-on-rerank (Python twin for the same coefficients) | Today the formula exists in ~4 places (upsert blend, priority sort, `_final_score`, pool ordering-by-vector). The failure mode this issue fixes — pool chosen by cosine while list sorts by final — reappears instantly if a fifth call site is added and one drifts. One expression function + one Python twin, pinned equal by test |
| Rerank pool | Same `rationale IS NULL` filter, but ordered by the **Settings-default hybrid expression** (not `vector_score.desc()`), top `rerank_top_n` (10) unchanged; fallback rows may enter the pool (their blend treats vector as 0) | The bug this issue exists to fix. The priority *slider* is read-side only (unchanged); the pool choice always uses Settings-road weights so stored results stay deterministic across requests |
| Rerank prompt profile side | Switch `_profile_digest` onto the shared `embedding.profile_digest_parts(profile)` (import), then append rerank-only lines built locally in `matching.py`: salary preference band, remote preference. Do **NOT** edit `profile_digest_parts` itself | Byte-stability note on `profile_digest_parts` (embedding.py:23-29) forbids display-only edits there; rerank-only lines live in matching. Shared helper brings YOE + work-authorization lines that `_profile_digest` lacked (the stale-duplicate bug #32 flagged) |
| Rerank prompt posting side | Per posting: existing digest block + `skills overlap: <list | none>`. Overlap list from the Python mirror helper. Same single batched `parse_structured` call, token logging unchanged | Cost discipline kept exactly as today |
| Sub-score backfill | No data migration: existing rows read NULL sub-scores until the next `rescore_matches()` run; every read path COALESCEs (see blends) so nothing crashes or ranks secretly-0 in the window | Rescore runs after every search and every profile-save; the NULL window is minutes old by construction. A backfill migration would need Python-side computation anyway (skills live in JSONB), which is exactly what a data-migration standard forbids mixing |
| API surface | `MatchResponse` gains `skill_score`, `recency_score`, `salary_score` (all `float \| None`); regenerate `openapi.json` + `schema.d.ts` | Scores are user-visible ranking input; hiding them entirely means they can never be debugged from the UI. No match-card UI change in this issue |
| Migration number | `0018_add_match_hybrid_score_columns` — model first: three nullable `Float` columns + `vector_score` → nullable | Ships in the same change as the model edit. Downgrade is destructive (drops stored sub-scores; re-derivable from the pipeline) — noted in the docstring per standards |

## Scope

### Migration (`backend/alembic/versions/0018_add_match_hybrid_score_columns.py`)

1. `op.add_column("match", ...)` × 3: `skill_score`, `recency_score`, `salary_score`
   (`Float, nullable=True`).
2. `op.alter_column("match", "vector_score", nullable=True)`.
3. No indexes change (`ix_match_profile_final_score` is keyed on the stored blend; sort
   `vector_score` orderings in code gain NULLS LAST handling — see below).
4. Downgrade: drop the three columns; restore `vector_score` NOT NULL **after** deleting
   fallback rows where `vector_score IS NULL` (destructive for those rows only — they are
   un-embedded postings whose scores re-derive on the next search; docstring states it).

### Backend (`backend/app/`)

- `core/config.py`:
  - New: `match_weight_skill=0.25`, `match_weight_recency=0.15`, `match_weight_salary=0.05`,
    `match_recency_decay_days: Annotated[int, Field(ge=1)] = 14`,
    `match_skill_signal_skills: Annotated[int, Field(ge=1)] = 25`.
  - Change: `match_weight_vector=0.35`, `match_weight_role_fit=0.15`,
    `match_weight_company_fit=0.05`.
  - `field_validator` summing the five weights to 1.0 ± 0.01 (startup fast-fail).
- `models/match.py`: add three nullable `Mapped[float | None]` columns; `vector_score`
  becomes `optional`.
- `services/matching.py` (the bulk of the change):
  - `_hybrid_score_expression(...)` + Python `_final_score(...)` extension as locked above.
  - `rescore_matches()`: corpus SELECT stops filtering `embedding NOT NULL` — the shared
    SQL pass computes all five signals, `vector_score` NULL for un-embedded rows; single
    `pg_insert ... on_conflict_do_update` unchanged in shape (no row-by-row); rerank-blend
    branch and invalidate branch rewritten onto the shared expression. Signals are
    re-persisted every rescore (sub-scores decay with `posted_at`), `updated_at=func.now()`.
  - `_rerank_top_matches()`: pool ORDER BY the hybrid expression; per-posting overlap lists
    via the Python mirror helper; prompt blocks per the locked decisions; `update(Match)`
    gains no new columns but `final_score` re-blend includes the stored sub-scores.
  - `_profile_digest()` → deleted; use `profile_digest_parts` + rerank-only lines.
  - `list_matches()`/`_priority_sort_expression()`/`_SORT_ORDERS`:
    `vector_score`-sort gains `nulls_last()` on the vector line; keep the three existing
    sorts (`final_score`, `vector_score`, `posted_at`) — new sorts are UI desire, out of
    scope. Priority blend moves to the shared expression.
- `schemas/matching.py`: `MatchResponse` gains the three sub-scores.
- JobSource connectors, query building, ingestion: untouched.

### OpenAPI / types

- Regenerate `frontend/lib/api/schema.d.ts` + `openapi.json` from the running backend after
  the response-model change. `MatchResponse` is additive (new optional fields); no hand-written types.

### Frontend

- Type regeneration only. No card/label changes — sub-score display polish is
  deliberately not in this issue (weights defaults are tunable; UI should not hard-code five new labels before the owner sees real score distributions).

### `.env.example` / docs

- `.env.example`: matching block rewritten for the new formula + four new knobs
  (`MATCH_WEIGHT_*`, `MATCH_RECENCY_DECAY_DAYS`, `MATCH_SKILL_SIGNAL_SKILLS`).
- `docs/guide/03-job-discovery-and-matching.md`: new score formula, what each signal means,
  fallback behavior for un-embedded postings, unchanged slider semantics.
- `docs/architecture.md`: matching stage notes hybrid pass + hybrid-chosen pool.
- Diagrams: re-render via `node scripts/render-diagrams.mjs` only if the matching-stage
  diagram text changes (likely a one-line annotation; verify before running).

### Tests (`backend/tests/`, scratch Postgres via `migrated_database` — no SQLite)

- `test_matching.py` (or a new `test_matching_hybrid.py` if the file is getting big —
  DoD says `test_matching*.py`, either satisfies it):
  - SQL signal computation on fixture postings: skill fraction exactness (word boundaries —
    "go" must not match "golang"; case-insensitive; regex-char skills), recency decay at
    known ages, salary CASE each branch (unknown/overlap/near/miss/currency/fallback), NULL
    `posted_at` → 0.5.
  - Fallback: corpus posting without embedding gets scored (count check), `vector_score`
    persisted NULL, `final_score` = renormalized skill+recency+salary blend.
  - Weights: `Settings` override changes `final_score` proportionally; sum-1.0 validator
    rejects an unbalanced `.env` (fast-fails).
  - Rerank pool: seed 12 rationale-less matches with a skill-strong-but-vector-weak posting
    that misses the cosine top-10 → it is in the rerank prompt pool; vector-only regression
    pinned by asserting prompt ordering, not implementation.
  - Priority slider: `default_priority()` reproduces Settings default weights; custom
    priority redistributes exactly the role/company mass, skill/recency/salary fixed.
  - Mirror helper: Python `skill_hit_terms` output == SQL pass hits on the same fixtures
    (anti-drift pin).
- `test_matches_endpoint.py`: response body carries the three new fields (and NULL for
  fallback rows).
- `test_migrations.py`: `0018` up (columns + nullability), downgrade drops cleanly with the
  destructive-fallback-row note reflected in reality.
- Connector / query-rendering tests: excluded — no behavior there.

### Gates

- `ruff check . && ruff format --check . && pytest` green in `backend/`.
- `npm run lint && npm run build` green in `frontend/`.
- Migration `0018` ships in the same change as the `Match` model edit.
- `.env.example` + guide + architecture updated in the same change; diagrams re-rendered
  if touched.

## Risks

| Risk | Mitigation |
|---|---|
| Skill regex on user-controlled posting text (ReDoS / pathological patterns) | Escaping is one `re.escape`-equivalent done in Python before the SQL bind (and mirrored); word anchors never allow user alternation/groupings; PG `regexp_count` with `flags 'i'` and a bounded 25-skill array keeps the pass O(rows × 25) |
| Score distribution surprises (e.g. skill score ~1 for everyone, recency dominating) | Sub-scores exposed in `MatchResponse` specifically so the owner can eyeball distributions from the first real run; weights are .env-tunable without code deploys |
| `vector_score` nullability leaks into old assumptions (`_SORT_ORDERS`, any code path assuming non-NULL) | One shared expression surface + `nulls_last` on the sort; grep-gate for raw `Match.vector_score` uses during review; fallback rows covered by the fallback test |
| Migrate/rollback on a live DB with reranked data drops verified rationales | Downgrade destroys sub-score columns by design (documented), reranks are re-derivable by re-running the pipeline — same posture as the plan-of-record's "one Alembic migration" intent |
| `parse_structured` RerankResult items missing postings | Unchanged from today (skip-and-log); overlap list is additive prompt context and cannot break the contract |

## Out of scope (this issue)

- Canonical cross-source dedupe (Problem 9 / #38) and its `canonical_id` schema work.
- "Why not this one?" second-pass rerank for ranks 11–20 (Problem 8.3) — separate setting + UX.
- Redistribution of the slider across skill/recency/salary (a two-knob UI is a product
  decision, not a scoring fix).
- Exposing sub-scores on match cards / filter-by-score UI.
- Re-embedding or any embedding-model change.
- Feedback-loop signals (Problem 10 / #39).
