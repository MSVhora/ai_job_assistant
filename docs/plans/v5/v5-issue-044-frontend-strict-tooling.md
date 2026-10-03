# Issue #44 — Frontend strict tooling: Prettier, strict typed ESLint, stricter tsconfig, tests in the gate

**Status:** Implemented — see notes below
**Tracks:** GitHub issue #44 (milestone `v5`, branch `v5/44-frontend-strict-tooling`)
**Plan of record:** [v5 plan](v5-hardening-plan.md) · standards: [frontend-nextjs.md](../../instructions/frontend-nextjs.md) (*v5 #44* rules), [testing.md](../../instructions/testing.md)
**Depends on:** #41 (shares the root `.pre-commit-config.yaml`) · **Blocks:** #45

## Goal

The standard asks for formatting automation, strict typing and a test gate; today the frontend has only `eslint` (`next/core-web-vitals` + `next/typescript`) and `tsc` via `next build`. Add Prettier (frontend-only; Python keeps `ruff format`), typed strict ESLint, stricter `tsconfig`, and put `npm test` and `format:check` in the gates.

## Current state

`frontend/package.json` scripts: `dev`, `build`, `start`, `lint` (`eslint`), `test` (`vitest run`), `generate:api`. Dev deps include `vitest`, `@testing-library/*`, `eslint 9`, `eslint-config-next 16.3.3`, `openapi-typescript`. No Prettier. `tsconfig.json` has `strict: true` only. An earlier scan for explicit `any` found **none** outside generated types (the one grep hit was the word "any-of" in UI copy), so no `any` cleanup is needed — the strict rule will keep it that way.

## Locked decisions

| Decision | Choice | Rationale |
|---|---|---|
| Formatter | Prettier + `prettier-plugin-tailwindcss`; `.prettierrc` (match the existing code style: double quotes, semicolons), `.prettierignore` (`lib/api/schema.d.ts`, `.next`, `node_modules`) | Frontend-only; backend is formatted by `ruff format` |
| ESLint | Flat config adds `typescript-eslint` `strictTypeChecked` + `stylisticTypeChecked` (with `parserOptions.projectService`), `eslint-config-prettier`, `jsx-a11y` strict, `eslint-plugin-testing-library`, `eslint-plugin-vitest` for tests | Industry-standard strict typed linting |
| `max-lines` | `max-lines: ["warn"→"error", { max: 200, skipBlankLines: true, skipComments: true }]` for components; ignored for `*.test.*` and generated `schema.d.ts`. Set to **warn** in #44, flipped to **error** when #45 finishes | Enforces the ~200-line guideline without blocking #44 on the existing exceptions |
| tsconfig | Add `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`, `noImplicitOverride`, `noUnusedLocals`, `noUnusedParameters`, `noFallthroughCasesInSwitch`; add `"typecheck": "tsc --noEmit"` | Catches classes of bugs `strict` misses |
| Scripts | `format` (`prettier --write .`), `format:check`, `typecheck` | Gate commands |
| Hooks | Extend the root `.pre-commit-config.yaml` (from #41) with Prettier and ESLint on staged frontend files | One hook framework for both stacks |
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

`README.md` Development table (`format`, `format:check`, `typecheck`, `test`); `AGENTS.md` definition of done (target gate becomes enforced); `docs/instructions/frontend-nextjs.md` (remove *(v5 #44)* markers); `docs/instructions/testing.md` (frontend gate).

## Risks

| Risk | Mitigation |
|---|---|
| Strict typed ESLint is noisy on a large codebase | Rule-family commits; temporary per-rule `warn` allowed only until the family is cleared |
| `exactOptionalPropertyTypes` conflicts with generated API types | Normalise at the `lib/api` boundary; do not hand-edit `schema.d.ts` |
| Prettier reformat hides real changes in blame | Isolated commit + `.git-blame-ignore-revs` |

## Out of scope

Component splits (#45), CI (see [future-tasks](../future-tasks.md)), changing the UI design system.

## Implementation notes

- **Baseline measured** (configs only, no fixes): `tsc` 38 errors (26 `TS2375` + 7 `TS2379` from `exactOptionalPropertyTypes`, 5 others); ESLint 279 problems (92 `no-confusing-void-expression`, 69 `restrict-template-expressions`, 43 `no-unnecessary-condition`, 14 `non-nullable-type-assertion-style`, 14 `max-lines`, 10 `prefer-nullish-coalescing`, the rest single digits) after ignoring the generated `schema.d.ts`, which alone had 60 more. Now: `tsc` 0, ESLint 0 errors and 15 `max-lines` warnings on components/pages (the #45 queue).
- **Commits:** configs, one isolated Prettier commit (`bdbef43`, listed in `.git-blame-ignore-revs`; enable with `git config blame.ignoreRevsFile .git-blame-ignore-revs`), tsc errors, ESLint autofix + redundant conditions, the rest.
- **`max-lines` scope:** the rule applies to `app/**/*.tsx` and `components/**/*.tsx`, not `lib/` modules (`lib/api/index.ts`, `lib/profile-schema.ts`, `search-form-schema.ts` are over 200 lines); the standard says "components". Stays `warn` until #45 flips it.
- **ESLint tunings** (each with a comment): `restrict-template-expressions` allows numbers; `prefer-nullish-coalescing` ignores strings (an empty string must fall back too, e.g. `target_title || headline`); `no-unnecessary-type-parameters` off in `lib/api/client.ts` (unchecked response casts); `testing-library/no-node-access` off in `SearchStepperModal.test.tsx` (an unlabeled Radix-portaled form). `eslint-plugin-jsx-a11y` is registered by `eslint-config-next`, so only its strict rule set is added.
- **No `!` on API data:** `eslint --fix` turned 14 `as T` casts into `!`; they were replaced by `skipToken` in the query hooks (`use-job-search`, `use-matches`, `use-profiles`, `use-match-rebuild`, `use-resume-draft`, `JobDetailPanel`).
- **Behaviour-adjacent edits** (suite green, JSON unchanged): optional props accept `| undefined`; the search payload/spec omit empty keys instead of `undefined`; ~25 redundant `?.`/`??` on non-nullable generated types removed (the `ProfileEditor` test fixture was an incomplete profile that relied on them and is now complete); `FormEvent` → React 19 `SubmitEvent`; `ProfileReviewForm` wraps the async submit in `void`; vitest `globals: true` so RTL auto-cleanup runs and the manual `cleanup()` calls are gone.
- **`npm audit` (not fixed here, waived):** `next` 16.3.3 has one critical advisory (RCE in `next/og` `ImageResponse`, GHSA-vcvr-r3jv-pc5j; the app does not use `next/og`), fixable by a non-major bump to 16.3.8. The rest are dev-tool transitives (`vitest`/`@vitest/mocker`, `eslint-config-next`'s `braces`/`micromatch`/`fast-glob`, `@redocly/openapi-core` via `openapi-typescript`) whose fixes are major downgrades. All of this predates #44; upgrading Next is a separate, deliberate change.
- **Hooks:** Prettier and ESLint added to the root `.pre-commit-config.yaml` as local hooks run from `frontend/`.
