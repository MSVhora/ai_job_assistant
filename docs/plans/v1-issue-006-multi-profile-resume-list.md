# Issue #6 (part 1) — Multi-profile Support + Resume List + Provenance

**Status:** Done (2026-09-01)
**Tracks:** GitHub issue #6 (first chunk — "flows end-to-end without dead ends")
**Plan of record:** [v1-implementation-plan.md](v1-implementation-plan.md) §4, §6, §7 —
**deviation:** multi-profile ("Data Analyst vs PM tracks") was deferred to v2; owner pulled it
into v1 on 2026-09-01 (two real tracks: Senior Android Developer / Senior Software Engineer).
The §1 deferral table carries a dated amendment.
**Depends on:** Issues #2–#4 (done)

---

## Goal

A candidate maintains **multiple named profiles** ("Senior Android Developer",
"Senior Software Engineer" — different cuts of one career, matched against different jobs).
Each profile is born from a resume's AI draft, evolves independently (edits, gap-fill,
merges), and keeps its own revision audit. The home page lists profiles and uploaded
resumes; from a resume draft the user merges into a selected profile or saves it as a new
one.

Concept model (owner-aligned): **resume = immutable artifact** with a 1:1 AI draft
(what the AI read); **profile = living working copy** seeded from a draft, absorbing many
drafts over time (draft→profile is 1:N, resume→profile is N:1 over time). "Active" means
*the selected profile*, never a manually toggled resume.

**Acceptance:** user can maintain two named profiles from one resume, edit each
independently, merge a newer resume into either, and every change lands in the right
profile's `profile_revision` trail.

## Locked decisions

| Decision | Choice | Rationale |
|---|---|---|
| Multi-profile in v1 | **Yes** — owner decision 2026-09-01; plan-of-record deferral amended | Real personal use case; data model decision must precede matching (issues #7+) so `match` keys off profile, not candidate |
| Profile storage | New `profile` table: `{id, candidate_id, name, structured_profile jsonb, source_resume_id, created_at, updated_at}` | Profile is a first-class entity; name gives tracks identity; provenance moves here from candidate |
| Existing data | **Discarded** (owner: test data) — migration `0006` backfills nothing; `candidate.structured_profile` + `candidate.source_resume_id` dropped | Owner-approved destructive migration; `0005` itself stays untouched (never edit applied migrations) |
| `profile_revision` | Re-parented: `profile_id` FK (NOT NULL) replaces `candidate_id`; existing revision rows deleted in `0006` (documented, owner-approved) | Audit belongs to the profile it describes |
| API surface (breaking) | `GET /api/profiles`, `POST /api/profiles` (name + structured_profile + optional source_resume_id), `GET/PATCH /api/profiles/{id}`, `DELETE /api/profiles/{id}`; old `/api/profile` removed | Pre-release, single consumer ships in the same change |
| PATCH semantics | Body `{name?, structured_profile?, source_resume_id?}`; `structured_profile` present → content save + revision row(s) (server-decided sources, same rules as #4); name-only → rename, no revision | Rename is metadata, not profile content; revision sources stay server-derived |
| Profile creation | Always from a reviewed draft (StructuredProfile requires content) via POST; "Save as new profile" prompts for a name | Keeps the "never auto-save" guarantee; empty profiles are meaningless |
| First save revisions | Same rules as #4, now on create: `ai_extraction` baseline (+ `manual_edit` when the submitted profile differs from the draft); later saves `manual_edit` / `reupload_merge` | Consistent audit semantics across single/multi-profile |
| Delete profile | Service-level cascade: delete its revisions, then the profile; 204 | Revisions FK is RESTRICT; file artifacts are untouched (resumes outlive profiles) |
| "Active profile" | Client-side selection (route param); no is_active column | Server state would imply matching semantics that don't exist yet; matching later takes explicit profile_id |
| Resume list | `GET /api/resumes` (plural rename from in-flight work) with `has_draft` + `source_profile_names` (which profiles this resume seeded) | Provenance is now 1:N — a resume can seed several tracks; badge list replaces single "profile source" flag |
| Resume paths | Plural `/api/resumes*` (carried from in-flight work; pre-release rename) | Standards compliance |
| Review routing | `/profile?resume=<id>` (no profiles → first-review w/ name prompt; profiles exist → target chooser) and `/profile?profile=<id>&resume=<id>` (merge into that profile); `/profile?profile=<id>` (edit) | Reuses existing mode machinery; the chooser is where "merge into X" vs "save as new" gets decided |

## Scope

### Backend

- Migration `0006_create_profile_table_reparent_revisions`: create `profile`; re-parent
  `profile_revision` (`profile_id` NOT NULL FK, indexed; `candidate_id` dropped; existing
  rows deleted); drop `candidate.structured_profile` + `candidate.source_resume_id`.
  Downgrade destructive (profiles/revisions unrecoverable) — noted in docstring
- Models: new `Profile`; `ProfileRevision.profile_id`; `Candidate` back to bare
- Schemas: `ProfileCreate {name, structured_profile, source_resume_id?}`,
  `ProfileUpdate {name?, structured_profile?, source_resume_id?}`,
  `ProfileResponse {profile_id, name, structured_profile, updated_at, source_resume_id,
  source_resume_filename, last_revision?}`, `ProfileSummary {profile_id, name, updated_at,
  source_resume_filename}`; `ResumeSummaryResponse.source_profile_names: list[str]`
- `services/profile_service.py` rework: `list_profiles`, `get_profile(profile_id)`,
  `create_profile` (name + initial revision logic vs draft),
  `save_profile(profile_id, payload)` (content save w/ revisions, rename w/o,
  provenance update on `source_resume_id`), `delete_profile` (cascade revisions)
- `services/resume_service.list_resumes`: `source_profile_names` via join
- Router `routers/profile.py`: `/api/profiles` CRUD; 404s via `ProfileNotFoundError`
- Tests: rework `test_profile_endpoints.py` → profile-scoped; new multi-profile cases
  (one draft → two profiles with independent revisions; merge into one leaves the other
  untouched; delete cascades); update `test_resume_list.py` (source_profile_names);
  `clean_tables` gains `profile, profile_revision`

### Frontend

- `lib/api`: profiles CRUD + types; `ResumeSummary` updated; regenerate `schema.d.ts`
- Hooks: `useProfiles`, `useProfile(id)`, `useCreateProfile`, `useSaveProfile(id)`,
  `useDeleteProfile`, `useRenameProfile(id)`
- Home page: **Profiles** section (name, updated date, "from <resume>.pdf" provenance,
  open/delete) above the resumes list
- `/profile` page modes: edit (`?profile=`), first-review with name prompt (`?resume=`,
  no profiles), target chooser (`?resume=` + profiles exist: merge into X / Y / save as
  new), merge (`?profile=&resume=`); rename inline in edit mode header
- `ProfileReviewForm` gains a name field for first-save; `MergeDiffPanel` unchanged;
  `ResumeList` shows `source_profile_names` badges

### Doc impact

- `docs/plans/v1-implementation-plan.md`: §1 deferral row annotated (multi-profile → v1)
- `docs/guide/02-upload-and-profile.md`: multi-profile flow, profiles/resumes lists,
  renamed paths
- `docs/architecture.md`: ER gains `profile` (revisions re-parented, candidate slimmed);
  sequences use `/api/profiles`; re-render diagrams
- `lib/api/schema.d.ts` regenerated

## Definition of done

- `ruff check . && ruff format --check . && pytest` green in `backend/`
- `npm run lint && npm run build` green in `frontend/`
- Migration `0006` generated, reviewed, applied (destructive — owner-approved)
- Two-profile lifecycle verified end-to-end on the running stack
- Docs + diagrams updated; container rebuilt

## Out of scope (this issue)

Per-profile matching (issues #7+ key off profile_id — model ready), gap-fill (#5),
resume deletion, per-resume re-extract button, profile copy/duplicate.
