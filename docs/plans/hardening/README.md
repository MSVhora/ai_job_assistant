# Hardening plans — bring the code up to the instruction standards

**Status:** Proposed — for owner review
**Why:** a review of `docs/instructions/` against the code (2026-10) found places where the standards are right but the code (or tooling) does not meet them yet. Principle: **where a standard is sound, fix the code; change a doc only where the doc itself was wrong.** The doc corrections already landed on `docs/docs-and-bug-fixes`; these plans fix the code.
**When:** executed right after the docs branch merges and **before** v5 implementation starts (nothing is deferred to v5).
**Standards these plans implement:** the *(H1)*–*(H7)* markers in [`docs/instructions/`](../../instructions/).

## Branching

Same rules as a version milestone (see `AGENTS.md`), with the `hardening/` prefix:

- cut `hardening/milestone` from `main`;
- one branch per plan: `hardening/H{n}-{slug}` off the milestone; merge into the milestone on close (merging `main` in at the same time), then delete the branch;
- the milestone merges to `main` with `--no-ff` after owner review.

## Plans and order

| Order | Plan | Area | Why here |
|---|---|---|---|
| 1 | [H0 env-example-and-settings](hardening-H0-env-example-and-settings.md) | config bug | Small real bug; quick win |
| 2 | [H2 backend-test-layout](hardening-H2-backend-test-layout.md) | backend tests | Mechanical move first so later diffs stay readable |
| 3 | [H3 db-hardening](hardening-H3-db-hardening.md) | database | Adds migration `0021`; shifts v5 migration numbers early |
| 4 | [H1 backend-strict-tooling](hardening-H1-backend-strict-tooling.md) | backend tooling | Strict lint/types over all code, including H3's migration; later work is written to standard |
| 5 | [H6 api-runtime-hardening](hardening-H6-api-runtime-hardening.md) | backend runtime | CORS, timeouts, limits, logging/error-contract audits |
| 6 | [H7 llm-cost-estimation](hardening-H7-llm-cost-estimation.md) | backend + UI | `estimate_cost` before v5 #41 builds on it |
| 7 | [H4 frontend-strict-tooling](hardening-H4-frontend-strict-tooling.md) | frontend tooling | Prettier + strict ESLint/TS, `npm test` gate |
| 8 | [H5 frontend-component-splits](hardening-H5-frontend-component-splits.md) | frontend | Behaviour-preserving splits under the new lint rules |
| 9 | v5 re-plan | docs | See below |

The backend track (H0–H3, H1, H6, H7) and the frontend track (H4, H5) are independent; with one developer they run sequentially in the order above.

## Rules for every plan

- Definition of done from `AGENTS.md` applies, plus the gates each plan names.
- **Docs stay in sync:** every plan has a *Doc impact* section; the listed docs change in the same change as the code.
- No drive-by refactors; strictness fixes are grouped by rule family, one commit per family.
- Each plan is marked **Implemented** with notes when it merges.

## Final doc-sync pass (after the last plan)

Re-run: the markdown link checker over `README.md` and `docs/**/*.md`; the route-vs-docs comparison (every route in `backend/app/routers/*.py` is described in `architecture.md` or a guide); `node scripts/render-diagrams.mjs` and confirm `git diff --stat docs/assets` only shows intended changes; and confirm `AGENTS.md` marks the new gates as enforced.

## v5 re-plan (after H3 and H7)

On `docs/v5-planning`:
- Migration numbers shift: H3 takes `0021` (and `0022` only if its index audit finds gaps), so v5's `0021`–`0025` become `0022`–`0026` (or `0023`–`0027`). Update the v5 plan §9 migration table and issues #40, #41, #44, #46, #50.
- v5 #41 (task routing, usage meter, cache, redaction) extends the `estimate_cost` from H7 instead of creating a cost estimator.
- v5 tests land in the mirrored layout from H2 (`tests/services/`, `tests/routers/`, …) and must pass the strict gates from H1/H4.

## Out of scope

CI automation, dependency-update bots, production Docker images and the other items in [`../future-tasks.md`](../future-tasks.md).
