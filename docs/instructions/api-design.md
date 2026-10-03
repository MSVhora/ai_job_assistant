# API Design Standards

Applies to every HTTP endpoint in `backend/app/routers/`.

## Shape

- Prefix `/api`; plural nouns for collections (`/api/profiles`, `/api/matches`); sub-resources nest (`/api/profiles/{id}/gap-fill`); actions that are not CRUD are `POST` on a verb sub-path (`/api/jobs/search`, `/api/profiles/{id}/tune-queries`).
- JSON keys are `snake_case` (pydantic defaults). Every route declares a `response_model`; request bodies and query parameters are pydantic models.
- No API version in the URL until a breaking change is unavoidable; then add `/api/v2` alongside rather than altering v1 behaviour.

## Status codes

| Code | Use |
|---|---|
| 200 / 201 | Success / created |
| 202 | Work accepted and running in the background; the response carries the id of a **pollable status resource** (`POST /api/jobs/search` → `GET /api/jobs/searches/{id}`) |
| 204 | Success with no body (delete) |
| 302 | The apply redirect that records an engagement signal before sending the user on |
| 400 | Domain validation beyond schema (unknown filter key, missing required profile) |
| 404 | Missing **or not owned by the caller** — ownership mismatches never reveal that a resource exists |
| 409 | Conflict/duplicate (one active run per profile + source); includes machine keys such as `active_search_id` so the UI can point at the existing run |
| 422 | Malformed input rejected by pydantic |
| 5xx | Unexpected failure; never includes internals |

401/403 are introduced together with authentication; today the app is single-user and local.

## Errors

`{"detail": "<human message>"}` plus optional machine keys. Domain errors subclass `DomainError` (`status_code`, `default_detail`) and are mapped by the central handlers in `core/errors.py`; routers never hand-build error bodies. Validation errors render as readable field messages.

## Collections

- List endpoints are bounded: `limit` with a documented maximum and, where growth is unbounded, `offset` *(v5 #46)*; paginated lists expose the total in `X-Total-Count` (already used by `GET /api/matches`, with the header exposed to CORS).
- Filters and sort are query parameters validated by a pydantic model; filters apply at read time so changing a filter never triggers recomputation.

## Background work

Long-running operations (searches, rebuilds, embeddings) return `202` immediately, persist status in the database, and are polled by the client. Duplicate concurrent runs are rejected with `409` by a database-level guard, and runs stuck past `MAX_RUN_AGE_MINUTES` are reclaimed.

## Contract and types

- FastAPI's OpenAPI is the contract. After any schema or route change regenerate the frontend types with `npm run generate:api` (backend running); never hand-write response types.
- Behaviour changes that users or the UI can observe are reflected in `docs/guide/` and `docs/architecture.md` in the same change.
