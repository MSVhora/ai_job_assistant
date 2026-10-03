# H4 — Frontend strict tooling: Prettier, strict typed ESLint, stricter tsconfig, tests in the gate

**Status:** Proposed — for owner review
**Tracks:** `hardening/H4-frontend-strict-tooling`
**Plan of record:** [README](README.md) · standards: [frontend-nextjs.md](../../instructions/frontend-nextjs.md) (*H4* rules), [testing.md](../../instructions/testing.md)
**Depends on:** H1 (shares the root `.pre-commit-config.yaml`) · **Blocks:** H5

## Goal

The standard asks for formatting automation, strict typing and a test gate; today the frontend has only `eslint` (`next/core-web-vitals` + `next/typescript`) and `tsc` via `next build`. Add Prettier (frontend-only; Python keeps `ruff format`), typed strict ESLint, stricter `tsconfig`, and put `npm test` and `format:check` in the gates.

## Current state

`frontend/package.json` scripts: `dev`, `build`, `start`, `lint` (`eslint`), `test` (`vitest run`), `generate:api`. Dev deps include `vitest`, `@testing-library/*`, `eslint 9`, `eslint-config-next 16.3.3`, `openapi-typescript`. No Prettier. `tsconfig.json` has `strict: true` only. An earlier scan for explicit `any` found **none** outside generated types (the one grep hit was the word "any-of" in UI copy), so no `any` cleanup is needed — the strict rule will keep it that way.

## Locked decisions

| Decision | Choice | Rationale |
|---|---|---|
| Formatter | Prettier + `prettier-plugin-tailwindcss`; `.prettierrc` (match the existing code style: double quotes, semicolons), `.prettierignore` (`lib/api/schema.d.ts`, `.next`, `node_modules`) | Frontend-only; backend is formatted by `ruff format` |
| ESLint | Flat config adds `typescript-eslint` `strictTypeChecked` + `stylisticTypeChecked` (with `parserOptions.projectService`), `eslint-config-prettier`, `jsx-a11y` strict, `eslint-plugin-testing-library`, `eslint-plugin-vitest` for tests | Industry-standard strict typed linting |
| `max-lines` | `max-lines: ["warn"→"error", { max: 200, skipBlankLines: true, skipComments: true }]` for components; ignored for `*.test.*` and generated `schema.d.ts`. Set to **warn** in H4, flipped to **error** when H5 finishes | Enforces the ~200-line guideline without blocking H4 on the existing exceptions |
| tsconfig | Add `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`, `noImplicitOverride`, `noUnusedLocals`, `noUnusedParameters`, `noFallthroughCasesInSwitch`; add `"typecheck": "tsc --noEmit"` | Catches classes of bugs `strict` misses |
| Scripts | `format` (`prettier --write .`), `format:check`, `typecheck` | Gate commands |
| Hooks | Extend the root `.pre-commit-config.yaml` (from H1) with Prettier and ESLint on staged frontend files | One hook framework for both stacks |
| Format commit | One mechanical `prettier --write` commit, isolated so blame can skip it (`.git-blame-ignore-revs`) | Keeps history usable |
| Tests | `npm test` is a gate; failing tests found here are fixed in this plan | Standard says tests gate "done" |

## Method

1. Install dev deps; add configs; run `npm run lint`, `npm run typecheck`, `npm test` and record the **baseline error counts** per rule in this file's notes.
2. Run Prettier once (format commit).
3. Clear ESLint/TS errors by rule family, one commit each (floating promises/`no-misused-promises`, `no-unnecessary-condition`, `prefer-nullish-coalescing`, indexed-access narrowing, unused vars, a11y). Behaviour changes are not allowed in these commits; a real bug found gets its own test and commit.
4. Add the scripts and hooks; run the full gate.

## Tests

Existing vitest suites (`SearchStepperModal.test.tsx`, `ProfileEditor.test.tsx`, `RunBanners.test.tsx`, `SourceFiltersForm.test.tsx`, `search-form-schema.test.ts`, `profile-schema.test.ts`) stay green; tests fixed or added only for bugs the stricter rules reveal.

## Gates

`npm run lint && npm run format:check && npm run typecheck && npm test && npm run build` in `frontend/`.

## Doc impact

`README.md` Development table (`format`, `format:check`, `typecheck`, `test`); `AGENTS.md` definition of done (target gate becomes enforced); `docs/instructions/frontend-nextjs.md` (remove *(H4)* markers); `docs/instructions/testing.md` (frontend gate).

## Risks

| Risk | Mitigation |
|---|---|
| Strict typed ESLint is noisy on a large codebase | Rule-family commits; temporary per-rule `warn` allowed only until the family is cleared |
| `exactOptionalPropertyTypes` conflicts with generated API types | Normalise at the `lib/api` boundary; do not hand-edit `schema.d.ts` |
| Prettier reformat hides real changes in blame | Isolated commit + `.git-blame-ignore-revs` |

## Out of scope

Component splits (H5), CI (see [future-tasks](../future-tasks.md)), changing the UI design system.
