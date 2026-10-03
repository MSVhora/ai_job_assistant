# H0 — `.env.example` correctness and a settings↔env guard

**Status:** Proposed — for owner review
**Tracks:** `hardening/H0-env-example-and-settings`
**Plan of record:** [README](README.md) · standards: [backend-fastapi.md](../../instructions/backend-fastapi.md) (config only via `Settings`), `AGENTS.md` ("setup or behavior changed: `.env.example` updated")
**Depends on:** nothing · **Blocks:** nothing (first in order)

## Goal

`.env.example` is the user's template for every setting. Two defects: the seniority band keys are misspelled (so a user who edits them changes nothing), and `CORS_ORIGINS` is missing. Fix both and add a test so a setting can never be added or misspelled without `.env.example` following.

## Evidence

- `.env.example` lines 96–98: `SENORITY_BAND_SENIOR`, `SENORITY_BAND_STAFF`, `SENORITY_BAND_PRINCIPAL` (note the missing `I`); `Settings` fields are `seniority_band_*` and `Settings` uses `extra="ignore"`, so the misspelled keys are silently ignored. Defaults happen to equal the template values, which is why nobody noticed.
- `Settings.cors_origins` (`core/config.py`) has no entry in `.env.example`.
- All other `Settings` fields are present (checked field by field).

## Locked decisions

| Decision | Choice | Rationale |
|---|---|---|
| Guard | A pytest that parses `.env.example` keys (non-comment `KEY=` lines) and compares them with the upper-cased `Settings.model_fields` | Catches missing and misspelled keys forever |
| Allowed extras | An explicit allow-list in the test: `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` (Compose), `NEXT_PUBLIC_API_BASE_URL` (frontend) | These are real keys but not `Settings` fields |
| `CORS_ORIGINS` format | Documented as a JSON list (`["http://localhost:3000"]`), matching pydantic-settings parsing of `list[str]` | It is what `Settings` actually accepts |
| Strictness | Do **not** turn `extra="ignore"` into `forbid` | The shared `.env` also feeds Compose and the frontend; the test is the guard instead |

## Scope

- `.env.example`: rename the three keys to `SENIORITY_BAND_*`; add a commented `CORS_ORIGINS` entry with the default and a one-line explanation.
- `backend/tests/test_env_example.py` (moved to `tests/core/` by H2): the guard above, with a clear failure message listing missing and unknown keys.

## Tests

- Guard passes on the fixed file; temporarily misspelling a key or removing `CORS_ORIGINS` makes it fail (verify once manually, not committed).
- Existing settings tests unchanged.

## Gates

`ruff check . && ruff format --check . && pytest` (target gates once H1 lands).

## Doc impact

`.env.example` (the fix itself); `docs/guide/01-getting-started.md` already documents `CORS_ORIGINS` (added on the docs branch) — confirm it matches the final `.env.example` wording.

## Risks

Low. A user who previously relied on the misspelled keys gets the documented defaults, which are identical.

## Out of scope

Validating `.env` at startup against unknown keys; secrets management.
