# Issue #42 — Mirror `app/` in `backend/tests/`

**Status:** Proposed — for owner review
**Tracks:** GitHub issue #42 (milestone `v5`, branch `v5/42-backend-test-layout`)
**Plan of record:** [v5 plan](v5-hardening-plan.md) · standards: [testing.md](../../instructions/testing.md), [backend-fastapi.md](../../instructions/backend-fastapi.md)
**Depends on:** #40 (so its new test moves with the rest) · **Blocks:** #43, #41 (smaller, readable diffs), all v6 tests

## Goal

The standard says tests mirror the application layout. Today `backend/tests/` is 40 flat files. Move them into folders that match `app/` so a test is found where its module lives, with **zero behaviour change**.

## Locked decisions

| Decision | Choice | Rationale |
|---|---|---|
| Layout | `tests/adapters/`, `tests/services/`, `tests/routers/`, `tests/core/`, `tests/schemas/`, `tests/scripts/`, `tests/db/` (migrations) | Mirrors `app/{adapters,services,routers,core,schemas}` plus `scripts/` and migrations |
| Shared files | `conftest.py`, `fakes.py`, `fixtures/` stay at `tests/` root | Imported by everything; `pythonpath = [".", "tests"]` already resolves `fakes` |
| Method | `git mv` only (history preserved); no edits except import/relative-path fixes | Reviewable as a pure move |
| Basenames | Stay unique across folders | Avoids pytest module-name collisions without adding `__init__.py` everywhere |
| Classification rule | A test belongs to the layer of the code it exercises: imports `TestClient`/routes → `routers`; imports a connector/`llm`/`retry` → `adapters`; DB or business logic → `services`; pydantic models only → `schemas`; `middleware`/`config`/`errors` → `core` | Deterministic, applied by reading each file's imports |

## Proposed mapping (confirm each by its imports while moving)

- **adapters:** `test_adzuna_adapter`, `test_apify_adapter`, `test_llm_embed_retry`, `test_llm_generate_retry`, `test_llm_parse_structured`, `test_retry`, `test_source_filters`, `test_source_registry`
- **core:** `test_db_commit_middleware`, `test_env_example` (from #40)
- **db:** `test_migrations`
- **routers:** `test_health`, `test_job_endpoints`, `test_matches_endpoint`, `test_profile_endpoints`, `test_setup_endpoint`, `test_resume_upload`
- **schemas:** `test_profile_schema`, `test_matching_schema`
- **scripts:** `test_seed_demo`
- **services:** `test_embedding`, `test_gap_fill`, `test_ingestion`, `test_duplicate_run_concurrency`, `test_matching`, `test_matching_filters`, `test_posting_dedupe`, `test_profile_derivation`, `test_profile_diff`, `test_profile_extraction`, `test_query_builder`, `test_query_rendering`, `test_query_tuner`, `test_resume_list`, `test_text_extraction`
- **decide on read:** `test_link_labeling`

## Scope

- `git mv` the files; fix any path assumptions (fixture file paths via `Path(__file__)`, `BACKEND_DIR` use in `conftest.py`).
- No changes to `pyproject.toml` `[tool.pytest.ini_options]` beyond what the move needs.

## Verification

1. Before: `pytest --collect-only -q | tail -1` → record the test count.
2. After the move: identical count; same node ids except the path prefix.
3. Full suite on a scratch Postgres: `TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/ai_job_assistant_test pytest` green (never the dev database).
4. Run one folder (`pytest tests/services`) and one file to confirm selective runs work.

## Gates

`ruff check . && ruff format --check . && pytest`.

## Doc impact

`README.md` test section (selective-run examples with the new paths); `docs/instructions/testing.md` (already states the target layout — remove the "target state" note); `AGENTS.md` commands table if it mentions test paths.

## Risks

| Risk | Mitigation |
|---|---|
| A test relies on its own directory (fixture paths) | Count + full-suite comparison; fix paths in the same commit |
| Merge conflicts with in-flight branches | Do it first and merge quickly; v6 plans are docs-only until then |

## Out of scope

Rewriting or deduplicating tests, adding coverage (#41), changing fixtures.
