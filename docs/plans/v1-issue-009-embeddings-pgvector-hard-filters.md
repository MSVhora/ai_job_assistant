# Issue #9 — Embeddings + pgvector Storage + Hard Filters

**Status:** Done (2026-09-03)
**Tracks:** GitHub issue #9 (Day 8, Week 2)
**Plan of record:** [v1-implementation-plan.md](v1-implementation-plan.md) §3 (matching engine), §4 (`job_posting.embedding`), §8 Day 8; [UI plan](v1-ui-implementation-plan.md) §6.5 (filters UI lands #10/#11, not here)
**Depends on:** Issues #1–#8 (done). Matching endpoint/table/scores stay in #10.

---

## Carry-over review: what of this issue already exists

Checked the issue's four checkboxes against the code after #8:

| Checkbox | State | Resolution |
|---|---|---|
| Setup check warns if no embedding-capable provider configured | **Already landed in #8** — `services/setup.py` emits `_EMBEDDING_UNABLE` (Anthropic-only embedding model) and `_EMBEDDING_KEY_MISSING`; covered by `tests/test_setup_endpoint.py` | No new work; issue checkbox closes with #8 |
| `vector` column on `job_posting` | Not present (head is migration `0009`; no `Vector` usage in `app/`) | Lands here |
| Batch-embed postings + profile embedding on save | Not present; `adapters/llm.py::embed()` (batch, returns usage) and `pgvector>=0.3` dep already exist | Lands here |
| Hard filters in SQL | Not present | Lands here |

## Goal

Make postings and profiles vector-searchable: a 768-dim `vector` column on `job_posting`
(and `profile`, see decisions), embeddings batch-written during ingestion and refreshed on
every profile content change, and a reusable SQL query that applies hard filters
(location / remote / job type / posted-within) and orders by cosine similarity. #10 builds
the `match` table, `/api/matches`, re-rank and rationale on top of exactly this query.

**Acceptance (issue):** cosine similarity ranking queryable in SQL; embedding dimension
change path documented (new column + backfill).

## Locked decisions (proposed — owner sign-off before build)

| Decision | Choice | Rationale |
|---|---|---|
| Profile embedding storage | **New nullable `profile.embedding vector(768)`** — adds a line to the plan-of-record §4 sketch, which lists embedding only on `job_posting` (flagged for plan-of-record review) | Day 8 says "profile + job descriptions → pgvector"; #10/#11 re-rank repeatedly (filters, priority slider) — re-embedding the profile per query is wasted latency for content that changes rarely |
| Embedding dimension | `Vector(768)` pinned in model **and** migration docstring, matching Gemini `text-embedding-004`; embed wrapper asserts returned dim == 768, mismatch → `LLMError` | Standards: dimension pinned to the embedding model, never silently changed; the guard catches provider/config drift at write time, not at match time |
| Embed text composition | Pure helpers in a new `services/embedding.py`: `profile_embed_text()` from `structured_profile` (target title, skills, seniority, summary, experience titles, location/work-auth prefs) and `job_embed_text()` = title + description. No LLM calls in composition | Deterministic + unit-testable; keeps `adapters/llm.py` as the only LLM boundary |
| Description truncation | Posting description capped at ~6,000 chars before embedding (module constant) | `text-embedding-004` input limit is 2,048 tokens; scrapers can return huge descriptions — truncate, don't fail the batch |
| Batch strategy | One `llm.embed` call per source per run (≤ `results_wanted` = 50 items) — no chunking in v1 | Batch sizes are bounded by the existing cap; usage already logged by the wrapper |
| Re-ingest | Always re-embed on upsert (`on_conflict_do_update` sets `embedding`) | Descriptions can change between runs; an embedding cache is not worth it at ≤100 postings/run |
| Embed failure during ingest | Graceful: postings still persist with `embedding = null`, `SourceOutcome.warning` appended ("embeddings unavailable: …") | Matches the degradation rule — a failed embed must not lose fetched postings; #10 treats null-embedding postings as filter-only (no vector score) |
| Profile embed timing | Inline during `create_profile` / `save_profile` (content change) / gap-fill apply — one vector, sub-second. Failure → profile still saved, embedding null, warning logged | Single-user scale; a background task for one vector is overhead. Gap-fill is listed separately because it mutates `structured_profile` directly, bypassing `save_profile` |
| Hard filters + ranking query | `services/matching.py::ranked_postings_query()` returns a reusable `select(JobPosting)` with: `embedding IS NOT NULL`, optional `location ILIKE '%…%'`, `remote_type = …`, `job_type = …`, `posted_at >= now() - interval`, ordered by `embedding <=> :profile_vec` | Plan-of-record §3 puts filters before re-rank; a query builder (not an endpoint) keeps #10 free to wrap it with the `match` pipeline. No new endpoint in #9 |
| Filter semantics | Location = case-insensitive substring on the free-text `location` column (no geocoding in v1); when `posted_within` is set, postings with null `posted_at` are **excluded** | Substring is honest about scraper location strings; a null `posted_at` can't prove recency, and silently including it defeats "posted within N days" |
| Filters source | New `schemas/matching.py::MatchFilters` (location, remote, job type, posted_within) — typed input for the query builder; endpoint wiring from profile prefs + UI overrides is #10's job | Keeps #9's surface pure-SQL; the schema is shared, not duplicated in #10 |
| No ANN index in v1 | No HNSW/ivfflat index on the vector columns; documented in the migration docstring + guide | Single-user scale (≤ a few thousand postings) — sequential scan is fine; an index needs tuning and only pays off when data grows |
| New dependencies | None — `pgvector` and `litellm` are already in `pyproject.toml` | |

## Scope

### Backend

**Migration `0010_add_embedding_columns`**
- `job_posting` + `embedding vector(768)` nullable; `profile` + `embedding vector(768)` nullable
- Docstring documents: dim pinned to Gemini `text-embedding-004` (768); changing embedding
  models = new column + backfill migration, never a silent dimension change; no ANN index
  in v1 (rationale above). Downgrade drops both columns
- Review the autogenerated file — vector columns won't come out perfect without
  `pgvector.sqlalchemy.Vector` imported

**Models** — `job_posting.py` + `profile.py`: `embedding: Mapped[list[float] | None]`
via `pgvector.sqlalchemy.Vector(768)`

**`app/services/embedding.py`** (new)
- `profile_embed_text(StructuredProfile) -> str`, `job_embed_text(title, description) -> str`
  (pure, incl. truncation constant)
- `embed_postings(postings) -> list[list[float] | None]` — batch via `llm.embed`, dim guard,
  per-item `None` on empty description
- `refresh_profile_embedding(profile) -> bool` — compose + embed + assign; `False` on failure
  (caller logs; never raises into the save path)

**Ingestion — `app/services/ingestion.py`**
- `_run_source`: collect normalized `JobPostingData`, batch-embed once per source, pass
  vectors into `_upsert_posting` (conflict `set_` includes `embedding`); embed failure →
  all-null vectors + warning on the `SourceOutcome` (decision above)

**Profile paths — `app/services/profile_service.py`, `app/services/gap_fill.py`**
- Call `refresh_profile_embedding()` after `structured_profile` changes in
  `create_profile`, `save_profile`, and the gap-fill apply block

**Matching query — `app/services/matching.py` + `app/schemas/matching.py` (new)**
- `MatchFilters` pydantic model (location, remote, job type, posted_within days)
- `ranked_postings_query(profile_embedding, filters)` per the decision row

### Tests

- `tests/fakes.py`: `install_aembedding(monkeypatch, …)` mirroring `install_acompletion`;
  fake vectors are programmatically generated 768-dim (known relative distances)
- `tests/test_embedding.py` — text composition (profile fields, truncation cap), dim-guard
  raises `LLMError` on wrong-dim response, batch call shape
- `tests/test_ingestion.py` extended — postings persisted with embeddings; embed failure →
  null embeddings + warning present, run still `succeeded`; re-ingest updates embedding
- Profile tests extended — create/save/gap-fill refresh the embedding; embed failure leaves
  profile saved with null embedding
- `tests/test_matching_filters.py` (DB, `clean_tables`) — each filter alone + combined;
  null-embedding exclusion; cosine ordering (fixtures with known distances); null
  `posted_at` excluded under `posted_within`
- Migration up/down exercised by the existing `migrated_database` fixture

### Doc impact

- `docs/plans/v1-implementation-plan.md`: §4 sketch gains `profile.embedding` (amendment
  flagged here for owner acceptance); §8 Day 8 stays as-is
- `docs/architecture.md`: ER annotations — "lands with issue #9" notes become landed
  state; profile entity gains the embedding attribute → re-render diagrams
  (`node scripts/render-diagrams.mjs`)
- `docs/guide/03-job-discovery-and-matching.md`: embeddings + hard-filter sections marked
  live; document the dimension-change path (new column + backfill), the no-ANN-index note,
  and the description truncation cap
- No API surface change → no `schema.d.ts` regeneration, no frontend work, `.env.example`
  unchanged (`embedding_model` already documented)

## Definition of done

- `ruff check . && ruff format --check . && pytest` green in `backend/`
- Migration `0010` generated, reviewed, applied; up/down verified
- Live check: one `/jobs` search populates `job_posting.embedding`; a psql query with
  `<=>` against the profile vector returns distance-ordered rows under filters
- Dimension-change path + truncation + no-index decisions documented
- Docs updated; diagrams re-rendered

## Out of scope (this issue)

`match` table + `vector_score`/`final_score` + `/api/matches` (#10 — keyed on `profile_id`
per owner decision 2026-09-02, recorded in plan-of-record §4), LLM re-rank +
rationale (#10), priority weighting (#11), filters UI (lands #10/#11 per UI plan §6.5),
ANN/HNSW index, embedding backfill tooling for model changes, LLM cost-estimation module,
disabling/enabling sources, posting detail endpoint.
