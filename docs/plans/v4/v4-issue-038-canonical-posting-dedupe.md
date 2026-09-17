# Issue #38 — Cross-source posting dedupe / canonical grouping (M5 / Phase E)

**Status:** Planned (branch `v4/38-canonical-posting-dedupe`, cut from `v4/milestone` per AGENTS.md workflow)
**Tracks:** GitHub issue #38 (milestone `v4`, Phase E — scoring, Problem 9)
**Plan of record:** [v4-search-relevance-plan.md](v4-search-relevance-plan.md) Problem 9
**Depends on:** #37 (hybrid scoring) — its plan explicitly reserves pg_trgm and the `canonical_id`
schema surface for this issue; dedupe lands on top of the five sub-scores, not before. Also #36
(one run per (profile, source) means two-source duplicates arrive via *separate* runs, which is
exactly the case this issue fixes).
**Blocks:** Nothing in v4; #39 feedback signals are unaffected (signals live on `match`, and
matches collapse to canonical postings before any signal recording matters).

---

## Goal

Dedupe today is `(source, external_id)` on `job_posting`
(`models/job_posting.py:31`, enforced in `_upsert_posting`'s `on_conflict`) — the same job
posted on Adzuna and LinkedIn becomes two rows, two `match` rows for the profile, and two
entries on the dashboard. `rescore_matches()` (`services/matching.py:392`) scores the scoped
corpus row-by-row with no notion of identity beyond the source pair.

The issue scope: group postings on `(normalized_company, normalized_title, location_bucket)`
with pg_trgm title similarity ≥ 0.92, merge the records (source URL list, freshest
`posted_at`, richest description), and collapse matches to the canonical posting — model
first, then one Alembic migration.

## Locked decisions

| Decision | Choice | Rationale |
|---|---|---|
| Schema shape | **Self-FK**: nullable `job_posting.canonical_id UUID REFERENCES job_posting(id)` (indexed, ON DELETE doesn't apply — see downgrade), `NULL` = this row is its own canonical. NOT a `canonical_group` hash column | The issue offers both. A group-hash column needs a canonical row *anyway* (matches must point at a real posting for joins/detail), so the hash would duplicate the FK's job; the self-FK makes "who is the representative" one indexed column and chains detectable in SQL |
| Grouping key | Same `country` (new nullable `String(2)` column on `job_posting`, NULL-safe equality) + normalized company equal + `similarity(title) ≥ posting_dedupe_similarity` (pg_trgm, Settings default 0.92) | The plan-of-record's `location_bucket` is "same metro/country"; a runnable deterministic bucket is the run's resolved 2-letter `country` (already a validated request field). Metro text matching would add a second fuzzy key with no better evidence — postings found by the same run share the country by construction, and re-fetched postings get `country` refreshed on upsert. Company equality (not similarity) is the precision guard that makes title similarity ≥ 0.92 safe |
| Company normalization | Python helper `normalize_company()`: lowercase, strip punctuation/whitespace, drop corporate suffixes (`ltd`, `limited`, `inc`, `llc`, `gmbh`, `bv`, `plc`, `co`, `corp`, `s.a.`, `pty`), test-pinned | Raw company strings differ by suffix/punctuation across sources ("Acme Ltd" vs "Acme, Inc."). Kept minimal and pinned by tests rather than a fuzzy second trigram key — false merges are the expensive failure mode |
| When grouping runs | Incremental, inside `_run_source()` after the upsert loop (before the commit): one new `services/posting_dedupe.py` pass over the just-upserted batch — each new posting is compared against (a) other batch members and (b) existing rows via a per-posting candidate lookup (`title % :title` with `pg_trgm.similarity_threshold` set for the statement, country + normalized-company equality as WHERE guards). NOT a whole-DB reclustering | Plan-of-record: "In ingestion, after normalize." Whole-DB clustering is O(n²) on every run for a benefit that decays (old duplicates collapse opportunistically as sources re-find them). Single-user scale keeps per-posting candidate lookups cheap, and the GIN trgm index keeps them indexed |
| Canonical choice | The **existing** row wins: earliest `fetched_at`, tiebreak lowest `id`. New duplicates get `canonical_id → canonical`; the canonical row is enriched, never re-pointed. Chains are collapsed on write: a candidate that already has `canonical_id` is resolved to its target first (enforced invariant: `canonical_id` only ever points at a row with `canonical_id IS NULL`) | Existing rows already hold matches, search_posting history, and embeddings — pointing at them preserves all three. Deterministic (fetched_at, id) makes the concurrent-runs case (#36 allows Adzuna + LinkedIn runs in parallel) converge to one canonical without coordination: both passes compute the same winner and the loser's write is an idempotent re-point |
| Merge rules (on the canonical) | `posted_at` ← freshest of the pair; `description` ← longest string; `source_urls` ← append `{"source": <dup.source>, "url": <dup.url>}` to a new nullable JSONB column (deduped on source+url); everything else untouched (salary, expiry, embedding, `url`/`source` stay the canonical's own) | Exactly the issue's merge list (URLs, freshest date, richest description). Salary/currency merging invites currency-comparison bugs for zero dashboard value; re-embedding on description change is a silent-cost decision that stays out of scope. `expires_at`/`is_closed` stay the canonical's — the freshness read path (`matching.freshness_condition()`) remains single-source-of-truth |
| Match collapse | `rescore_matches()` keys match rows on the **representative** = `func.coalesce(JobPosting.canonical_id, JobPosting.id)`: the scoring SELECT keeps computing signals per corpus row, Python groups rows by representative keeping the row whose `id == representative`, the upsert writes `(profile, representative)` rows, and one bulk DELETE removes this profile's matches pointing at non-representatives (`job_posting_id IN (SELECT id FROM job_posting WHERE canonical_id IS NOT NULL)`) | Matches must attach to the posting the dashboard joins on; doing it at rescore (which already runs after every search/profile save) means `list_matches`/rerank-pool/filters need zero changes. The Python-side grouping (rather than gnarly `DISTINCT ON` SQL) matches #37's pattern of SQL signals + Python row assembly. Rationales lost with deleted duplicate rows re-derive: the canonical row is rationale-less and enters the rerank pool (same posture as the #37 backfill decision) |
| Existing rows | No data migration / backfill: pre-#38 duplicates stay separate until a source re-finds one of them (then the pass groups them); matches for both keep showing until collapse | Data migrations can't run `rescore`-adjacent Python anyway (standards), and the collapse logic doubles as the backfill the moment any source re-finds a pair. Stated in the guide note so the behavior isn't mistaken for a bug |
| Similarity knob | `posting_dedupe_similarity: Annotated[float, Field(ge=0.0, le=1.0)] = 0.92` in `Settings`; the matching SQL uses the `%` operator with `set_config('pg_trgm.similarity_threshold', …, true)` per statement so a GIN trgm index can serve the lookup | 0.92 straight from the plan-of-record/issue; a Settings knob matches the house pattern (every threshold so far is .env-tunable) and `1.0` (exact title) is the honest "disable" without a second boolean |
| pg_trgm | `CREATE EXTENSION IF NOT EXISTS pg_trgm` in migration `0019` (same pattern as `0001` for vector) + `CREATE INDEX ix_job_posting_title_trgm USING gin (title gin_trgm_ops)` | Issue DoD: extension ensured by the migration, never hand-added. The GIN index is what makes the per-posting candidate lookup indexed rather than sequential |
| API surface | None. No response-model change, no `schema.d.ts` regen: merged URLs stay in `source_urls` (data recorded, not yet surfaced); `JobPostingSummary`/`Detail` untouched | The issue asks for dedupe + merge, not a UI. Surfacing "also on: LinkedIn" on cards/detail is a follow-up once real merge data exists — shipping the API field first would hard-code an unvalidated shape |

## Scope

### Migration (`backend/alembic/versions/0019_add_posting_canonical_dedupe.py`, models first)

1. `CREATE EXTENSION IF NOT EXISTS pg_trgm`.
2. `op.add_column("job_posting", …)` × 3:
   - `canonical_id` — `UUID`, nullable, FK → `job_posting.id` (`use_alter=True` on the model
     so the circular self-reference doesn't order CREATE TABLE wrong), index
     `ix_job_posting_canonical_id`.
   - `source_urls` — `JSONB`, nullable (list of `{source, url}`).
   - `country` — `String(2)`, nullable (no backfill — old rows fill in on re-fetch).
3. `CREATE INDEX ix_job_posting_title_trgm ON job_posting USING gin (title gin_trgm_ops)`.
4. Downgrade: drop the trgm index, the three columns, then `DROP EXTENSION IF EXISTS pg_trgm`.
   Docstring notes the destructive part: dropping `canonical_id` orphans nothing (rows are
   independent again) but discards the merge record (`source_urls`) and re-splits dashboard
   entries — re-derivable by re-running searches.

Migration review checklist (per standards): no enum manipulation, no renames, no data
transformation, FKs indexed.

### Backend (`backend/app/`)

- `models/job_posting.py`: the three new columns (`Mapped[uuid.UUID | None]` self-FK via
  `ForeignKey("job_posting.id", use_alter=True)`, `Mapped[dict[str, object] | None]` JSONB,
  `Mapped[str | None]` country) + the trgm `Index` in `__table_args__`.
- `services/posting_dedupe.py` (new module):
  - `normalize_company(name: str | None) -> str | None` (locked rules; `None` never matches
    anything).
  - `dedupe_postings(session, posting_ids: list[uuid.UUID]) -> int` — resolves chains,
    runs the candidate lookups (`%` operator + similarity threshold + country/company
    guards, excluding self and already-grouped targets), applies canonical choice +
    enrichment updates in bulk, returns the number of grouped duplicates. Logging:
    `ingestion.dedupe new=%d grouped=%d` (never logs posting titles/companies).
- `services/ingestion.py`:
  - `_upsert_posting()` gains `country: str | None` (from the resolved payload — passed
    through `_run_source`), stored on insert **and** refreshed `on_conflict_do_update`
    (re-fetched postings adopt the newer run's country).
  - `_run_source()` calls `dedupe_postings(session, [persisted ids])` after the upsert
    loop, before the commit — so a run's dedupe lands atomically with its postings and the
    matching stage always sees the collapsed state.
- `services/matching.py` (`rescore_matches()` only):
  - representative mapping + Python grouping + bulk delete of duplicate-pointing matches
    (locked decision above); the docstring notes the collapse and the rationale re-derivation.
  - `count_corpus_postings`/`count_out_of_corpus_matches` keep counting raw postings
    (corpus truth) — untouched.
- `core/config.py`: `posting_dedupe_similarity` (default 0.92); `.env.example` gains
  `POSTING_DEDUPE_SIMILARITY=0.92` with a comment.
- Connectors, query rendering, rerank pool ordering, `list_matches`, frontend: untouched.

### Docs

- `docs/guide/03-job-discovery-and-matching.md`: how canonical grouping interacts with the
  `(source, external_id)` dedupe (the unique constraint stays the *first* line of dedupe —
  canonical grouping is the cross-source second line), what merges into the canonical row,
  the opportunistic (no-backfill) rollout, and the threshold knob.
- `docs/architecture.md`: ingestion sequence gains the dedupe pass line; posting-table
  description notes `canonical_id`/`source_urls`/`country`.
- Diagrams: re-render via `node scripts/render-diagrams.mjs` (the search-matching sequence
  diagram text changes — one `dedupe (cross-source canonical grouping)` step).

### Tests (`backend/tests/`, scratch Postgres via `migrated_database` — no SQLite)

- New `test_posting_dedupe.py`:
  - Integration (the issue's DoD case): same job normalized from two source payloads →
    both postings upserted → `dedupe_postings` groups them → one `match` row after
    `rescore_matches`, pointing at the canonical.
  - Merge rules: freshest `posted_at` wins; longest description wins; `source_urls`
    accumulates and dedupes on (source, url); canonical's own `url`/`source`/salary
    untouched.
  - Guards: same title, different company → no group; same company+title, different
    country → no group; similarity below threshold → no group; NULL company or NULL country
    never matches; company-suffix normalization cases (`normalize_company` pinned).
  - Canonical choice: existing row (earlier `fetched_at`) stays canonical; the new
    duplicate re-points to it.
  - Chains: A→B then C arrives resembling A — C points at B (chain resolution), and no row
    ever points at a row that itself has `canonical_id` (invariant asserted).
  - Idempotence: running the pass twice groups nothing new.
  - Convergence: two "concurrent" passes (sequential simulation) over the same pair from
    opposite directions end on one canonical.
- `test_matching.py` (collapse section):
  - duplicate + canonical both in corpus → exactly one match row (the representative's
    signals: canonical's title/description drive the scores);
  - pre-existing match on the duplicate (seeded rationale) is deleted, canonical row
    rationale-less and eligible for the rerank pool;
  - non-duplicate corpus unchanged (no false deletions).
- `test_ingestion.py`: `_run_source` stores/refreshes `country` (insert + on-conflict
  refresh paths); dedupe invoked with the persisted ids (fake-connector run through the
  real `_run_source`).
- `test_migrations.py`: `0019` up (extension present, three columns, GIN index) / downgrade
  (clean removal), following the existing fixture chain pattern.
- Connector / query-rendering tests: excluded — no connector behavior changes.

### Gates

- Backend: `ruff check . && ruff format --check . && pytest` green in `backend/`.
- Frontend: `npm run lint && npm run build` green in `frontend/` (no code change expected;
  gates still run since the milestone branch must stay green).
- Migration `0019` ships in the same change as the `JobPosting` model edit.
- `.env.example` + guide + architecture updated in the same change; diagrams re-rendered.
- `TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/ai_job_assistant_test`
  runs the full suite (pg_trgm exercised for real).

## Risks

| Risk | Mitigation |
|---|---|
| False merge (two genuinely distinct jobs with near-identical titles at similarly-named companies in one country) | Company equality (normalized, suffix-stripped) + 0.92 trigram + same-country guards; threshold is .env-tunable downward if real data shows over-grouping; `source_urls` preserves the duplicate's URL so a wrong merge is auditable from the row |
| Missed merge (title/URL noise across sources defeats the key) | Accepted: dedupe is best-effort grouping, not identity resolution — the dashboard tolerates a residual duplicate; a URL/host-based key is a possible follow-up but LinkedIn/Adzuna share no posting URL scheme |
| Concurrent runs (Adzuna + LinkedIn in parallel, allowed by #36) both detect the same pair | Deterministic (fetched_at, id) winner + idempotent re-point converge; the chain-resolution invariant prevents two-canon cycles; convergence pinned by test |
| Rationale loss when a duplicate match row is deleted | Same posture as #37's backfill: re-derivable by the next rerank (canonical row is rationale-less → pool-eligible); collapse runs before the matching stage of the same run, so the window is one rerank cycle |
| `pg_trgm` unavailable on a managed/self-host Postgres image | Same failure mode as pgvector (already required); extension created in the migration so a missing extension fails loudly at migrate time, not mid-search |
| Similarity lookup without index support (explicit `similarity() >=` is not indexable) | Use the `%` operator with per-statement `set_config('pg_trgm.similarity_threshold', …)` so the GIN trgm index serves the candidate lookup |
| Embedding mismatch after description merge | Accepted + documented: the canonical keeps its original embedding; a stale-but-close vector only affects ranking, and re-finding the posting re-embeds it (next-run refresh path) |

## Out of scope (this issue)

- Whole-DB reclustering / a data-migration backfill of existing duplicate pairs
  (opportunistic collapse on re-find covers it; revisit only if the dashboard still shows
  legacy pairs after real usage).
- Surfacing `source_urls` / "also on" in the API or match cards (data recorded now; UI
  needs real merge data to design against).
- Merging salary/expiry/closed state into the canonical row.
- Re-embedding the canonical after a description merge.
- Cross-profile canonical conflicts (single-user app; grouping is global by construction).
- Fuzzy company matching (trigram on company) — equality only, per the locked guard.
- Feedback signals (Problem 10 / #39) — unaffected by this schema.
