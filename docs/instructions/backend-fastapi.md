# FastAPI Backend Standards

Applies to everything under `backend/`.

## Structure & responsibilities

- `routers/` — HTTP layer only: parse input, call a service, return a response model. No business logic, no SQL, no LLM calls.
- `services/` — business logic. Raise domain errors; no `Request`/`Response` objects here.
- `models/` — SQLAlchemy ORM models. Schema source of truth.
- `schemas/` — pydantic v2 request/response models, one module per domain area.
- `adapters/` — `llm.py` (LiteLLM wrapper: generate, parseStructured, embed, estimateCost) and job-source connectors.
- `core/config.py` — pydantic-settings `Settings`; the only place that reads env vars.
- `deps.py` — shared dependencies (DB session, settings, current profile).

## Rules

- **Response models everywhere**: every route declares `response_model`. Never return ORM objects or raw dicts.
- **Async all the way**: `async def` routes, SQLAlchemy 2.0 async engine + `asyncpg`. No blocking calls (requests, file IO, time.sleep) inside async routes — use async libs or `BackgroundTasks`.
- **DB session via dependency**: one `AsyncSession` per request from `deps.py`; the
  `DbCommitMiddleware` commits on `http.response.start` (a yield-dependency teardown runs
  **after** the response is sent, so teardown commits race the client) and rolls back on
  unhandled errors. Services receive the session; never create engines/sessions ad hoc and
  never call `session.commit()` in services.
- **Status codes**: 400 validation beyond pydantic's 422, 401 unauthenticated, 404 missing, 409 conflict/duplicate, 422 malformed input. Register central exception handlers for domain errors; no bare `except:` and no silent exception swallowing — log and re-raise or convert.
- **Config**: only through `Settings` (`.env` backed). No `os.getenv` scattered in code. Required keys fail fast at startup.
- **LLM calls**: only via `adapters/llm.py`, which must return token usage and route through cost estimation before any batch operation. Structured extraction must validate against a pydantic schema and retry/repair once on failure before erroring.
- **Job sources**: only via the `JobSource` protocol. A failing source degrades gracefully (skip + warn), never fails the whole search.
- **Long-running work** (ingestion runs, batch scoring, embeddings): `BackgroundTasks` with status queryable from the DB — never a synchronous request that hangs.
- **Logging**: stdlib logging with structured extras; log operation + duration + token counts for LLM calls. Never log resume content, API keys, or full prompts.
- **Security**: file uploads size- and type-checked; paths built with `uuid` names, never user-supplied filenames; CORS locked to the frontend origin in prod.

## Testing (pytest)

- Tests mirror `app/` layout (`tests/services/test_matching.py`, …).
- Routes tested via `httpx.AsyncClient` against the app; DB tests run against a scratch Postgres (docker) with migrations applied — never SQLite, it hides pgvector/JSONB issues.
- Cover: schema validation failures, dedupe logic, connector mapper correctness with fixture payloads, migration up/down.

## Conventions

- Python 3.12 type hints; `ruff` for lint + format; no `Any` without justification.
- Endpoints prefixed `/api`; plural nouns (`/api/jobs`, `/api/matches`); kebab or snake consistent — snake_case in JSON keys to match pydantic defaults.
- One migration per PR alongside its model change (see database standards).
