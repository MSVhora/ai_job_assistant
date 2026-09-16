# AGENTS.md

Guidance for AI coding agents working in this repo. These rules apply to every task.
Detailed per-area standards live in `docs/instructions/` and are loaded automatically via `opencode.json`.

## Project

AI Job Assistant — self-hosted, single-user, BYOK (bring-your-own-key) web app:
resume upload → AI-extracted, human-reviewed profile → multi-source job discovery → ranked matches with explanations.

- **Plan of record:** `docs/plans/v1/v1-implementation-plan.md` — read it before non-trivial work. Do not silently drift from its scope; if something in it is wrong or changed, say so in the response.

## Stack

| Layer | Tech |
|---|---|
| Backend | Python 3.12, FastAPI, SQLAlchemy 2.0 (async), pydantic v2, pydantic-settings |
| Frontend | Next.js (App Router), TypeScript strict, Tailwind CSS |
| Database | Postgres + pgvector, Alembic migrations |
| LLM | LiteLLM wrapper (single module); default provider Gemini Flash |
| Deploy | Docker Compose; config via `.env` (see `.env.example`) |

## Layout

```
backend/
  app/
    main.py, core/, deps.py
    routers/      # HTTP layer only
    services/     # business logic
    models/       # SQLAlchemy ORM models (source of truth for schema)
    schemas/      # pydantic request/response models
    adapters/     # llm.py (LiteLLM wrapper), job source connectors
  alembic/        # migrations
  tests/
frontend/
  app/, components/ (ui/ + features/), lib/, hooks/
docs/instructions/  # coding standards (always loaded)
docs/plans/         # versioned implementation plans (v1/, v2/, v3/ per-version folders)
```

## Non-negotiables

1. **Every Postgres schema change = a new Alembic migration.** Models are the source of truth; autogenerate, review, apply. Never hand-alter the DB. See `docs/instructions/database-postgres.md`.
2. **All LLM calls go through the LiteLLM wrapper** (`app/adapters/llm.py`). Never import an OpenAI/Anthropic/Google SDK directly in routers or services.
3. **All job-source calls go through the `JobSource` connector interface.** New sources = connector config + mapper, not changes to matching logic.
4. **Never commit secrets.** Keys live in `.env` (gitignored), documented in `.env.example`.
5. **Never trust the client.** Backend re-validates everything with pydantic regardless of frontend checks.

## Git workflow

- **Milestone branch, one per version.** At milestone start, cut `v{N}/milestone` (e.g. `v4/milestone`) from `main`. This is the integration target for the whole milestone; `main` only receives the milestone as one reviewed unit.
- **One branch per issue (off the milestone branch).** Create `v{N}/{issue-number}-{slug}` (e.g. `v4/31-query-builder-cache`) from `v{N}/milestone` before starting an issue; docs-only changes may go straight to `main`.
- **Merge issues into the milestone branch on close, not before.** When the issue is tested and complete: merge its branch into `v{N}/milestone`, merging `main` into the milestone branch at the same time (`git merge main` into the milestone first — this is the *one* allowed merge direction into the milestone). Resolving drift in small chunks keeps the final milestone→main merge conflict-free. Then delete the issue branch (local + remote). Run the lint/test gates before each merge so the milestone branch is always green.
- **Milestone merge needs owner review.** When every issue in the milestone is done and tested: merge `v{N}/milestone` into `main` with `--no-ff` (one recoverable milestone commit), `git pull`, then delete the milestone branch (local + remote).
- Never commit directly to `main` for issue work; never rebase the milestone branch mid-milestone (keeps tested states testable); keep the milestone-commit message convention.


## Definition of done (before reporting a task complete)

- Backend touched: `ruff check . && ruff format --check . && pytest` pass (run in `backend/`).
- Frontend touched: `npm run lint && npm run build` pass (run in `frontend/`).
- Model changes: migration generated, reviewed, and included in the same change.
- New external dep: justified in the response (prefer stdlib / what the stack already uses).
- Setup or behavior changed: `.env.example` / README updated.
- Docs kept in sync: if the change alters user-facing behavior, the API surface, the DB schema, or the architecture, update the relevant guide (`docs/guide/`), `docs/architecture.md`, and any affected diagram in the same change, then re-run `node scripts/render-diagrams.mjs` so the rendered SVG assets match. New issue plans state their doc impact.

## Commands

| What | Command |
|---|---|
| Backend dev | `uvicorn app.main:app --reload` (in `backend/`) |
| Backend lint/format | `ruff check .` / `ruff format .` (in `backend/`) |
| Backend tests | `pytest` (in `backend/`) |
| New migration | `alembic revision --autogenerate -m "descriptive_message"` (in `backend/`) |
| Apply migrations | `alembic upgrade head` (in `backend/`) |
| Frontend dev | `npm run dev` (in `frontend/`) |
| Frontend lint/build | `npm run lint` / `npm run build` (in `frontend/`) |
| Full stack | `docker compose up -d` |
| Re-render doc diagrams | `node scripts/render-diagrams.mjs` (repo root; needs `@mermaid-js/mermaid-cli`) |

## Code style

- Type hints everywhere (Python) / strict TS.
- No comments except non-obvious decisions; no TODOs without an owner in the plan.
- Keep responses and commit-scoped edits minimal — no drive-by refactors.
