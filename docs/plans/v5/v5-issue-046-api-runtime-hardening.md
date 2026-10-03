# Issue #46 — API and runtime hardening: CORS, timeouts, list limits, logging and error-contract audits

**Status:** Proposed — for owner review
**Tracks:** GitHub issue #46 (milestone `v5`, branch `v5/46-api-runtime-hardening`)
**Plan of record:** [v5 plan](v5-hardening-plan.md) · standards: [backend-fastapi.md](../../instructions/backend-fastapi.md) (*v5 #46* rules), [api-design.md](../../instructions/api-design.md), [security-privacy.md](../../instructions/security-privacy.md)
**Depends on:** #41 (strict tooling) · **Blocks:** nothing hard (v6 builds on it)

## Goal

Make the runtime rules in the standards true and keep them true with tests: explicit CORS, explicit timeouts on every outbound call, bounded list endpoints, no sensitive data in logs, and one error contract.

## Evidence and findings

| Standard | Finding |
|---|---|
| CORS explicit methods/headers | `main.py`: `allow_methods=["*"]`, `allow_headers=["*"]`, `allow_credentials=True` with configured origins |
| Timeouts on every outbound call | Connectors (`adzuna.py`, `apify.py`) set `httpx.AsyncClient(timeout=_TIMEOUT_S)`; **LLM and embedding calls in `adapters/llm.py` pass no timeout** to LiteLLM |
| List endpoints bounded | `GET /api/matches` has `limit` (1–200) and `offset` + `X-Total-Count`; `GET /api/jobs/searches` is capped by a hard-coded `.limit(20)` in `ingestion.list_profile_searches` (not configurable); `GET /api/profiles`, `GET /api/resumes` and `GET /api/jobs/searches/{id}/postings` have no limit |
| No resume text/keys/prompts in logs; config only via `Settings` | Quick scan found none (no `os.getenv`/`os.environ` in `app/`; warning logs carry exception text and ids) — make it a test |
| One error contract | Domain errors use `{"detail", ...}` via `core/errors.py`; consistency across all routers not asserted |

## Locked decisions

| Decision | Choice | Rationale |
|---|---|---|
| CORS | `allow_methods=["GET","POST","PATCH","DELETE","OPTIONS"]`, `allow_headers=["Content-Type","Accept"]`, origins from `CORS_ORIGINS`, `expose_headers=["X-Total-Count"]` (replacing the manual header in the matches route) | Least privilege; same behaviour for the shipped UI |
| LLM timeout | New setting `LLM_TIMEOUT_S` (default 60) passed to every LiteLLM call; timeouts surface as the existing "request timed out" message and are retried by the shared policy | Standard requires explicit timeouts |
| List limits | Add `limit` (default 100, max 200) and `offset` to the unbounded list endpoints, keep default behaviour for current clients; add `X-Total-Count` where the UI could page | Backward compatible, bounded |
| Logging guard | A test that runs upload → extract → search with fakes under `caplog` and asserts no log record contains resume text, prompt text, or key-shaped strings | Turns the rule into a regression test |
| `os.getenv` guard | Enforced by the ruff `banned-api` rule added in #41 (plus a test that fails if it is removed) | Mechanical |
| Error-contract test | A parametrized test enumerates every `DomainError` subclass and asserts `{"detail": str}` and the declared `status_code` through the registered handler | Catches drift automatically |

## Scope

- `app/main.py` CORS block; matches route uses `expose_headers` instead of setting the header by hand.
- `core/config.py`: `llm_timeout_s`; `adapters/llm.py`: pass `timeout=` to `acompletion`/`aembedding`.
- List endpoints in `routers/profile.py`, `routers/resume.py`, `routers/jobs.py` + schemas for `limit`/`offset` (turn the fixed `20` of the recent-runs list into a validated `limit` with the same default); frontend `lib/api` functions keep working with defaults (no UI change unless a list would exceed the default).
- Tests in `tests/routers/`, `tests/adapters/`, `tests/core/`.
- `.env.example`: `LLM_TIMEOUT_S`.

## Tests

- CORS: preflight from an allowed origin succeeds; from another origin it is rejected; disallowed method/header rejected; `X-Total-Count` is exposed.
- LLM timeout: a fake slow provider triggers the timeout path and the retry policy.
- List limits: default, max, over-max (422), `offset` paging, total header.
- Logging guard and error-contract tests as above.

## Gates

`ruff check . && ruff format --check . && pyright && pytest --cov=app`.

## Doc impact

`docs/architecture.md` (privacy posture: CORS, timeouts; error contract paragraph); `docs/guide/01-getting-started.md` troubleshooting (CORS wording confirmed against the final behaviour); `docs/guide/03-job-discovery-and-matching.md` if list endpoints gain visible `limit`/`offset`; `docs/instructions/{backend-fastapi,api-design,security-privacy}.md` (remove *(v5 #46)* markers); `.env.example`.

## Risks

| Risk | Mitigation |
|---|---|
| Tightened CORS breaks the UI | Preflight test with the exact methods/headers the frontend sends; manual smoke |
| New default limits truncate a list a page assumed complete | Defaults chosen above current data sizes; frontend checked for each list consumer |

## Out of scope

Authentication, rate limiting, pagination UI, structured JSON logging.
