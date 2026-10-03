# Future tasks (parked, not scheduled)

Items raised during reviews that are deliberately **not** part of the current plans. Promote an item into a versioned plan before any work starts.

| Task | Why | Notes |
|---|---|---|
| **CI workflow (GitHub Actions)** | Every "must pass before done" gate is currently honour-system (no `.github/workflows`) | Backend job: ruff, `ruff format --check`, pyright, `pytest --cov` on a `pgvector/pgvector:pg16` service, `alembic check`, `pip-audit`. Frontend job: lint, `format:check`, typecheck, test, build, `npm audit`. Docs job: link check and `render-diagrams` drift (`git diff --exit-code docs/assets`). Decide after v5 whether it is worth the maintenance for a solo project. |
| Dependency update automation | Keep locks and audits fresh | Dependabot or Renovate for `pyproject`/`uv.lock`, `package.json`, Docker base images |
| Migration linter in CI | Catch unsafe DDL early | `squawk` or equivalent against the migrations |
| Resume delete endpoint | `security-privacy.md` notes there is no way to delete a resume through the app | Needs ownership checks, file removal, and handling of profiles that cite `source_resume_id` (SET NULL) |
| Production Docker images | `frontend/Dockerfile` runs `npm run dev`; compose runs the backend with `--reload` | Multi-stage builds, `next build && next start`, non-root users, healthchecks for `api`/`web` |
| Structured (JSON) logging | Current logs are `key=value` text | Only worth it if logs are shipped somewhere |
| Decide the fate of `backend/openapi.json` | It is untracked in the working tree | Either generate and commit it deliberately (it feeds `generate:api`) or add it to `.gitignore` |
| Frontend `tsc` and a11y checks in CI | Catch regressions without a browser | `axe` via Testing Library for key screens |
| Auth and multi-user | Out of scope while single-user | See the gate in `security-privacy.md` before any shared deployment |
