# Issue #30 — Search initiation stepper (one source per run) + profile country persistence fix

**Status:** Done (branch `v3/30-search-stepper-and-country-fix`, commit 2439ab3)
**Tracks:** GitHub issue #30 (milestone `v3`, scope addition — beyond the original M1–M3 breakdown)
**Plan of record:** [v3-implementation-plan.md](v3-implementation-plan.md) §4 M3 frontend (extends it); §6 issue table gains #30
**Depends on:** #28 (merged — `SourceFilterDecl` declarations + backend options validation), #29 (merged — `SourceFiltersForm`, ui primitives, vitest), #24/#25 (merged — profile-scoped searches, `?profile=` URL param)
**Blocks:** nothing

---

## Goal

Two pieces of work in one issue:

1. **Search initiation UX.** Today `/jobs` initiates searches through a "Global
   configuration" dialog (`GlobalConfigModal`) that packs profile selection, a
   multi-source toggle list (`SourceMultiSelect`), per-source query cards and the
   search form into one modal — sources behave like a persistent global setting
   (`selectedSources`) rather than a per-run decision, and one submit fans a single
   run out across every selected source. This issue replaces it with an explicit
   **Start search button → 4-step wizard**: (1) pick a profile, (2) pick **one**
   source, (3) fill in common details prefilled from the profile, (4) fill the
   source's declared advanced filters and initiate. One run targets exactly one
   source; parallel runs on different sources remain possible.

2. **Country persistence bug.** Users report the gap-fill chat keeps asking for
   `contact.country` even after they gave it. Root cause (confirmed in code): the
   **frontend profile edit form has no `country` field at all**. The chat path is
   correct — `gap_fill.py:_apply_answers` sets `profile.contact.country` and
   persists the JSONB (backend/app/services/gap_fill.py:225–227). But any manual
   save in `ProfileReviewForm` PATCHes a `structured_profile` rebuilt by
   `toProfilePayload()` without `country`, the backend's `ContactInfo` defaults the
   missing field to `None`, and `save_profile()` replaces the whole JSONB — wiping
   the chat-set value. The missing branch in `ProfileEditor.applyGapFill()`
   (frontend/components/features/profile/ProfileEditor.tsx:64–98) means the form
   never even knows about the chat-applied country. Next `missing_fields()` call
   flags `contact.country` again → the chat re-asks, forever.

## Locked decisions

| Decision | Choice | Rationale |
|---|---|---|
| UI shape | `GlobalConfigModal` + `GlobalConfigTrigger` are **replaced** by a "Start search" button in the sidebar footer opening a 4-step wizard modal (`SearchStepperModal`): profile → source → details → advanced filters + initiate. Steps validate before advancing; back navigation preserves entered values | Issue body: button-initiated stepper. "Global configuration" implied sources are a persistent global setting; a run is really a one-shot decision, so the wizard makes the mental model honest |
| One source per run (backend contract) | `JobSearchRequest.sources: list[str] \| None` becomes `source: str` (**required exactly one**). `source_queries` stays a `dict[str, SourceQuerySpec]` but a model validator enforces its keys ⊆ `{source}` (empty dict = use `payload.query` only). `_selected_sources()` / `_validate_queries()` / `run_search` simplify accordingly; response shapes unchanged | Owner decision (2026-09-15): one source per run, no multi-source batch runs. Backend refuses what the UI no longer expresses — client-side-only enforcement would violate "never trust the client". Single-user self-hosted app, no external API consumers → breaking change is acceptable |
| Parallel runs allowed | **No guard** against overlapping runs (owner decision). `JobsPageClient.searchId: string \| null` becomes `searchIds: string[]`; a `RunBanner` renders per active run; `SearchResults` stays bound to the most-recent started run (`selectedSearchId`). Dismissing a finished banner removes only that id; switching profile clears all | Owner decision (2026-09-15). The current code already never deduped concurrent runs — codifying "parallel OK" is the no-extra-work option; the only real change is banner-list state |
| Common fields (step 3) | Search title, include skills, exclude skills, location, country, posted within (duration), min salary, **max salary (new in UI)**, results wanted — prefilled from the profile: `title`/`skills`/`exclude` from the stored per-source spec (`profile.search_queries.queries[source].*` fallback `seedSpec(structured)`), `location` from `preferences.target_location ∥ contact.location`, `country` from `contact.country` (now reliably persisted after the fix below), `salary_min`/`salary_max`/`currency` from `preferences` | Issue body lists these as shared fields that must prefill from the profile. `salary_max` reaches an existing backend field (`JobSearchRequest.salary_max`, Adzuna `salary_max` param) that the current form never sends |
| Per-source fields (step 4) | Rendered by the existing `SourceFiltersForm` from the selected source's `filters` declarations (from #29), plus the regenerate-with-AI action for the selected source (`SearchQueriesCard` reused with `sources=[selectedSource]`) | Zero per-source components; new sources get their filter forms automatically per v3 D5 |
| Step 2 source cards | Single-select list of enabled sources; each card shows the existing source badge (**Official API** / **Third-party scraper**) and is disabled when `is_configured` is false, with a "missing API key" hint | Frontend standards: badges always visible on cards; a known-unconfigured source would burn the run |
| Rebuild matches placement | `RebuildBanner` (currently rendered inside `GlobalConfigModal`, guide ref: `docs/guide/03-job-discovery-and-matching.md:111`) moves to the `/jobs` sidebar column, below the run banners | The #29 scope addition already relocated read-time controls (profile selector, priority) out of the dialog; the modal's disappearance needs an explicit new home, not an orphaned feature |
| Profile selector duplication | Sidebar `ProfileSelector` (from #29) **stays**; wizard step 1 opens preselected on the active `?profile=` profile and confirms/changes it | Consistent with #29: both views always show the same track |
| Country fix — frontend only | Add `country` to `profileFormSchema` contact (optional `"" \| 2-letter`, lowercased), `toFormValues()`, `toProfilePayload()`; add a `contact.country` branch to `applyGapFill()`; add a Country input to `ProfileReviewForm` next to Location (frontend/components/features/profile/ProfileReviewForm.tsx:104). **No backend change** (`ContactInfo.country` already exists, validated lowercased 2-letter), **no migration** (JSONB field) | The bug is entirely the frontend form model dropping the field on save; the backend round-trips it fine once the payload includes it |
| Payload mapping | `toSearchRequest()` becomes single-source: `{ profile_id, source, source_queries: { [source]: { title, skills, exclude, options } }, country, location, results_wanted, max_days_old, salary_min, salary_max, salary_currency }`; `SourceMultiSelect` and the `sources` array logic are removed | Mirrors the backend contract above; `options` coercion from #29 (`coerceOptions`) is reused unchanged |
| Types | Regenerate `lib/api/schema.d.ts` via `npm run generate:api` after the backend schema change; `JobSearchRequest` TS type flows from it | Backend request shape changed — hand-editing generated types is forbidden |
| No new deps | Nothing added; everything builds on react-hook-form + zod + existing `ui/` primitives (#29 shipped select/checkbox/accordion) | Stepper is a state machine + layout, not new capability |
| Stepper a11y | Steps announced via `aria-current="step"` on the active step indicator; step content wrapped in a labeled region; per-issue error summaries marked `role="alert"`; the wizard keeps the existing `Modal` focus-trap/escape behavior | Frontend standards: keyboard-navigable modals, `aria-live` for async status; a multi-step form without step announcements is a screen-reader dead end |

## Scope

### Backend (`backend/app/`)

- `schemas/job_search.py`:
  - `JobSearchRequest`: replace `sources: list[str] | None` with
    `source: str` (required, `min_length=1`); keep `source_queries` but add a model
    validator: every key must equal `source` (unknown key → 422).
  - No DB change — `job_search.query` is an opaque JSONB echo of the request;
    old rows keep the old shape but nothing parses them back
    (`run_search` receives the payload object directly). Verify the status
    endpoint does not re-read `query` before deleting the field.
- `services/ingestion.py`:
  - `_selected_sources()` resolves the single `payload.source` (unknown →
    `UnknownJobSourceError`, not enabled → `JobSourceNotEnabledError`, quorum
    error `NoJobSourcesConfiguredError` disappears as a code path for explicit
    requests — keep it for the `source is None` defensive branch only if any is
    left, else delete).
  - `_validate_queries()` / `run_search()` iterate one source; keep the
    `SourceOutcome` list-shaped `results` so `RunBanner` rendering is unchanged.
- No router signature changes (`POST /api/jobs/search` body shape only);
  no migration; `.env.example` unchanged.

### Frontend — stepper (`frontend/components/features/jobs/`)

- `SearchStepperModal.tsx` (new): step state machine (1–4, back/next),
  per-step validation gate, renders step content from the shared form
  (`FormProvider` reusing `SearchFormValues` + `makeSearchFormSchema` scaled to
  `sources=[selectedSource]`).
- Step 1 `ProfileStep`: `ProfileSelector` seeded with the active profile id.
- Step 2 `SourceStep` (new): single-select source cards (badge, configured
  state); replaces `SourceMultiSelect.tsx` (deleted).
- Step 3 `CommonDetailsStep`: title / include skills / exclude skills (the
  per-source query fields from `SearchQueriesCard`, with the regenerate action
  for the selected source) + location / country / posted within / min salary /
  **max salary** / results wanted. Prefill effect moves here from
  `SearchForm.tsx:73–111` (same re-seed triggers: profile switch, regenerate
  refresh).
- Step 4 `AdvancedFiltersStep`: `SourceFiltersForm` (declared options) +
  review summary (profile, source, query line) + "Start search" submit calling
  the single-source `toSearchRequest()`.
- `GlobalConfigModal.tsx` / `GlobalConfigTrigger` deleted; sidebar footer gains
  a "Start search" button (same gradient styling) + relocated `RebuildBanner`.
- `JobsPageClient.tsx`: `searchIds` state + banner list; per-profile reset
  clears all ids; `selectedSearchId` (latest started run) drives `SearchResults`.
- `RunBanner.tsx`: `searchId` prop becomes required `string` (no null state —
  the parent only renders banners for known ids).
- `search-form-schema.ts`: `SearchFormValues.sources: string[]` → single source
  context passed by the wizard; `toSearchRequest()` single-source with
  `salary_max`; delete `SourceMultiSelect`-related helpers.

### Frontend — country fix (`frontend/lib`, `frontend/components/features/profile/`)

- `profile-schema.ts`: `contact.country` in `profileFormSchema` (optional;
  `""` or lowercase 2-letter pattern), `toFormValues()`
  (`profile.contact.country ?? ""`), `toProfilePayload()`
  (`country: trimmed === "" ? null : lowercased 2-letter`).
- `ProfileEditor.tsx` `applyGapFill()`: add the
  `touched.has("contact.country")` branch syncing `next.contact.country`.
- `ProfileReviewForm.tsx`: Country input (label "Country code", hint
  "ISO 3166-1 alpha-2, e.g. in", badge `ai` like Location, error slot).

### Tests

Backend (`backend/tests/`):
- Request validation: two `source_queries` keys → 422; `source` mismatched with
  a key → 422; unknown source → 400; disabled source → 409-equivalent
  `JobSourceNotEnabledError` mapping unchanged; single-source happy path
  (fixture `_selected_sources` → one source; `_validate_queries` with empty
  `source_queries` + `query` set).
- Existing multi-source tests updated/removed to the new contract.

Frontend (`frontend/` — vitest from #29):
- `search-stepper` schema/payload: single source reaches `source` +
  `source_queries[source]`; `salary_max` reaches the payload; empty/unset
  advanced filters omitted; a cleared field disappears.
- Prefill: title/skills/exclude seed from stored per-source spec then
  `seedSpec()`; salary/location/country seeds from preferences/contact.
- `profile-schema.test.ts`: country round-trip — `toFormValues` keeps a
  2-letter country; `toProfilePayload` lowercases; blank → `null`; schema
  rejects >2 chars / non-alpha.
- Stepper gating: cannot advance from step 1 without a profile, step 2 without
  a source; source badges rendered; unconfigured source disabled.
- Banner list: two started runs render two banners; dismissing one keeps the other.

### Gates

- Backend: `ruff check . && ruff format --check . && pytest` green.
- Frontend: `npm run lint && npm run build && npm test` green in `frontend/`.
- `npm run generate:api` run after the backend schema change (types + API
  client stay generated, never hand-edited).
- Live check: start two runs back-to-back on different sources — both banners
  poll and each stores under its own search id; a chat-set country survives a
  manual profile save; the wizard prefills country from the profile without
  re-asking.
- Docs: `docs/guide/03-job-discovery-and-matching.md` — initiation-flow section
  rewritten (button → stepper, one source per run, parallel runs), the "Global
  configuration dialog" reference (:111) updated to the sidebar placement;
  `docs/guide/02-upload-and-profile.md` — manual-edit field list gains Country;
  `docs/architecture.md` — sequence diagram + API row now show the single
  `source` payload and parallel-run behavior. Re-run
  `node scripts/render-diagrams.mjs` (sequence diagram payload changes).
- No migration; `.env.example` unchanged.

## Risks

| Risk | Mitigation |
|---|---|
| Breaking `JobSearchRequest` change orphans anything that still sends `sources` | Only the frontend calls it; frontend + types regenerated in the same change; old stored runs' `query` echo is write-only (verified before field deletion) |
| Parallel run banners stack and clutter the page | Banners render only while a run is active/unseen; each is dismissible; they live in the existing `self-start` column and scroll with it |
| Country still empty for profiles that never got it extracted/asked | Wizard step 3 keeps a required country field with prefill — after the fix the chat answers persist, so re-asking converges; remain empty → user fills the field once |
| Prefill clobbers user edits when profile updates mid-wizard | Re-seed triggers unchanged from today (profile switch / regenerated queries), memoized as in `SearchForm.tsx`; user-entered step 3 values stay until an explicit profile change |
| Rebuild-matches discoverability drops after the modal removal | Sidebar placement is directly under the Start search button; guide updated in the same change |

## Out of scope (this issue)

- Any guard against concurrent runs, run cancellation, or run queuing (owner: parallel runs OK).
- Scheduling / recurring searches.
- Changes to the stored `profile.search_queries` schema or the LLM query-builder prompt.
- `MatchFilterPanel` / match read-side filters.
- New job sources or new `SourceFilterDecl` types.
- LinkedIn country handling (`geo_id` stays a manually filled advanced filter).
- Data repair migration for already-wiped `contact.country` values — users re-answer one chat turn; nothing else was stored from that field.
