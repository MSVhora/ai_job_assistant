# FastAPI Backend Standards

Applies to everything under `backend/`.

> **Target state.** Rules marked *(H1)*, *(H6)* or *(H7)* describe tooling or behaviour that the
> [hardening plans](../plans/hardening/README.md) bring the code up to. Until each lands, the code
> may not yet comply; the plan for each gap exists and nothing here is aspirational filler.

## Structure & responsibilities

- `routers/` — HTTP layer only: parse input, call a service, return a response model. No business logic, no SQL, no LLM calls.
- `services/` — business logic. Raise domain errors; no `Request`/`Response` objects here.
- `models/` — SQLAlchemy ORM models. Schema source of truth.
- `schemas/` — pydantic v2 request/response models, one module per domain area.
- `adapters/` — `llm.py` (LiteLLM wrapper: `generate`, `parse_structured`, `embed`, and `estimate_cost` *(H7)*) and job-source connectors.
- `core/config.py` — pydantic-settings `Settings`; the only place that reads env vars.
- `core/errors.py` — domain error classes and the central exception handlers.
- `deps.py` — shared FastAPI dependencies (`get_db` provides the request's `AsyncSession`; settings come from `get_settings()`).

## Rules

- **Response models everywhere**: every route declares `response_model` (redirect/204 routes are the only exceptions). Never return ORM objects or raw dicts.
- **Async all the way**: `async def` routes, SQLAlchemy 2.0 async engine + `asyncpg`. No blocking calls (requests, file IO, time.sleep) inside async routes — use async libs, `asyncio.to_thread`, or `BackgroundTasks`.
- **DB session via dependency**: one `AsyncSession` per request from `deps.py`; the
  `DbCommitMiddleware` commits on `http.response.start` (a yield-dependency teardown runs
  **after** the response is sent, so teardown commits race the client) and rolls back on
  unhandled errors. Services receive the session; never create engines/sessions ad hoc and
  never call `session.commit()` in request-path services.
  - **Background-task exception:** `BackgroundTasks` outlive the request, so they open a fresh
    session from `session_factory` and commit explicitly (as `ingestion.py`, `match_rebuild.py`
    and `profile_service._refresh_queries_background` do). Commit only at meaningful boundaries
    (status changes, finished batches) and always inside `async with session_factory()`.
- **Status codes**: 400 validation beyond pydantic's 422, 404 missing (also for resources the caller does not own), 409 conflict/duplicate, 422 malformed input. 401/403 are not used while the app is single-user with no auth; introduce them together with auth. Register central exception handlers for domain errors; no bare `except:` and no silent exception swallowing — log and re-raise or convert.
- **Error contract**: error bodies are `{"detail": "<human message>"}`, optionally with extra machine keys (for example `active_search_id` on the duplicate-run 409). Domain errors subclass `DomainError` in `core/errors.py` and carry `status_code` + `default_detail`; routers never build error JSON by hand.
- **Config**: only through `Settings` (`.env` backed). No `os.getenv`/`os.environ` in application code. Invalid settings fail fast at startup (bounds, weight sums). Provider keys (Gemini, Adzuna, Apify) are optional at startup by design — a missing key is reported by `/api/health` and `/api/setup/check` so the Setup page can guide the user.
- **LLM calls**: only via `adapters/llm.py`, which returns token usage and logs it; user-triggered batch LLM actions are confirm-gated and show an estimated cost before they run *(H7)*. Structured extraction must validate against a pydantic schema and retry/repair once on failure before erroring.
- **Job sources**: only via the `JobSource` protocol. A failing source degrades gracefully (skip + warn), never fails the whole search.
- **Long-running work** (ingestion runs, batch scoring, embeddings): `BackgroundTasks` with status queryable from the DB — never a synchronous request that hangs. A run guard (partial unique index) prevents duplicate concurrent runs and a sweeper reclaims stuck runs.
- **Outbound HTTP** *(H6)*: every client call has an explicit timeout and goes through the shared retry policy (`adapters/retry.py`).
- **List endpoints** *(H6)*: bounded by a `limit` (with a documented maximum) and, where unbounded growth is possible, `offset`; the total is exposed via `X-Total-Count` where the UI paginates.
- **Logging**: stdlib logging with `key=value` messages (operation, duration, token counts for LLM calls). Never log resume content, API keys, tokens, or full prompts.
- **Security**: file uploads size- and type-checked (magic bytes); paths built with `uuid` names, never user-supplied filenames; CORS restricted to configured origins with explicit methods and headers *(H6)* — never `*` together with credentials in production.

## Tooling (target gates)

- **Ruff** *(H1)*: `select = ["ALL"]` with a short, documented ignore list in `pyproject.toml` (docstring rules, rules that conflict with the formatter). Tests get per-file ignores (`S101`, `ANN`, `PLR2004`). `ruff format` is the formatter.
- **Types** *(H1)*: pyright in `strict` mode on `app/`. No `Any` without a justified `# pyright: ignore[...]`/`ANN401` waiver.
- **Coverage** *(H1)*: `pytest --cov=app` with a fail-under threshold set from the measured baseline and only ever raised.
- **Supply chain** *(H1)*: dependencies locked; `pip-audit` clean (or each waiver documented).
- **Hooks** *(H1)*: `pre-commit` runs ruff, pyright, secret scanning (gitleaks) and a large-file check.
- Gate command: `ruff check . && ruff format --check . && pyright && pytest --cov=app` (in `backend/`).

## Testing (pytest)

See [testing.md](testing.md). In short: tests mirror the `app/` layout, DB tests run against a scratch Postgres with migrations applied (never SQLite — it hides pgvector/JSONB issues), no live network or LLM in the default run.

## Conventions

- Python 3.12 type hints everywhere; no `Any` without justification.
- Endpoints prefixed `/api`; plural nouns (`/api/jobs`, `/api/matches`); snake_case in JSON keys to match pydantic defaults. See [api-design.md](api-design.md).
- One migration per PR alongside its model change (see [database-postgres.md](database-postgres.md)).
