# Issue #45 — Split oversized frontend components (≤ 200 lines)

**Status:** Implemented — see notes below
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

## Implementation notes

- **Scope grew from 8 to 15 files.** The plan's table was measured before #44's Prettier pass and fixes; by then 7 more files were over 200 lines (`HowItWorksSection`, `ResumeUploadForm`, `JobDetailPanel`, `MatchCard`, `ExperienceProjects`, `MergeDiffPanel`, `SourceList`). All 15 are split so `max-lines` could become an error. Order followed the plan table, then the added files.
- **Result:** `max-lines` (200, blanks and comments skipped) is now `error` for `app/**/*.tsx` and `components/**/*.tsx`; `lib/` modules stay out of scope. `npm run lint`, `format:check`, `typecheck`, `test` (39) and `build` are clean.
- **How "no behaviour change" was checked.** Before splitting I rendered `HowItWorksSection`, the get-started page, `MatchCard` (two variants), `MergeDiffPanel`, `SourceList`, `ResumeUploadForm` and `ProfileReviewForm` (AI badges on and off, with every section populated), and later `MatchList` (no profile, loading, error, empty, empty with filters, populated with pagination), as throwaway snapshots of `container.innerHTML` against mocked hooks. They were compared after each split and are not committed (the standard discourages large snapshot tests). `SearchStepperModal`/`ProfileEditor`/`RunBanners`/`SourceFiltersForm` kept their existing tests. `JobsPageClient`, `JobDetailPanel` and the wizard's effects had no render baseline: they are JSX/prop moves checked by `tsc`, lint and the existing tests, so they deserve the manual smoke below.
- **Splits:** `fields.tsx` -> `fields` + `cards` + `profile-icons`; `EducationCredentials` -> `EducationSection` / `CertificationsAwards` / `ExtraSections`; `ExperienceProjects` -> `ExperienceSection` / `ProjectsSection`; `ProfileReviewForm` -> `ContactSection` + `PreferencesSection` (the links field array and the derived-seniority `watch` moved into them); `MergeDiffPanel` -> `merge-diff.ts` helpers; `SearchSteps` -> `ProfileSourceSteps` / `DetailsStep` / `ReviewSummary`; `SearchStepperModal` -> `StartSearchButton`, `StepIndicator`, `SearchStepContent`, `SearchRunErrors`, `useSeedSearchForm` (same effect, deps and order), `search-steps.ts`, plus `emptySearchFormValues`/`missingFieldMessage` in `search-form-schema.ts`; `MatchList` -> `MatchListStates`, `MatchStatusTabs`, `MatchEmptyState`, `MatchPagination`; `MatchCard` -> `MatchSignalButtons` (owns the signal mutation) + `match-card-parts`; `JobsPageClient` -> `JobsFilterSidebar`, `JobsNotices`, `JobsSourceStates`; `JobDetailPanel` -> `job-detail-parts` + `MatchBreakdown`; get-started page -> `components/features/get-started/{icons,previews,options,OptionCard}`; `HowItWorksSection` icons and `SourceList`'s `DisclosureDialog` and `ResumeUploadForm`'s icons/progress panel moved out.
- **Deliberate non-fix found on the way:** in `MatchList` the list's class is `` `transition-opacity${matches.isFetching ? "opacity-60" : ""}` `` (no space), so the "dimmed while refetching" style never applies. Left as is to keep this a pure refactor (it is now in the moved code path of `MatchList.tsx`); worth a separate one-line fix.
- **Not done:** bundle-size comparison (`next build` in this Next version prints no per-route sizes); the manual smoke script from the plan was not run in a browser.
