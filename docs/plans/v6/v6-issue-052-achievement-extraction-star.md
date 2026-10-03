# Issue #52 — STAR achievement extraction: models, extraction service, confirm-gated runs (Week 2)

**Status:** In progress — branch `v6/52-achievement-extraction-star`
**Tracks:** GitHub issue #52 (milestone `v6`, branch `v6/52-achievement-extraction-star`)
**Plan of record:** [v6-implementation-plan.md](v6-implementation-plan.md) §5, §8 (cost), §9 (migration `0025`)
**Depends on:** #49 (task routing, cache, meter), #51 (chunks)
**Blocks:** #53 (review), #55, #58

---

## Goal

Distil chunks into **draft** STAR achievements with skills/impact/difficulty tags and mandatory evidence links, using the cheap model, hash-cached and cost-estimated before the user confirms the run. Drafts are never visible downstream until approved (#53).

### Plan-of-record drift (flagged)

| Plan says | This issue does | Why |
|---|---|---|
| 14 new tables; embedding only when approved | **15 tables**: adds `achievement_extraction_run` (progress, estimate, usage, guard). Drafts **are embedded** at creation | An extraction run needs the same guard/progress/resume treatment as sync (hard req. 4 spirit), and #53 merge proposals need draft embeddings. Retrieval still filters `status='approved'`, so downstream behaviour is unchanged. Plan §9 and §8 get updated when this merges. |
| — | `achievement.evidence_stale_at timestamptz NULL` added | #53 needs to flag an approved achievement whose evidence changed after a refresh |

## Locked decisions

| Decision | Choice | Rationale |
|---|---|---|
| Model | `LLMTask.extract` (cheap model) | Plan §8 |
| Unit of work | One chunk per call, 0–3 achievements out | Small schemas (Gemini large-schema looping risk) |
| Skipping unchanged work | Skip when `chunk.content_hash == chunk.extracted_hash` **and** `ACHIEVEMENT_PROMPT_VERSION` unchanged; plus `llm_output_cache` hit | A refresh only re-extracts changed chunks |
| Output fields | Plan §5.1 `ExtractedAchievement` | — |
| Hard validators (post-parse, not prompt-only) | (1) `evidence_ids ⊆ chunk's item ids`, non-empty; (2) every metric number appears verbatim in a cited item body (else the metric moves to `needs_confirmation`, never kept as evidence-verified); (3) `result` is null unless some cited text states an outcome (checked by the model's own `result_quote`, which must be a substring of the evidence); (4) text containing redaction placeholders → draft flagged | Hard requirement 1 enforced in code |
| Skill canonicalization | `resources/skill_aliases.yaml` (lowercase, alias → canonical) + match against `structured_profile.skills` across the candidate's profiles | Consistent tags for retrieval and keyword overlap |
| Difficulty | 1–5 against a written rubric embedded in the prompt (1 routine fix … 5 architectural / cross-team) | Reproducible |
| Employer suggestion | For repo-based chunks: suggest `employer_ref` by overlap of chunk dates with `structured_profile.experience` ranges across profiles; stored as `employer_ref` with `employer_ref_source='suggested'` inside the JSON until confirmed in #53 | Plan §5.3 |
| Run guard | Partial unique index on `achievement_extraction_run (candidate_id) WHERE status IN ('pending','running')`; sweeper with `max_run_age_minutes`; 409 with `active_run_id` | Same pattern as #36/#50 |
| Confirm gate | `POST …/extract/estimate` returns chunk count (new vs cached), tokens, cost from v5 #47's `estimate_structured_cost` on the real chunk prompts and `estimate_cost` for embeddings (`usd` null + "cost unavailable for this model" when unpriced), and a private-data breakdown; `POST …/extract` requires `confirmed_estimate_id` | User sees what leaves the machine and what it costs |
| `derived_from_private` | Set from linked items at creation | Provenance marking |

## Scope

### Migration (`0025_add_achievements.py`, models first)

Tables `achievement`, `achievement_evidence` (unique `(achievement_id, item_id)`, `role`, `quote`), `achievement_revision` (FK `RESTRICT`), `achievement_extraction_run` + the active-run partial unique index; enums `achievement_status`, `achievement_origin`, `achievement_revision_source`; `CHECK difficulty BETWEEN 1 AND 5`; `evidence_stale_at`; indexes `(candidate_id, status)`. No existing table or enum touched (deliberately avoids altering `profile_revision_source`).

### Backend (`backend/app/`)

- `models/achievement.py` (+ exports), `schemas/achievement.py` (`ExtractedAchievement`, `MetricClaim`, `AchievementResponse`, run/estimate schemas).
- `services/achievement_extraction.py`: `estimate(candidate_id)`, `start_extraction(confirmed_estimate_id)`, background `run_extraction(run_id)` (fresh sessions, explicit commits, per-chunk failure isolation, progress and usage on the run row), `extract_chunk(chunk)` using `cached_parse_structured`; validators above in `services/achievement_validation.py` (pure).
- `services/skill_canon.py` + `resources/skill_aliases.yaml`.
- Prompt module `services/prompts/achievement.py` with `ACHIEVEMENT_PROMPT_VERSION`; evidence fenced in delimited blocks with an instruction to treat it as data, not instructions (prompt-injection hygiene, plan §12).
- Draft embedding via `embedding.embed_texts` on `title + STAR + skills`.
- `routers/achievements.py` (this issue only): `POST /api/evidence/extract/estimate`, `POST /api/evidence/extract`, `GET /api/evidence/extract/runs/{id}`, `GET /api/achievements?status=` (list; edit/approve arrives in #53).

### Tests

- `tests/services/test_achievement_validation.py` (pure): evidence ids outside the chunk rejected; fabricated number → moved to `needs_confirmation`; `result` without a supporting quote → null; placeholder flag; empty evidence rejected.
- `tests/services/test_achievement_extraction.py` (Postgres, the provider-boundary fakes `install_acompletion`/`install_aembedding` in `tests/fakes.py` (the #60 recorder builds on them)): trap chunk with no metric yields `metrics == []` and `result is None`; run twice → second run makes **zero** provider calls; changing `ACHIEVEMENT_PROMPT_VERSION` re-runs; one chunk raising `LLMError` does not fail the run; estimate within ±25 % of actual metered tokens on the fixtures; private share reported; `derived_from_private` set.
- `tests/services/test_extraction_run_guard.py`: concurrent starts → one 409 with `active_run_id`; sweeper releases a stale run.
- `tests/services/test_skill_canon.py`: aliases, case, profile-skill matching.
- `tests/db/test_migrations.py` (+ `tests/db/test_schema_standards.py` picks the new tables up): `0025` round trip.

### Standards from v5 (must hold from the first commit)

- **Lint/types:** ruff `ALL` and pyright strict pass with no new `noqa`; untyped third-party values are narrowed through small typed helpers (the pattern in `adapters/llm.py`); a `# pyright: ignore` needs a reason comment. Functions stay within the configured limits (args 6, branches 13, returns 8, complexity 14).
- **Coverage and layout:** the 90 % floor holds with `TEST_DATABASE_URL` set; new code ships with its tests in the mirrored folders (`tests/adapters/`, `tests/services/`, `tests/routers/`, `tests/db/`, `tests/core/`; recorded/golden suites in `tests/eval/`).
- **Config:** every new `Settings` field appears in `.env.example` (the settings↔env guard test fails otherwise); no `os.getenv`/`os.environ` and no provider SDK imports outside their one module.
- **API:** new routes keep `response_model` (binary downloads declare their media type instead), use only the CORS-allowed methods (`GET`, `POST`, `PATCH`, `DELETE`, `OPTIONS` — **never PUT**) and headers (`Content-Type`, `Accept`), raise `DomainError` subclasses (checked by `tests/core/test_error_contract.py`), and bound every list with the shared `pagination()` dependency and `X-Total-Count`.
- **Privacy:** no resume/evidence text, prompts, tokens or keys in logs (extend `tests/routers/test_logging_privacy.py` for the new flows); LLM calls log `cost_usd=`; outbound HTTP has an explicit timeout.
- **Schema (v5 #43 conventions):** every table with `updated_at` gets `create_updated_at_trigger(table)` / `drop_updated_at_trigger(table)` from `app.core.migration_helpers`; every FK is indexed and declares its ON DELETE (CASCADE owned children, RESTRICT identity/audit, SET NULL provenance); constraints and indexes are named (`uq_`/`ix_`/`fk_`/`ck_`); bounded scalars get a `CHECK`; `alembic check` is clean and the schema audit (`tests/db/test_schema_standards.py`) reports nothing; downgrade works. Revision numbers continue from `0024` (this issue adds `0025`).

### Gates / docs

the backend gate (`ruff check . && ruff format --check . && pyright && pytest --cov=app` with a scratch `TEST_DATABASE_URL`) and `pre-commit run --all-files`; `.env.example` unchanged (settings from #49); `architecture.md` ER (achievement tables, run table) and a new ingest→extract sequence diagram, re-render diagrams; guide 04 gains "Extraction and cost estimate".

## Risks

| Risk | Mitigation |
|---|---|
| Thin commit text produces vague achievements | PR-first chunking (#51), "result = null" rule, review ranking in #53, "add a note" prompts |
| Model ignores the "no invented metrics" rule | Enforced after parsing, not only in the prompt; golden trap cases in CI |
| Prompt injection inside PR descriptions | Delimited evidence + schema validation + evidence-id subset check; no tools |
| Free-tier throughput makes first run slow | Concurrency cap, per-chunk isolation, resumable (re-start skips completed chunks via hashes) |

## Out of scope

Approve/edit/merge UI (#53), LLM-based merge proposals (v7), resume/agent use, cross-achievement summarization.

## Implementation notes (deviations from the plan above)

- **Stateless confirm gate:** there is no estimates table. `estimate_id` is a SHA-256 over the chunks to process (`id`, `content_hash`, `extracted_hash`), the prompt version and the routed extract model; `POST /extract` recomputes it and answers 409 on a mismatch.
- **Evidence labels:** chunk text carries no per-item ids, so the prompt adds a labelled item list (`E1: [commit] title (date)`, redacted) and the model cites labels. Metric numbers, metric quotes and result quotes are validated against the **chunk text the model saw** (redacted), not the original item bodies.
- **`extracted_hash`** stores `digest(content_hash, ACHIEVEMENT_PROMPT_VERSION)`, so a content change or a prompt bump re-extracts. A chunk that already has drafts at the current prompt version is skipped without a call; drafts from an older prompt version are archived (revision `status_change`) when the new extraction succeeds. Approved rows are never touched.
- **Schema:** the run table reuses the `sync_status` enum (three new enums only: `achievement_status`, `achievement_origin`, `achievement_revision_source`; the Python member for `split` is `split_` because `split` shadows `str.split`, with `values_callable` keeping the DB label `split`). Added `review_flags` JSONB; metric `verified` is `evidence | user | needs_confirmation`.
- **Stale reconciliation** (only after a run with no failed chunk): drafts whose source chunk hash no longer exists are archived, approved ones get `evidence_stale_at`.
- **Estimate accuracy:** prompt tokens are priced from the real prompts (checked within ±25 % of metered tokens in tests); completion tokens are a conservative per-chunk ceiling (450), so the estimate is an upper bound. Embedding cost assumes 200 tokens per pending chunk.
- **Employer:** a repo scope's own `employer_ref` wins (`source: scope`); otherwise the best date-overlap experience across the candidate's profiles (`source: suggested`). Resume, note and link chunks get none.
- **Tests:** `clean_tables` now also truncates `llm_output_cache` (content-addressed rows otherwise leak between tests). No live LLM is exercised; quality is judged in #60.
