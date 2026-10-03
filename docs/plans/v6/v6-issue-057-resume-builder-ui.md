# Issue #57 — Resume builder UI: create → review (copy, comments, private marks) → generate PDF (Week 3)

**Status:** Proposed — for owner review (revised 2026-10-02 after owner decisions)
**Tracks:** GitHub issue #57 (milestone `v6`, branch `v6/49-resume-builder-ui`)
**Plan of record:** [v6-implementation-plan.md](v6-implementation-plan.md) §2.5, §6.4, §10.2, §12
**Depends on:** #53 (nav, evidence UI patterns), #54–#56
**Blocks:** #61 (acceptance run)

---

## Goal

A three-step screen: **create** (profile, length 1–4 pages, template, JD paste or ranked match) → **review** the generated resume *as data* — copyable, with private marks, included/not-included lists, conflicts, JD gaps and per-section comments — → explicit **Generate PDF** with preview and download.

## Locked decisions

| Decision | Choice | Rationale |
|---|---|---|
| Routes | `/resume-builder` (list + create) and `/resume-builder/[id]` (review + PDF) | Plan §10.2 |
| Length | Select: "1 page", "2 pages", "Multiple pages" (3 or 4) | Owner decision |
| Tailoring strength | When a JD (paste or match) is chosen, a 3-way control **Light / Balanced (default) / Strong** with the help text "How much the job description should boost aligned work. Work that doesn't match the JD is still included by its own priority."; hidden when no JD | Owner 2026-10-02 |
| **No PDF until asked** | Creating/regenerating shows the review view only; the PDF area stays empty until "Generate PDF" | Owner decision |
| Review view | Sections (Summary, Experience, Projects, Skills, Education…) as plain selectable text; each bullet shows evidence chips (open the commit/PR/note), check badge, origin badge, and the **"Private repo" mark** when `from_private` (screen only) | Owner decision |
| Copy / export | Buttons per bullet, per section, and whole document: **Plain text**, **Markdown**, **JSON Resume** (calls `GET …/export`); output is clean — no marks, no badges; contact from the profile | "Copy into my own resume format" |
| Included vs not included | Included content in resume order; a ranked "Not included" list with reasons (did not fit / needs review / omitted overlap / not written) and **Add** (re-fit; writes the bullet on demand if unwritten) and **Remove**; page usage line "2 pages of 2 — N more achievements available" | Priority-first transparency |
| Overlapping roles | A card per omitted role: "Omitted: *Role A* (Jan 2022–Mar 2023) overlaps *Role B* — kept the higher-priority role" with **Include anyway** | Owner decision |
| Comments | Comment box on every section and bullet; list of open/applied/rejected comments; **Apply comments** regenerates only commented blocks; rejected ones show the reason and an **Add a note** action | Owner requirement |
| Conflicts panel | By severity; **Edit in profile** deep link (edits go through the existing PATCH → `profile_revision`) or **Keep as is** | Hard req. 5 |
| JD gaps | "Not supported by your evidence" list with nearest evidence and **Add a note** | Plan §6.5 |
| Private toggle | "Exclude private-derived bullets" regenerates/re-fits without them; no download confirmation dialog and no marks in the PDF (owner decision) | Simplicity |
| PDF step | "Generate PDF" → `POST …/render` → blob URL in an `<iframe>`; download button; request-id guard against out-of-order responses; failure `CannotFit` shows the items to review | No new dependency |
| Template picker | `classic` / `compact` select, applied at PDF time and used by the fit | MVP; first cut-line item |
| Existing screens | `MatchCard` "Tailor resume" → `/resume-builder/new?match=…&profile=…`; `/profile` "Build resume from evidence" | Plan §2.5 |

## Scope

### Frontend (`frontend/`)

- `app/resume-builder/page.tsx`, `app/resume-builder/[id]/page.tsx`, `new` flow via query params.
- `components/features/resume/`: `ResumeCreateForm` (length, template, JD picker, tailoring strength), `JdPicker` (paste / from-match tabs with the match rationale shown), `ReviewSection`, `BulletRow` (`EvidenceChips`, `CheckBadge`, `PrivateBadge`, `CopyButton`), `NotIncludedList`, `OmittedRoleCard`, `ConflictsPanel`, `GapsPanel`, `CommentThread` + `ApplyCommentsBar`, `ExportMenu`, `PdfStep` (`PdfPreview`, `FitSummary`).
- `lib/api/` functions and `hooks/` (`useResumeDocument`, `useFit`, `useApplyComments`, `useRenderPdf` with request-id guard).
- `MatchCard` and profile CTA; `SiteHeader` nav entry; regenerate API types.

### Backend

Only small additions if the UI needs them (`GET /api/resume-documents?profile_id=` list); everything else is delivered by #54–#56.

### Tests / verification

- `npm run lint && npm run build` green.
- Manual script recorded in the PR: create from paste (2 pages) and from a match (1 page); review shows data with no PDF; private marks visible on the right bullets and **absent** from every copy format; Plain/Markdown/JSON Resume copies paste cleanly; add a "not included" bullet (re-fit) and remove one; omitted overlapping role → Include anyway; comment on one section → Apply → only that section changes; a comment asking for unsupported content is rejected with "Add a note"; conflict "Edit in profile" and "Keep as is"; Generate PDF → page count ≤ target, downloads; unfittable state lists items; out-of-order PDF responses ignored.
- Hook tests for the request-id guard where the repo has frontend tests; otherwise documented manual script (current frontend practice).

### Standards from v5 (must hold from the first commit)

- **Gate:** `npm run lint && npm run format:check && npm run typecheck && npm test && npm run build` in `frontend/`; Prettier (width 100) with the Tailwind plugin.
- **Components ≤ 200 lines** (ESLint `max-lines` is an error in `app/` and `components/`): split into subcomponents and hooks from the start.
- **Types:** no `any`, no `!` on API data (use TanStack Query's `skipToken` for nullable ids); optional props are declared `?: T | undefined`; payloads omit empty keys instead of sending `undefined` (`exactOptionalPropertyTypes`, `noUncheckedIndexedAccess`).
- **Structure:** every route segment that fetches data has `loading.tsx`, `error.tsx` and `not-found.tsx`; all calls go through `lib/api` with regenerated types (`npm run generate:api`); read the Next 16 docs in `node_modules/next/dist/docs/` before using framework APIs.
- **Tests:** co-located Testing Library tests for every new component and hook, mocking at the `lib/api` boundary.

### Gates / docs

Frontend + backend gates; guide 04 finalized (screenshots in `docs/assets/`): choosing a length, reading the review view, copying, comments, private marks, generating the PDF; README feature list.

## Risks

| Risk | Mitigation |
|---|---|
| Review view becomes a heavy editor | Plain text bullets, up/down reorder only; comments are the rewrite mechanism |
| Users expect the PDF to mirror private marks | Guide states marks are review-only by design |
| Copy output drifts from what the PDF contains | Both come from the same stored content; export test in #54 compares them |

## Out of scope

Rich-text editing, drag-and-drop, side-by-side diff against the original profile, sharing links, cover letters.
