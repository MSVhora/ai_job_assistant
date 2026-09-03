# Issue #11 — Priority weighting UI + README + demo

**Status:** Done (2026-09-03). Demo GIF + screenshot and the GitHub checkbox hygiene
close-out deferred to the owner (see Open questions).
**Tracks:** GitHub issue #11 (Day 10, Week 2)
**Plan of record:** [v1-implementation-plan.md](v1-implementation-plan.md) §4 (`preferences` jsonb sketch), §6 (API surface), §7 (dashboard spec), §8 Day 10; [UI plan](v1-ui-implementation-plan.md) §6.5 ("Priority slider (#11): role-fit ↔ company-fit; changing it re-weights ranking")
**Depends on:** Issues #1–#10 (done). #10 stored `role_fit`/`company_fit` on `match` specifically so this slider re-weights without any LLM call.

---

## Carry-over review: what of this issue already exists

Re-verified against the code on 2026-09-03:

| Checkbox | State | Resolution |
|---|---|---|
| Priority-weight slider wired into ranking | Not present — no slider in `frontend/` (no `components/ui/slider.tsx` either); weights fixed via `MATCH_WEIGHT_*` Settings; `GET /api/matches` has no `priority` param | Lands here |
| Dashboard per §7 spec (search seeded from profile, filters, source badges, expandable rationale) | Landed in #7–#10: `SearchForm` seeds location/country/salary from profile preferences, `MatchFilterBar` + sort, badges on `MatchCard`, accessible rationale disclosure | Verify + close out; only the slider is missing |
| README walkthrough + screenshot/GIF; `.env.example` documented | `.env.example` documented in #10 (weights block notes the slider hand-off); README (64 lines) has quickstart + doc links but no walkthrough section or demo asset | Lands here (see the demo-asset open question) |
| Navigation away during background runs doesn't break them | Landed in #7: run is a FastAPI `BackgroundTasks` job with status in `job_search`; `RunBanner` polls via TanStack Query and explicitly says the page can be left | Carry-over close-out — verify only, no new work |

## Cross-issue sweep: gaps the original draft missed

Full review of issues #1–#10 scope (plans + code + docs) found the original draft accurate
but incomplete. All gaps are absorbed into this plan:

| # | Gap | Where it lands |
|---|---|---|
| 1 | Displayed-score mismatch: with a custom priority the ordering follows a computed blend but `MatchCard` shows the stored default-weights `final_score` — number static while order changes reads as broken UX | Decision row "effective score in the response" + tests |
| 2 | Priority × sort interaction unspecified (what happens with `sort=vector_score`/`posted_at`? what if `MATCH_WEIGHT_*` changed after matches were stored?) | Decision row "priority × sort interaction" + guide note |
| 3 | Stored-preferences read path unrobust: draft said "strips/clamps" without deciding 422-vs-clamp or what an invalid stored JSONB does | Decision row "stored preferences validation" + tests |
| 4 | Plan-of-record §6 API surface table never gains the new endpoint | Doc impact |
| 5 | `docs/guide/README.md` "Planned: priority weighting … issue #11" line never flips to landed | Doc impact |
| 6 | Frontend PATCH failure handling unspecified (standards: no silent failures) | Frontend scope |
| 7 | Closed issues #2–#10 have all four checkboxes unticked in their GitHub bodies (work is done — plans marked Done, code landed — the bodies were never updated); #1 and #10 are fine | Hygiene decision (owner call) |
| 8 | Issue #12 (buffer: seed data, error states, rate-limit backoff) is still open — boundary not stated, inviting scope creep | Out of scope |

## Goal

The priority-weight slider (role-fit ↔ company-fit) re-weights the dashboard ranking live,
per profile, with zero LLM calls — riding on the sub-scores #10 stored in `match`. The
weight persists per profile (the plan-of-record's deferred `preferences` jsonb column
lands here). README gets a real walkthrough + demo asset. Dashboard is verified against
§7 and the nav-away behaviour against the acceptance criteria.

**Acceptance (issue):** dashboard matches §7 spec; first successful match achievable in
minutes.

## Locked decisions (proposed — owner sign-off before build)

| Decision | Choice | Rationale |
|---|---|---|
| Re-weighting is read-time | `GET /api/matches` gains optional `priority` (float 0–1, role↔company). The sort key is computed in SQL from stored sub-scores: `CASE WHEN role_fit IS NOT NULL THEN w_v*vector_score + w_r*role_fit/10 + w_c*company_fit/10 ELSE vector_score END`; the stored `final_score` column stays the default-weights snapshot written at score time | The whole point of storing the sub-scores in #10: re-weighting is a view concern — no writes, no re-scoring, no LLM. Custom-weight sorts scan ≤ a few hundred rows (same no-index rationale as v1 pgvector) |
| Slider → weights mapping | `w_v` fixed from `Settings.match_weight_vector` (0.4); remaining mass splits by the slider: `w_r = (1-w_v)*priority`, `w_c = (1-w_v)*(1-priority)`. Default `priority = match_weight_role_fit / (match_weight_role_fit + match_weight_company_fit)` = 0.667, which reproduces the current 0.4/0.4/0.2 defaults exactly | One knob with stable semantics ("how much do I care about the employer vs the role"); default position is byte-identical to today's ranking |
| Effective score in the response | When a custom `priority` reorders, the response's `final_score` field carries the request's effective sort score (the stored column is untouched). At default priority it equals the stored snapshot, so `MatchCard` needs no change. Alternative rejected: a separate `effective_score` field — one more field to keep in sync for a single consumer | Ordering and the displayed number must agree or the slider looks broken; honest data preserved in storage, view reflects what was ranked |
| Priority × sort interaction | `priority` only affects `sort=final_score` (the default); `sort=vector_score`/`posted_at` ignore it. When the effective priority equals the Settings default, ordering uses the stored `Match.final_score` unchanged (fast path, zero drift). Caveat documented in the guide: editing `MATCH_WEIGHT_*` in `.env` after matches exist does not retroactively reorder at the default slider position — it applies on the next score-write or once the slider moves off default | Avoids surprising interplay between sort modes and the snapshot; keeps the no-op path byte-identical to today |
| Weight persistence | The plan-of-record's deferred `profile.preferences JSONB` column lands (migration `0012`), validated by a pydantic `StoredPreferences {priority: float 0–1}`. `GET /api/matches` without an explicit `priority` uses the profile's stored value, falling back to the Settings default | §4 sketches `preferences (jsonb) — weights (role vs company)`; the architecture note said it "lands with the matching work that consumes it" — that is now. Naming note: this is the *view* preference; resume-derived prefs remain `structured_profile.preferences` (column comment documents this) |
| Stored preferences validation | Write path (`PATCH …/preferences`): pydantic `ge=0, le=1` → 422 on violation, no clamping (the frontend range input can't exceed bounds anyway). Read path: parse with `extra="ignore"` (future preference keys don't 500 old deploys); invalid/missing stored value → fall back to the Settings-derived default, never a 500 from junk in the JSONB | Backend re-validates regardless of client; a corrupt stored blob must degrade to defaults, not break the dashboard. Resolves the draft's ambiguous "strips/clamps" |
| Persisting the slider | New `PATCH /api/profiles/{profile_id}/preferences` (service function, 404 guard) — deliberately NOT part of `ProfileUpdate`/`profile_revision` | A slider wiggle is a view preference, not profile content: no revision-audit spam, no embedding refresh, no match re-scoring. Debounced (~400 ms) from the frontend |
| Slider UI | `PrioritySlider` feature component (labelled `<input type="range">`, `aria-valuetext` like "60% role fit / 40% company fit", Tailwind `accent-*` styling) rendered with the filter bar; change updates the matches query key immediately (live reorder) and debounces the PATCH; switching profiles resets the slider to that profile's stored value | §7 spec wording "priority-weight slider (role-fit ↔ company-fit)"; keeps accessibility rules (label, value announcement). Domain semantics live in the feature component — no generic `components/ui/slider.tsx` needed (amends the UI plan's primitive list; owner flag) |
| Slider persistence failures | The debounced PATCH failure surfaces as a toast ("couldn't save the preference — ranking reflects this session only"); the slider keeps its local position and the next change retries | No silent failures per the async-UI standard; a failed save must not silently revert or block sliding |
| Unranked postings under the slider | Rows without sub-scores keep `final_score = vector_score` regardless of priority — the slider reorders only the re-ranked top N relative to each other and to unranked rows via their fixed vector scores | Honest data: there is no company signal for postings the LLM never scored; inventing one would fake precision |
| README | New "How it works" walkthrough (upload → review → gap-fill → search → ranked matches) linking the guide chapters; quickstart stays on top | README currently jumps from quickstart to internal docs; the walkthrough is what "first successful match achievable in minutes" needs |
| Demo asset | Screenshot(s) of the jobs dashboard committed to `docs/assets/` and embedded in README. Owner records the animated GIF (screen capture needs a human at the controls); I can stage the app state and capture static screenshots headlessly if Playwright/Chromium is acceptable to install | Flagged as an open question — see below |
| New dependencies | None for the backend. Playwright only if the owner opts into headless screenshot capture | |
| GitHub checkbox hygiene | Closed issues #2–#9 (and #4, #6, #7, #8, #9 — all show 4 unticked boxes) get their boxes ticked with a one-line comment pointing at the plan's Done marker + landing commit; owner opts in or out | Plans are already the record of truth, but unticked boxes on closed issues undercut the showcase; ticking is cheap |
| Checkbox close-outs | §7-spec items and nav-away: verified, then marked done in the issue with pointers to the code/tests that prove them | |

## Scope

### Backend

**Migration `0012_add_profile_preferences`**
- `profile` + `preferences JSONB null`; docstring documents the deferred-column landing
  (plan §4), the view-vs-content distinction, and that no backfill is needed (absent =
  use server default). Downgrade drops the column
- Update `docs/instructions/database-postgres.md` JSONB guidance note if needed
  (`priority` is read per-profile, never filtered on — likely no change)

**Models/schemas**
- `Profile.preferences: Mapped[dict | None]`
- `schemas/profile.py`: `StoredPreferences {priority: float, ge=0, le=1}` with
  `extra="ignore"` (validation decided above), `ProfileUpdate` unchanged, `ProfileResponse`
  gains `preferences: StoredPreferences | None`
- `schemas/matching.py`: `MatchQueryParams.priority: float | None (ge=0, le=1)`

**Services**
- `matching.py`: `priority_weights(priority) -> (w_r, w_c)` pure helper; the read query's
  `sort=final_score` ordering switches to the computed blend when `priority` (explicit or
  stored) differs from the default; zero-LLM, zero-write; `MatchResponse.final_score`
  carries the effective sort score when reordering (decision row above); stored-preferences
  load with invalid-JSONB fallback
- `profile_service.py`: `update_preferences(session, profile_id, payload)` +
  preferences loading for the matches path (fallback chain: explicit param → stored →
  Settings default)

**Router**
- `PATCH /api/profiles/{profile_id}/preferences` (404 guard, response model)

### Frontend

- Regenerate `schema.d.ts`: `npm run generate:api` (backend running)
- `hooks/use-matches.ts`: priority joins the query key; preferences mutation hook
  (`useUpdatePreferences`) with error toast on failure
- `PrioritySlider.tsx`: labelled range input, live value text, debounced persistence,
  disabled while profile loads, resets on profile switch
- `MatchList.tsx`: render the slider beside the filter bar; pass priority through the
  matches query; restore position from the profile response
- `RunBanner`/`SearchResults`: no changes expected — §7 items verified only

### README + docs

- README: walkthrough section + screenshot embed(s)
- `docs/plans/v1-implementation-plan.md`: §4 amendment note (preferences column lands
  with #11); **§6 API surface gains `PATCH /api/profiles/{id}/preferences`**; §7/§8 stay
  as-is
- `docs/architecture.md`: ER gains `profile.preferences`; the deferred-preferences note
  becomes landed state → re-render diagrams
- `docs/guide/03`: slider section (what it re-weights, what it can't, persistence,
  read-time semantics, effective-score display, `MATCH_WEIGHT_*` caveat); README pointers
- `docs/guide/README.md`: "Planned: priority weighting … issue #11" moves to the landed
  list with the issue link
- `.env.example`: note that the slider overrides `MATCH_WEIGHT_ROLE_FIT`/`COMPANY_FIT`
  per profile at read time (server defaults still apply to API-only consumers)

### Tests

- `tests/test_matches_endpoint.py` extended: `priority` reorders fixtures with known
  sub-scores (hand-built rows: role-heavy vs company-heavy postings); response scores
  non-decreasing in returned order under a custom priority; invalid values → 422; stored
  preference used when param absent; explicit param beats stored; `sort=vector_score` /
  `posted_at` ignore `priority`
- `tests/test_profile_endpoints.py` extended: PATCH preferences (404, 422 out-of-range,
  response shape); structured-profile save does not touch preferences; preferences PATCH
  creates no `profile_revision`
- `tests/test_matching.py`: `priority_weights` math (0, 1, default, clamped inputs); sort
  expression blend correctness via service-level rows; stored-preferences fallback on
  invalid/missing JSONB; effective default priority keeps the stored-order fast path
- Migration up/down via `migrated_database`
- Frontend: `npm run lint && npm run build`

### Doc impact

Listed in the README + docs section above; also update the issue-10 plan's out-of-scope
line? No — #10's plan stays as written (its "out of scope" correctly predicted this work).

## Definition of done

- `ruff check . && ruff format --check . && pytest` green in `backend/`
- `npm run lint && npm run build` green in `frontend/`
- Migration `0012` generated, reviewed, applied; up/down verified
- Live check: moving the slider visibly reorders matches (company-heavy posting rises as
  the slider moves), displayed scores move with the order, reload keeps the position, and
  no LLM/token activity occurs while sliding (server logs quiet)
- README walkthrough + screenshot(s) committed; GIF by owner (or explicitly deferred)
- GitHub checkbox close-out: #11's boxes ticked with pointers; #2–#9 hygiene executed or
  explicitly deferred by owner
- Docs updated; diagrams re-rendered

## Out of scope (this issue)

Priority affecting re-rank *selection* or ingestion (slider is read-time only), per-search
weight presets, weighting other signals (salary/recency), ATS scorer (v1.1), saved
searches. **Issue #12 (buffer: seed data, error states, rate-limit backoff) stays a
separate open issue** — nothing from it is pulled in here.

## Open questions (owner)

1. **Demo asset** — README walkthrough landed; the animated GIF needs a human at the
   controls (headless Playwright screenshots offered, not opted into).
2. **GitHub checkbox hygiene** — tick closed issues #2–#9's boxes (recommended) or leave
   plans as the sole record. Not executed yet.
