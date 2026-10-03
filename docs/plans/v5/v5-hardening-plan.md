# v5 plan — hardening: bring the code up to the instruction standards

**Status:** Proposed plan for v5 (owner review pending)
**Depends on:** v1 (#1–#12), v2 (#13–#23), v3 (#24–#30), v4 (#31–#39) — all done.
**Plan of record:** this file; per-issue plans `v5-issue-NNN-*.md` (#40–#47), one GitHub milestone `v5`, issues merged sequentially into a `v5/milestone` branch (see `AGENTS.md` git workflow).
**Why:** a review of `docs/instructions/` against the code (2026-10) found places where the standards are right but the code (or tooling) does not meet them yet. Principle: **where a standard is sound, fix the code; change a doc only where the doc itself was wrong.** The doc corrections already landed on `docs/docs-and-bug-fixes`; v5 fixes the code.
**Next milestone:** the Developer Evidence Engine (evidence-grounded resume builder + interview agent) is **v6**; it starts after v5 merges. Its plans live in `docs/plans/v6/`.
**Standards v5 implements:** the *(v5 #40)*–*(v5 #47)* markers in [`docs/instructions/`](../../instructions/).

## Branching

Standard milestone workflow from `AGENTS.md`:

- cut `v5/milestone` from `main`;
- one branch per issue: `v5/{issue-number}-{slug}` (for example `v5/42-backend-test-layout`) off the milestone; merge into the milestone on close (merging `main` in at the same time), then delete the branch;
- the milestone merges to `main` with `--no-ff` after owner review.

## Issues and execution order

Issue numbers continue from v4's #39. They are numbered by area; **execute in the order below**.

| Order | Issue | Area | Why here |
|---|---|---|---|
| 1 | [#40 env-example-and-settings](v5-issue-040-env-example-and-settings.md) | config bug | Small real bug; quick win |
| 2 | [#42 backend-test-layout](v5-issue-042-backend-test-layout.md) | backend tests | Mechanical move first so later diffs stay readable |
| 3 | [#43 db-hardening](v5-issue-043-db-hardening.md) | database | Adds migration `0021`; fixes migration numbering for v6 early |
| 4 | [#41 backend-strict-tooling](v5-issue-041-backend-strict-tooling.md) | backend tooling | Strict lint/types over all code, including #43's migration; later work is written to standard |
| 5 | [#46 api-runtime-hardening](v5-issue-046-api-runtime-hardening.md) | backend runtime | CORS, timeouts, limits, logging/error-contract audits |
| 6 | [#47 llm-cost-estimation](v5-issue-047-llm-cost-estimation.md) | backend + UI | `estimate_cost` lands before v6's LLM work builds on it |
| 7 | [#44 frontend-strict-tooling](v5-issue-044-frontend-strict-tooling.md) | frontend tooling | Prettier + strict ESLint/TS, `npm test` gate |
| 8 | [#45 frontend-component-splits](v5-issue-045-frontend-component-splits.md) | frontend | Behaviour-preserving splits under the new lint rules |

The backend issues (#40, #42, #43, #41, #46, #47) and the frontend issues (#44, #45) are independent; with one developer they run sequentially in the order above.

## Rules for every issue

- Definition of done from `AGENTS.md` applies, plus the gates each plan names.
- **Docs stay in sync:** every plan has a *Doc impact* section; the listed docs change in the same change as the code.
- No drive-by refactors; strictness fixes are grouped by rule family, one commit per family.
- Each plan is marked **Implemented** with notes when it merges.

## Milestone close (after #45)

Final **doc-sync pass**: re-run the markdown link checker over `README.md` and `docs/**/*.md`; the route-vs-docs comparison (every route in `backend/app/routers/*.py` is described in `architecture.md` or a guide); `node scripts/render-diagrams.mjs` and confirm `git diff --stat docs/assets` only shows intended changes; and confirm `AGENTS.md` marks the new gates as enforced. Then the owner reviews and the milestone merges to `main`.

## Hand-off to v6

v6 (`docs/plans/v6/`) is written against the state v5 leaves behind:

- migrations: #43 takes `0021` (and `0022` only if its schema audit finds gaps), so v6's migrations start at `0023`;
- v6 #49 (task routing, usage meter, cache, redaction) extends the `estimate_cost` from #47 instead of creating a cost estimator;
- v6 tests land in the mirrored layout from #42 (`tests/services/`, `tests/routers/`, …) and must pass the strict gates from #41 and #44;
- new tables with `updated_at` add the trigger through the helper from #43.

## Out of scope

CI automation, dependency-update bots, production Docker images and the other items in [`../future-tasks.md`](../future-tasks.md).
