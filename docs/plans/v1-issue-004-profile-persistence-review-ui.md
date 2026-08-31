# Issue #4 — Profile Persistence + Review/Edit UI + Revision Audit

**Status:** Planned
**Tracks:** GitHub issue #4 (Day 3, Week 1)
**Plan of record:** [v1-implementation-plan.md](v1-implementation-plan.md) §4, §6, §7, §8
**Depends on:** Issue #2 (upload + text extraction — done), Issue #3 (LLM draft extraction — done)

---

## Goal

Make the reviewed profile real: `GET/PATCH /api/profile` persists `candidate.structured_profile`
(with an embedded preferences block), every PATCH writes a field-level diff row to
`profile_revision`, and the frontend gets the Upload → Review → Save flow from plan §7 page 2 —
AI-extracted fields highlighted, every field editable, per-field error slots, and a re-upload
merge/diff review that never silently overwrites.

**Acceptance (from the issue):** user can correct any field; every correction recorded in revisions.

Note: the issue's checklist item "migration: candidate, resume tables" is already satisfied —
migrations `0002`/`0003` created them. This issue's migration is `0004`.

## Locked decisions

Decided during planning (deviations from plan §4 are additive/deferral and accepted):

| Decision | Choice | Rationale |
|---|---|---|
| Preferences & completeness columns | **Deferred** — prefs stay inside `structured_profile` (per issue #3's schema); no separate `preferences`/`completeness` jsonb columns in v1 yet | Plan §2 locked storage as "structured_profile jsonb + profile_revision audit table"; gap-fill (#5) can derive missing fields from the profile, and the priority-weights column lands with matching (#6+) where it's consumed. Two homes for prefs = two sources of truth. `docs/architecture.md` ER amended in this change |
| PATCH semantics | **Upsert**: PATCH creates the profile when none exists (this is the "save reviewed draft" path); 200 either way | Plan §6 defines only GET/PATCH — a separate POST would drift; the first save from the review form is just a PATCH |
| Revision sources are server-decided | Server derives `source` + diffs; client never sends them. `source_resume_id` (optional, validated) is the only hint the client provides | Never trust the client |
| First save from a draft | **Two revisions when the user corrected fields during first review**: `ai_extraction` (draft vs null — the AI baseline) + `manual_edit` (draft vs submitted) only where they differ; one `ai_extraction` row when submitted == draft | Acceptance says every correction is recorded — folding first-review edits into the AI baseline would misattribute them. Both values are already in hand |
| Later PATCHes | One revision per PATCH: `manual_edit` (no resume ref) or `reupload_merge` (`source_resume_id` points at a resume whose draft exists). Empty-diff PATCHes still write a row — keeps "every PATCH writes a revision" literal | Plan §6 + §4 source enum |
| Diff shape | `diff` jsonb = `{path: {old, new}}`; dotted paths for scalars (`contact.full_name`, `headline`, `preferences.target_title`), whole-value old/new for list fields (`skills`, `experience[...]` arrays) | Plan §4's "field-level {field: {old, new}}"; list-internal element diffs are noise for a human-read audit |
| Draft fetch | New `GET /api/resume/{resume_id}/draft` returning the issue-#3 `DraftProfileResponse` shape (no LLM call, no re-extract) | Refresh-safe review UI; extract re-runs cost tokens. Additive to plan §6, same spirit as #3's draft-persistence decision |
| GET with no profile | `404` via `ProfileNotFoundError` | Backend standards: 404 = missing. Frontend maps 404 → empty state |
| Merge UX | Merge panel defaults to **keep current** per field; taking the draft's value is explicit (per-field toggle or "take all"); save = one PATCH with the merged profile + `source_resume_id` | "Never silent overwrite" — the old→new diff is fully captured in the `reupload_merge` revision |
| AI-extracted highlighting | Purely derived at render time: first review = all fields flagged; merge mode = fields where draft ≠ saved are flagged; edit mode = no badges | No provenance tracking needed — revisions already record the history |

## Scope

### Backend

#### Migration `0004_add_structured_profile_and_profile_revision`

- `candidate.structured_profile` jsonb **null** (profile is optional until first save)
- `profile_revision` table: `id` uuid pk, `candidate_id` fk (RESTRICT, indexed),
  `source` native PG enum `profile_revision_source` with all four values
  (`ai_extraction | manual_edit | gap_fill | reupload_merge` — created upfront so #5/#6
  need no enum migration), `diff` jsonb, `created_at` timestamptz default `now()`
- Models first (`models/candidate.py`, new `models/profile_revision.py`), autogenerate, hand-review
- Downgrade drops the table + enum and the column — **destructive** (loses the audit trail and
  saved profile), noted in the docstring

#### Schemas (`schemas/profile.py` additions)

- `ProfileResponse` = `{candidate_id, structured_profile: StructuredProfile, updated_at,
  last_revision: {id, source, created_at} | None}`
- `ProfileUpdateRequest` = `{structured_profile: StructuredProfile, source_resume_id: uuid | None}`

#### Service — `services/profile_service.py`

- `diff_profiles(old: dict | None, new: dict) -> dict` — pure function, dotted-path scalar
  diffs + whole-list diffs, per the locked shape
- `get_profile(session) -> ProfileResponse` — via the single-candidate convention; 404 when
  no candidate or `structured_profile` is null
- `save_profile(session, payload) -> ProfileResponse`:
  1. resolve candidate (reuse `get_or_create_candidate`)
  2. if `source_resume_id` given: load resume → 404 if missing, verify `candidate_id` matches;
     its `draft_profile` is the comparison baseline
  3. decide revision(s) per the locked rules above; write `profile_revision` rows
  4. persist `structured_profile`, return response
- `get_resume_draft(session, resume_id) -> DraftProfileResponse` — 404 unknown resume,
  409 (`ResumeDraftUnavailableError`) when `draft_profile` is null

#### Router — `routers/profile.py` (new) + `routers/resume.py` (one route)

- `GET /api/profile` → `ProfileResponse`
- `PATCH /api/profile` → `ProfileResponse`
- `GET /api/resume/{resume_id}/draft` → `DraftProfileResponse` (reuses response schema; no LLM)

#### Errors (`core/errors.py`)

- `ProfileNotFoundError` → 404
- `ResumeDraftUnavailableError` → 409 (resource exists, wrong state — matches #3's convention)

#### Config

- No new settings, no `.env.example` changes

### Frontend

#### Dependencies (justified per frontend standards)

- `react-hook-form` + `zod` — mandated for forms (validate on submit/blur, per-field error slots)
- `@tanstack/react-query` — mandated for server state (profile query/mutations, invalidation)

#### API layer (`lib/api/`)

- Fix `apiFetch` to omit the hardcoded JSON `Content-Type` for `FormData` bodies (multipart upload)
- Add: `uploadResume`, `extractResume`, `getResumeDraft`, `getProfile`, `patchProfile`
- Regenerate `lib/api/schema.d.ts` via `npm run generate:api` after the backend lands —
  no hand-written API types

#### Hooks (`hooks/`)

- `useProfile` — query; 404 mapped to a null "no profile yet" state
- `useResumeDraft` — draft query for review mode
- `useSaveProfile`, `useUploadAndExtract` — mutations; upload+extract chained, then navigate

#### UI primitives (`components/ui/`, seeded from `BackendStatus` patterns)

- `badge` (success/warn/ai variants), `button`, `input`, `textarea`, `field`
  (label + control + error slot), `card`

#### Feature components (`components/features/`)

- `ResumeUploadForm` — file picker, 413/415/422 error display, progress → extract → navigate
- `ProfileReviewForm` — full editable form over `StructuredProfile`; repeatable subsections
  (experience, projects, education, certifications, awards, extra sections, links, skills);
  add/remove/reorder entries; zod-validated per the backend schema
- `AiExtractedBadge` — "AI-extracted" highlight per the locked rendering rule
- `MergeDiffPanel` — re-upload review: per-field keep-current (default) / take-draft choice,
  "take all" action, explicit save
- `SaveStatus` — aria-live save/revision confirmation ("Saved — revision recorded")
- Array-heavy sections may need subcomponents to stay under the ~200-line component limit

#### Pages

- `/` — hero + `ResumeUploadForm` (replaces placeholder); after upload+extract → `/profile?resume=<id>`
- `/profile` — one page, three modes:
  - **first review** (`?resume=<id>`, no saved profile): draft loaded via the draft endpoint,
    all fields flagged AI-extracted, editable; Save = first PATCH (upsert)
  - **edit** (saved profile): form bound to `useProfile`, Save = PATCH (`manual_edit`)
  - **merge** (re-upload triggered from this page): `MergeDiffPanel`, Save = PATCH with
    `source_resume_id` (`reupload_merge`)
- `Providers` client component (QueryClientProvider) mounted in the root layout
- **Next 16 caveat:** consult `node_modules/next/dist/docs/` before writing pages/forms
  (per `frontend/AGENTS.md` — conventions may differ from training data)

### Tests

Backend (pytest, DB-backed via `clean_tables` — add `profile_revision` to its truncate list):

- `test_profile_endpoints.py` — GET → 404 before first save; first PATCH with
  `source_resume_id` creates profile + `ai_extraction` revision (+ second `manual_edit`
  revision only when submitted ≠ draft); later PATCH → single `manual_edit` revision with
  correct dotted-path diff; PATCH with `source_resume_id` → `reupload_merge`; unknown resume
  → 404; resume without draft → 409 on draft fetch; malformed body → 422; no-change PATCH →
  empty-diff revision row; `last_revision` populated in responses
- `test_profile_diff.py` — pure unit tests: nested scalar diff, list replace, no-op → `{}`,
  old-value nulls for additions

Frontend: no test runner installed — gates are `npm run lint` + `npm run build` (strict TS).

## Doc impact

- `docs/guide/02-upload-and-profile.md`: mark review/edit + revision audit as shipped (#4);
  document GET/PATCH semantics, the draft endpoint, merge flow, and revision-source meanings
- `docs/architecture.md`: ER diagram — remove/annotate deferred `preferences` + `completeness`
  columns (prefs live in `structured_profile`); confirm `profile_revision` shape matches the
  enum; re-render with `node scripts/render-diagrams.mjs`
- No `.env.example` changes; `lib/api/schema.d.ts` regenerated as a build artifact

## Definition of done

- `ruff check . && ruff format --check . && pytest` green in `backend/`
- `npm run lint && npm run build` green in `frontend/`
- Migration `0004` generated, reviewed, included in the same change
- Acceptance met: every field editable, every correction lands in `profile_revision`,
  re-upload never overwrites without an explicit merge save
- Docs + diagrams updated per above; new deps justified (see frontend section)

## Out of scope (later issues)

Candidate-scoped APIs / candidate CRUD (owner decision 2026-08-31: considered, deferred —
revisit with multi-profile work in v2),
revision-history viewer UI (fast-follow — data is recorded, read UI comes later),
conversational gap-fill (#5), embeddings/matching (#6+), separate `preferences` weights column
(with matching).
