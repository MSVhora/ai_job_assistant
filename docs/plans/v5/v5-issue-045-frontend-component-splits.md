# Issue #45 — Split oversized frontend components (≤ 200 lines)

**Status:** Proposed — for owner review
**Tracks:** GitHub issue #45 (milestone `v5`, branch `v5/45-frontend-component-splits`)
**Plan of record:** [v5 plan](v5-hardening-plan.md) · standards: [frontend-nextjs.md](../../instructions/frontend-nextjs.md) ("components under ~200 lines")
**Depends on:** #44 (`max-lines` rule, formatting, strict lint) · **Blocks:** v5 UI work (new screens build on smaller parts)

## Goal

Bring every component file under ~200 lines **without changing behaviour or appearance**, then flip the ESLint `max-lines` rule from warn to error so it stays true.

## Evidence (non-test, non-generated files over 200 lines)

| File | Lines | Split direction |
|---|---|---|
| `components/features/profile/fields.tsx` | 422 | One file per field group (contact, experience, education, skills, preferences); shared field primitives stay in `fields.tsx` |
| `components/features/jobs/SearchStepperModal.tsx` | 369 | Extract the step navigation, the review step and the submit/409 handling hook (`useStartSearch`) |
| `app/get-started/page.tsx` | 340 | Section components under `components/features/get-started/` |
| `components/features/jobs/SearchSteps.tsx` | 301 | One component per wizard step |
| `components/features/profile/ProfileReviewForm.tsx` | 297 | Section components + a `useProfileReviewForm` hook |
| `components/features/jobs/MatchList.tsx` | 271 | List, toolbar/tabs and empty/error states |
| `components/features/profile/EducationCredentials.tsx` | 270 | Education, certifications and awards sub-sections |
| `components/features/jobs/JobsPageClient.tsx` | 266 | Sidebar, run banners area and matches area; state hooks extracted |

(`lib/profile-schema.ts` 331, `search-form-schema.ts` 280 and `lib/api/index.ts` 264 are not components; they are left alone unless the lint rule is scoped to them — it is not.)

## Locked decisions

| Decision | Choice | Rationale |
|---|---|---|
| Behaviour | None changes: props, DOM output, accessibility attributes, query keys and network calls stay identical | Refactor only |
| Order | One file per commit, in the table order, tests green after each | Small, reviewable, bisectable |
| Extraction rules | Presentational pieces → `components/features/...`; stateful logic → hooks in `hooks/` or next to the feature; no new dependencies | Matches the structure standard |
| Safety net | Where a file lacks tests, add a small render test (roles/labels/text) **before** splitting it | Prove "no behaviour change" |
| Lint | After the last split, set `max-lines` to `error` | Locks the result in |

## Verification

- `npm run lint && npm run format:check && npm run typecheck && npm test && npm run build` after every commit.
- Manual smoke script (recorded in the PR): upload a resume → review and save a profile → gap-fill → start a search (including the duplicate-run 409 path) → view matches, tabs, slider, signals → Tune my queries dialog → Setup page and get-started page.
- Compare bundle size output of `next build` before/after (no unexpected growth).

## Doc impact

`docs/instructions/frontend-nextjs.md` (remove *(v5 #45)* marker); no user-facing guide changes.

## Risks

| Risk | Mitigation |
|---|---|
| Subtle behaviour change (effect ordering, re-render boundaries) | Keep hooks' dependencies identical; render tests; manual smoke |
| Conflicts with parallel UI work | Merge #45 before v5 UI issues start |

## Out of scope

Visual redesign, state-management changes, renaming public components, splitting non-component modules.
