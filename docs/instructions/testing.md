# Testing Standards

Applies to `backend/tests/` and the colocated frontend tests.

> **Target state.** The mirrored backend layout and coverage gate *(v5 #41, #42)* are brought into the
> code by the [v5 plans](../plans/v5/v5-hardening-plan.md); today `backend/tests/` is flat.

## Principles

- A change is not done until its tests exist and the gate passes (see `AGENTS.md`, definition of done).
- Every bug fix lands with a test that fails without the fix.
- Tests are deterministic and offline by default: **no live network, no live LLM, no real provider keys** in the default run. Provider behaviour is covered with fixtures and fakes; anything that needs a real provider is opt-in and clearly marked.
- Test the behaviour and the contract (status codes, response shape, DB state), not private helpers.

## Backend (pytest)

- **Layout** *(v5 #42)*: tests mirror `app/` — `tests/adapters/`, `tests/services/`, `tests/routers/`, `tests/core/`, `tests/schemas/`, `tests/scripts/`, `tests/db/` (migrations). A module `app/services/matching.py` is tested by `tests/services/test_matching.py`. Shared `conftest.py`, `fakes.py` and `fixtures/` stay at the `tests/` root. Test basenames stay unique.
- **Database tests** run against a scratch Postgres with migrations applied — never SQLite (it hides pgvector, JSONB, partial-index and trigger behaviour). The suite needs `TEST_DATABASE_URL` pointing at a **disposable** database; it migrates up at session start and downgrades at the end, so it must never be your dev database. Without the variable DB tests skip.
- **Routes** are tested with `httpx.AsyncClient` against the app. Note that Starlette's `TestClient` drains `BackgroundTasks` before returning, so tests that need to observe a run in flight pre-seed the row instead.
- **Fakes and fixtures**: provider and connector behaviour comes from `tests/fakes.py` and recorded payloads in `tests/fixtures/` (for example `adzuna_search_response.json`, `linkedin_dataset.json`). Use `httpx.MockTransport` for HTTP connectors. Fixture data is synthetic — no real resumes or personal data.
- **Must cover**: schema validation failures, dedupe logic, connector mapper correctness with fixture payloads, error paths and graceful degradation, ownership checks (404 on mismatch), and **migration up/down**.
- **Concurrency**: invariants that rely on the database (run guards, unique indexes) get a test that races two sessions and asserts the index, not the application check, is what stops the loser (see `test_duplicate_run_concurrency.py`).
- **Async**: `asyncio_mode = "auto"`; do not create module-level asyncio primitives (semaphores, locks) that bind to one event loop.
- **Coverage** *(v5 #41)*: `pytest --cov=app` with a fail-under threshold that is only raised.
- **Naming**: `test_<unit>_<behaviour>`; one behaviour per test; arrange/act/assert visible.

## Frontend (vitest + Testing Library)

- Tests are co-located with the code (`Component.test.tsx`, `module.test.ts`) and run with `npm test`.
- Query by role, label and visible text; assert on what the user sees. No testing of implementation details or snapshots of large trees.
- Mock at the `lib/api` boundary, never `fetch` inside components (components do not call `fetch`).
- Pure logic (zod schemas, formatters, search-form schemas) gets plain unit tests.
- Accessibility regressions (labels, focus, `aria-live`) are tested where they were fixed.

## Flaky tests

A flaky test is a bug: fix or delete it the same day. Do not add retries or sleeps to hide it.
