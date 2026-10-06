# Issue #6 (part 2) — Profile Flow End-to-End Polish

**Status:** Implemented (2026-09-01) — automated gates green; owner e2e acceptance run pending
**Tracks:** GitHub issue #6 (second chunk — loading/error/empty states, retry paths, acceptance run)
**Plan of record:** [v1-implementation-plan.md](v1-implementation-plan.md) §8 Week 1 (Day 5 buffer) + [v1-ui-implementation-plan.md](v1-ui-implementation-plan.md) §5–§6
**Depends on:** Issues #2–#5 and issue #6 part 1 (multi-profile, done 2026-09-01)
**Audit basis:** async-state/error-surfacing audit of the working tree, 2026-09-01

---

## Goal

Close the remaining issue-#6 checkboxes: every async view has complete loading/error/empty
states, no silent failures or dead ends, failures surface actionable messages, and the
acceptance run passes — fresh `.env` + `docker compose up` → usable profile in <30s on the
free Gemini tier.

Audit found 4 dead ends and 8 smaller gaps. This issue fixes all of them.

## Locked decisions

| Decision | Choice | Rationale |
|---|---|---|
| Error surfacing model | **Inline-first** (error slots/cards per component) + **sonner toast** as global safety net via `mutationCache`/`queryCache` `onError` handlers | UI plan §4 already plans the toast primitive and §5 mandates "errors surface inline + toast, never swallowed"; inline alone missed delete-profile and gap-fill-start failures |
| New dep: `sonner` | **Adopt** | Already the planned primitive in the UI plan §4; not scope drift |
| Draft-missing dead end | Resume rows with `has_draft: false` render an **"Extract profile"** action (`POST /api/resumes/{id}/extract`) instead of linking to `/profile`; the `/profile?resume=` 409 state gets the same action | Kills the "retry forever on a deterministic 409" and the "re-upload creates a duplicate row" trap in one move; extract is already idempotent |
| Extract failure during upload | `use-upload-and-extract` keeps the uploaded `resume_id` and throws a typed error carrying it; the form shows "Extraction failed — extract again" which re-runs extract **without re-uploading** | Upload succeeded server-side; retrying from scratch duplicates the resume row |
| Query retry defaults | `QueryClient` `defaultOptions`: queries retry once, **never on 4xx**; mutations never retry | TanStack's default 3× retry burns ~10s before a deterministic 404/409 error renders |
| `client.ts` 422 handling | Parse FastAPI's **array** `detail` into a readable message; map 413/415/422/502/503 to human text per UI plan §5; add per-request timeout (default 30s, 120s for upload/extract) | `HTTPValidationError` currently falls through to generic "API error 422 on …" |
| Backend retry/repair | Keep the one validation-repair pass; **add one transport retry with short backoff on 429/5xx** in `adapters/llm.py` (`generate` only) | Free Gemini tier rate-limits aggressively; acceptance (<30s) needs the second attempt; adapter-level retry is the sanctioned place |
| Actionable LLM errors | `LLMExtractionError` / `LLMGapFillError` details include a **safe cause hint** ("rate limited — retry shortly", "timeout", "output failed validation after repair") — never raw provider text or prompt content | Issue checkbox: "failures surface actionable messages"; backend standard: never log/echo prompts or keys |
| Extraction stays synchronous | No BackgroundTask/polling migration in this issue | Single-user, <30s target, UI plan defers polling to ingestion/scoring runs (§5); changing the run model now adds risk for no user-visible gain |
| Gap-fill start failure | Surface `turn.error` in the **idle branch** of `GapFillChat` (alert + retry = press Start again) | Currently a failed initial turn silently returns to the intro with no explanation |
| Gap-fill vs unsaved edits | On applied turn, **merge** applied fields into current form values; never `form.reset` whole profile | Editor currently discards concurrent manual edits on every applied answer |
| BackendStatus | Migrate to `useQuery(["health"])` + `refetchInterval` 30s | UI plan §5 calls for the `["health"]` key; stale-green badges hide a dead backend |
| FirstReview duplicate error | Show the create error **once** (SaveStatus slot only; name field keeps its own validation error) | Same message rendered twice |
| TargetChooser empty case | Explicit "no profiles yet — save as new" message when the merge list is empty | Functional but silent edge |

## Scope

### Frontend

- `app/providers.tsx`: `QueryClient` defaults (retry once, skip 4xx; mutations no retry);
  `queryCache`/`mutationCache` `onError` → sonner toast (deduped); add `<Toaster>` to layout
- `lib/api/client.ts`: array-`detail` parsing, status→message mapping (413/415/422/502/503),
  timeout via `AbortSignal.timeout` with per-call override; typed
  `ExtractionFailedError extends ApiError { resumeId }` thrown by extract
- `hooks/use-upload-and-extract.ts`: invalidate `["resumes"]` on success; chain errors carry
  `resumeId`; expose `retryExtract(resumeId)` reusing the stored id
- `hooks/use-resume-draft.ts` / `use-profiles.ts`: no retry on 404/409 (covered by defaults;
  verify)
- New hook action `useResumeList`: extract mutation wired from `ResumeList` rows with
  `has_draft: false` (pending spinner on the row, error inline under the row)
- `ResumeList.tsx`: no-badge rows → "Extract profile" button (not a link)
- `ProfilePageClient.tsx` / `MergeMode.tsx`: draft-fetch 409 → dedicated card ("Extraction
  didn't complete") with Extract action; distinguish from other errors
- `ProfilesSection.tsx`: render `deleteProfile.error` inline (dialog stays open, message
  above buttons); success closes dialog
- `GapFillChat.tsx`: error alert rendered in idle branch; error copy includes recovery hint
- `ProfileEditor.tsx`: `onApplied` merges fields into current form values
  (`form.setValue`/`reset` with current-values merge), no full reset
- `FirstReview.tsx`: drop error from the name `Field` slot (keep client validation errors
  there; server error only in `SaveStatus`)
- `TargetChooser.tsx`: explicit empty-list message
- `BackendStatus.tsx`: rewrite on `useQuery(["health"], { refetchInterval: 30000 })`
- `components/ui/toast.tsx`: thin sonner wrapper styled with the app's tokens

### Backend

- `adapters/llm.py`: `generate()` — one retry, short backoff (~1s), on 429/5xx
  transport errors only; log both attempts with duration/token counts
- `services/profile_extraction.py` / `gap_fill.py`: `LLMExtractionError` /
  `LLMGapFillError` details carry the safe cause hint (rate limit / timeout /
  validation-after-repair)
- `core/errors.py` + `main.py`: add `RequestValidationError` handler → 422 with a single
  readable string `detail` (client parses strings today); fix `ProfileNotFoundError`
  default detail ("profile not found")

### Tests

- Backend: adapter retry test (429 → second call succeeds; 429 twice → `LLMError`);
  extraction error detail asserts cause hint; `RequestValidationError` handler shape via
  `httpx.AsyncClient` (malformed UUID body → 422 string detail)
- Frontend: no test framework in the stack — verification is the manual e2e checklist below

### Doc impact

- `docs/guide/02-upload-and-profile.md`: retry/extract-again affordances, what each error
  state means, re-extract from the resume list
- `docs/architecture.md`: no schema/API-surface change (extract endpoint already exists) —
  no diagram re-render needed; note the adapter-level retry in the error-handling paragraph
  if one exists

## Definition of done

- Backend: `ruff check . && ruff format --check . && pytest` green
- Frontend: `npm run lint && npm run build` green; `sonner` added to `package.json`
  (justification: UI plan §4 planned primitive)
- No silent failure paths remain: audit's 4 dead ends + 8 gaps each have a filed fix above
- Manual e2e checklist on the running stack:
  1. Fresh `.env` from `.env.example`, `docker compose up`, upload → review → save →
     gap-fill → saved profile, **<30s on free Gemini tier**
  2. Extraction forced to fail (invalid key): resume row shows Extract action; clicking
     it after fixing the key completes without a duplicate row
  3. Delete-profile with network interrupted: inline error, form/list state intact
  4. Gap-fill start with LLM down: visible error in intro state
  5. Backend stopped mid-session: BackendStatus flips to down within ~30s

## Out of scope (this issue)

BackgroundTask extraction + status polling (revisit if extraction exceeds ~30s in
practice), revision history drawer, resume deletion, per-resume re-extract *button in the
review UI* (list + 409-card entries cover it), toast-driven success notifications beyond
the global safety net.
