# Issue #53 — Evidence & achievement review: API, audit trail, `/evidence` and `/evidence/review` UI (Week 2)

**Status:** Proposed — for owner review
**Tracks:** GitHub issue #53 (milestone `v6`, branch `v6/45-evidence-review-ui-audit`)
**Plan of record:** [v6-implementation-plan.md](v6-implementation-plan.md) §5.2–5.3, §10, §12 (private provenance)
**Depends on:** #50 (sync API), #51 (items/notes), #52 (drafts)
**Blocks:** #54–#59 (approved achievements are the only input downstream)

---

## Goal

Give the user the human-in-the-loop gate (hard requirement 2): connect GitHub and manage repos, refresh history, add notes, then review, edit, merge, split, confirm metrics and **approve** achievements — every change audited in `achievement_revision`. Largest frontend issue of the milestone.

**Pre-agreed split if it runs long:** 45a = backend review service + endpoints + tests; 45b = both UI pages. Do 45a first regardless.

## Locked decisions

| Decision | Choice | Rationale |
|---|---|---|
| Approval gate | Approve requires ≥ 1 evidence link and no unresolved `needs_confirmation` metrics; service-enforced, 409 with a reason otherwise | Hard req. 1–2 |
| Audit | Every mutation writes `achievement_revision(source, diff)` — `manual_edit`, `merge`, `split`, `metric_confirmation`, `status_change`, `ai_extraction` (written at draft creation in #52's service call or lazily here) | Mirrors `profile_revision` |
| Editing approved rows | Allowed; re-embeds, recomputes `derived_from_private`, writes a revision; the row stays `approved` | Avoids re-approval churn on typo fixes |
| Evidence changed after a refresh | Approved achievements whose linked items changed get `evidence_stale_at` and an "Evidence updated — re-review" badge; never silently altered | Refresh safety (owner decision) |
| Merge | Manual (user selects ≥ 2); system **proposes** pairs with cosine ≥ 0.90 and overlapping dates within the same project; merged row is `origin='merged'`, sources archived with a revision pointing to the merge | Plan §4.5: never auto-merge |
| Split | Duplicate with evidence subset assignment; both rows drafts | Needed for chunks that bundled two efforts |
| Metric confirmation | Per-metric action: "confirm as written" or "edit value"; stored `verified='user'` with timestamp in the revision | Metrics only if evidence or user-confirmed |
| Employer mapping | Per repo (scope-level) in the `/evidence` repo table, available once a repo has synced (dates known). Dropdown lists experience entries from the candidate's profiles (company + dates) plus **Personal / open source**. Pre-filled as *Suggested* when the repo's authored-commit date range overlaps exactly one employment range by > 50 % of the repo's active span; otherwise blank. The user confirms once per repo; the choice applies to all of that repo's achievements. Unmapped repos are not blocking: their achievements are treated as **projects**, never as employer experience, and the review page shows "N repos unmapped" | Plan §5.3; a wrong mapping would put a claim under the wrong employer |
| Private marking | "Private repo" badge + the note "Generated from private repository data" on any evidence/achievement card with `is_private`/`derived_from_private`; filter chip "Private-derived" | Owner decision 2026-10-02 |
| Opt-in location | Per-repo **enable toggle** in the `/evidence` repo table, *before* any sync reads that repo. Repos discovered later (by Refresh or Full re-sync) appear **disabled** with a "new" badge; refresh never enables anything on its own. The first time a **private** repo is enabled the disclosure modal appears (what text goes to your LLM provider, what never does, that derived outputs are marked) and `acknowledged_at` is stored; later private repos show a one-line confirm. Fetching from GitHub stays local; text reaches the LLM only at extraction, so the extraction estimate modal repeats the private-chunk count as the second checkpoint | Owner question 2026-10-02 |
| Refresh UX | Two buttons: **Refresh** (incremental) and **Full re-sync** (confirm dialog explaining it re-reads everything and creates new drafts only) | Owner requirement |
| Bulk approve | On the **Draft** tab of `/evidence/review`: button "Approve all fully-evidenced (N)" opens a preview list (title, evidence count) with checkboxes pre-ticked, then confirms. Eligible = draft, ≥ 1 evidence link, **no** pending metric confirmations, no redaction-placeholder flag, not stale, and **not private-derived** (those always need an individual look). Each approval writes a `status_change` revision with `bulk=true`. Shown after extraction completes; undo = **Unapprove** (`approved→draft`), which removes it from the knowledge base again | Fights rubber-stamping (risk #8) while saving time on clean items |
| UI reuse | `components/ui` (`Modal`, `Field`, `Checkbox`, `Badge`, `Card`, `Select`, `Textarea`, `toast`), the run-banner polling pattern, review layout from `components/features/profile` | Plan §10.2 |

## Scope

### Backend (`backend/app/`)

- `services/achievement_review.py`: `edit`, `approve`, `reject`, `archive`, `merge`, `split`, `confirm_metric`, `link_evidence`/`unlink_evidence`, `propose_merges(candidate_id)`, `mark_stale_after_sync(candidate_id)` (called at the end of a sync/rebuild: compares item `content_hash` against what each approved achievement last saw), `diff_achievement(old, new)` (shared field-level diff helper style as `profile_diff`).
- `routers/achievements.py`: `GET /api/achievements` (status/project/private/stale filters), `GET/PATCH /api/achievements/{id}`, `POST …/approve|reject|archive|merge|split|confirm-metric`, `POST/DELETE …/evidence`, `GET …/revisions`, `GET /api/achievements/merge-proposals`, `PATCH /api/evidence/github/scopes` extended (employer mapping already stored, now validated against the candidate's profiles' `experience`).
- All bodies pydantic-validated; ids checked for ownership; transitions validated by a small state table (`draft→approved|rejected`, `approved→draft` (unapprove), `approved→archived`, `rejected→draft`, no others).

### Frontend (`frontend/`)

- Routes: `app/evidence/page.tsx` (connect status, repo opt-in table with private badge / content level / employer select / disclosure modal, sync banner with budget + paused/resume info, Refresh + Full re-sync, notes & links panel, "Ingest resume entries" action, extraction estimate + confirm modal) and `app/evidence/review/page.tsx` (tabs Draft / Approved / Rejected / Needs attention; card list ranked by impact × evidence strength; detail drawer: STAR editor, tags, metrics with confirm buttons, evidence side panel with source links and quotes, revision history, merge proposals).
- `components/features/evidence/*`, `components/features/achievements/*`; `lib/api/` functions and TanStack Query hooks in `hooks/`; nav entry in `SiteHeader`.
- Regenerate `frontend/lib/api/schema.d.ts` from the running backend.

### Tests

Backend (Postgres): approve without evidence → 409; approve with pending metric → 409; every mutation writes exactly one revision with the right source/diff; editing an approved row re-embeds and recomputes `derived_from_private` (fake embedder asserts a call); merge archives sources and links evidence union; split divides evidence; invalid transitions rejected; stale flag set by `mark_stale_after_sync` and cleared on re-review; merge proposals respect the 0.90 / same-project / date-overlap rule and never auto-apply; ownership 404s; bulk-approve excludes private-derived and unconfirmed items.
Frontend: `npm run lint && npm run build`; manual walkthrough checklist recorded in the PR (connect → opt in private repo with disclosure → sync → pause banner → extract with estimate → review → approve → refresh → stale badge).

### Standards from v5 (must hold from the first commit)

- **Lint/types:** ruff `ALL` and pyright strict pass with no new `noqa`; untyped third-party values are narrowed through small typed helpers (the pattern in `adapters/llm.py`); a `# pyright: ignore` needs a reason comment. Functions stay within the configured limits (args 6, branches 13, returns 8, complexity 14).
- **Coverage and layout:** the 90 % floor holds with `TEST_DATABASE_URL` set; new code ships with its tests in the mirrored folders (`tests/adapters/`, `tests/services/`, `tests/routers/`, `tests/db/`, `tests/core/`; recorded/golden suites in `tests/eval/`).
- **Config:** every new `Settings` field appears in `.env.example` (the settings↔env guard test fails otherwise); no `os.getenv`/`os.environ` and no provider SDK imports outside their one module.
- **API:** new routes keep `response_model` (binary downloads declare their media type instead), use only the CORS-allowed methods (`GET`, `POST`, `PATCH`, `DELETE`, `OPTIONS` — **never PUT**) and headers (`Content-Type`, `Accept`), raise `DomainError` subclasses (checked by `tests/core/test_error_contract.py`), and bound every list with the shared `pagination()` dependency and `X-Total-Count`.
- **Privacy:** no resume/evidence text, prompts, tokens or keys in logs (extend `tests/routers/test_logging_privacy.py` for the new flows); LLM calls log `cost_usd=`; outbound HTTP has an explicit timeout.
- **Schema (v5 #43 conventions):** every table with `updated_at` gets `create_updated_at_trigger(table)` / `drop_updated_at_trigger(table)` from `app.core.migration_helpers`; every FK is indexed and declares its ON DELETE (CASCADE owned children, RESTRICT identity/audit, SET NULL provenance); constraints and indexes are named (`uq_`/`ix_`/`fk_`/`ck_`); bounded scalars get a `CHECK`; `alembic check` is clean and the schema audit (`tests/db/test_schema_standards.py`) reports nothing; downgrade works. Revision numbers continue from `0022`.

### Standards from v5 (must hold from the first commit)

- **Gate:** `npm run lint && npm run format:check && npm run typecheck && npm test && npm run build` in `frontend/`; Prettier (width 100) with the Tailwind plugin.
- **Components ≤ 200 lines** (ESLint `max-lines` is an error in `app/` and `components/`): split into subcomponents and hooks from the start.
- **Types:** no `any`, no `!` on API data (use TanStack Query's `skipToken` for nullable ids); optional props are declared `?: T | undefined`; payloads omit empty keys instead of sending `undefined` (`exactOptionalPropertyTypes`, `noUncheckedIndexedAccess`).
- **Structure:** every route segment that fetches data has `loading.tsx`, `error.tsx` and `not-found.tsx`; all calls go through `lib/api` with regenerated types (`npm run generate:api`); read the Next 16 docs in `node_modules/next/dist/docs/` before using framework APIs.
- **Tests:** co-located Testing Library tests for every new component and hook, mocking at the `lib/api` boundary.

### Gates / docs

Backend + frontend gates green; `docs/guide/04-evidence-and-resume.md` completed (review workflow, private badges, refresh modes); screenshots under `docs/assets/`; `architecture.md` notes the audit trail and the approval gate.

## Risks

| Risk | Mitigation |
|---|---|
| Review fatigue ⇒ rubber-stamping | Ranking, bulk-approve restrictions, evidence quote beside every claim, per-metric confirmation |
| UI scope blows the week | Pre-agreed 45a/45b split; employer mapping and merge proposals can be delivered after core approve/edit |
| Revision diffs grow noisy | Field-level diffs only (like `profile_diff`), no whole-row snapshots |

## Out of scope

LLM-assisted merge, bulk edit, keyboard-shortcut review mode, exporting achievements, multi-user review.
