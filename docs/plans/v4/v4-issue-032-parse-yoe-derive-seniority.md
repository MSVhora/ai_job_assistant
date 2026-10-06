# Issue #32 — Parse years of experience; derive seniority fallback (M1)

**Status:** Done (merged — branch `v4/32-parse-yoe-derive-seniority`; implementation notes: deterministic parser as planned; gap-fill derivation gated on a non-empty `applied` list so no-op turns stay no-ops and don't half-persist; legacy rows with seniority set but `seniority_source: None` are treated as user-set and never re-derived; YOE shown in the profile header subtitle ("~N yrs experience") in addition to the read-only review-form field; fixture `VALID_PROFILE` switched to fixed past dates so derived values are time-independent)
**Tracks:** GitHub issue #32 (milestone `v4`, Phase A / M1)
**Plan of record:** [v4-search-relevance-plan.md](v4-search-relevance-plan.md) Problem 2
**Depends on:** #31 (merged — `profile_digest_parts()` shared helper, `ensure_queries_fresh` background regeneration, full-profile query context)
**Blocks:** Nothing directly; #33 (term precedence) and #34 (Adzuna dialect) consume the enriched query context, #37/#38 consume the digest. (Note: issue #31's header said "#32 = Adzuna dialect", but GitHub #32 is this YOE issue and #34 is the Adzuna dialect — numbering confirmed via `gh issue list`.)

---

## Goal

Experience dates are stored verbatim strings (`schemas/profile.py` `ExperienceItem.start_date/end_date`), so nothing can reason about "8 years, senior backend": not query building (#34/#33), not the embedding digest, not the rerank prompt (#38). Predictions has `preferences.seniority` only when the user set it or the LLM found it stated; `final_score` has no seniority signal; LinkedIn's classic experience filter is gone.

This issue:

1. Adds `years_of_experience` to `StructuredProfile`, derived **deterministically** from the verbatim date strings (no LLM involvement).
2. Fills `preferences.seniority` from YOE as a **fallback** when the user hasn't set it, using band thresholds from `Settings`; user-set values always win; derived values are marked and correctable in the review UI.
3. Stores both in the `StructuredProfile` JSONB — **no migration** — and re-derives opportunistically on every extraction / profile save / gap-fill apply (the round-trip problem below makes server-side re-derivation mandatory, not just backfill).
4. Feeds YOE/seniority into the shared `profile_digest_parts()` (which streams into the query-builder context via `_candidate_context`); the rerank prompt stays out of scope (hook point documented for #38).

## Locked decisions

| Decision | Choice | Rationale |
|---|---|---|
| YOE computation | **Deterministic Python parser over the verbatim date strings, not the LLM.** Deliberate deviation from the issue wording ("the LLM derives it from date strings during the existing extraction call") | The verbatim-string storage exists precisely so a parser can do this (research: `profile_extraction.py:28-43` tells the LLM to copy dates verbatim and never invent numbers). A parser is unit-testable against the DoD's exact cases (empty dates, partial ranges, future-proof formats), needs no prompt change or `PROFILE_PROMPT_VERSION` bump, and carries zero extraction-regression risk — while still satisfying "no extra round-trip" |
| YOE semantics | Career span: earliest parseable `start_date` → latest `end_date` (or now for `is_current`), truncated to whole years | Per-job summation double-counts overlapping roles; span is simple, deterministic, and adequate for seniority bands |
| Where YOE lives | Top-level `StructuredProfile.years_of_experience: int \| None = None` (not on `ExperienceItem`) | It's a profile-level synthesis, not a per-role fact; additive JSONB field, old rows validate with the default (no migration) |
| Seniority bands | `Settings` scalars: `seniority_band_mid: int = 2`, `seniority_band_senior: int = 5`, `seniority_band_staff: int = 8`, `seniority_band_principal: int = 12`; mapping < 2 → `junior`, 2–4 → `mid`, 5–7 → `senior`, 8–11 → `staff`, 12+ → `principal` | Issue example says "entry" and "staff/lead" but `SeniorityLevel` (`schemas/profile.py:13-24`) has no `entry` and requires a single deterministic value — `junior` / `staff` are the mapped choices; deviations noted here. Flat scalars fit the existing Settings pattern (no dict-typed setting precedent in `core/config.py`) |
| Provenance | New `Preferences.seniority_source: Literal["user", "derived"] \| None = None`, **fully server-managed** — never added to the frontend zod schema or payload | Additive JSONB (old rows validate fine with `None`). Survives `model_dump` round-trips and gap-fill's direct JSONB writes. Server-managed beats client-echoed: "never trust the client" |
| User-set vs derived on save | No provenance echo needed from the client; `save_profile()` compares payload vs stored: payload seniority set and **differs from stored** → user change → `seniority_source = "user"`; payload seniority `None` → derive, source `"derived"`; payload seniority equal to stored and stored source `"derived"` → stay derived, **re-derive from the new YOE** (value may change) | The frontend form round-trips the whole `structured_profile` and strips unknown fields (`toProfilePayload`), so a stored provenance flag can't rely on the client sending it back. Legacy rows (seniority set, source `None`, pre-dating derivation) are treated as user-set — the user-set-wins contract holds |
| Re-derivation points | Run `apply_derived_fields()` in: `extract_resume_profile` (post-parse, beside `_enrich_link_labels`), `create_profile`, `save_profile` (before the diff/revision computation), and gap-fill `_apply_answers` | Derivation must happen before `content_changed`/diff so revisions show the derived fields; the form round-trip strips server-derived values, so every server write path must re-derive or the fields would silently vanish on the next save |
| Gap-fill chat | `missing_fields()` skips `preferences.seniority` when it is set with source `"derived"` — the chat asks only what it truly can't infer | Owner decision 2026-09-16. The derived value remains visible and correctable in the review form (derived badge); user-set/legacy values keep asking only when actually `None` |
| Gap-fill seniority answers | When a turn applies `seniority`, `_apply_answers` sets `seniority_source = "user"` | A chosen answer is user-set by definition; derivation must never overwrite it afterwards |
| Embedding digest | Add a `Years of experience: N` part to `profile_digest_parts()` (only when YOE is not None); embed text is NOT kept byte-identical this time | Plan-of-record explicitly feeds the digest, and the seniority line already varies with derived values. Vectors are re-embedded opportunistically on the next save/apply via the existing refresh path; untouched profiles keep their (still valid, YOE-less) vectors until edited — same opportunistic semantics as the issue's backfill clause. Bytes-stability contract in `embedding.py:23-29` is deliberately amended; noted there |
| Query-hash wave | Accepted: new `years_of_experience` + `seniority_source` keys enter `compute_queries_input_hash` (it hashes the full structured_profile dump), so the next save regenerates stored specs once | Same accepted trade-off as #31's hash-inputs decision; single-user app, one background generation wave |
| Rerank prompt | **Out of scope — hook documented for #38.** `matching._profile_digest()` (`matching.py:390-411`) is a stale duplicate of `profile_digest_parts()` and will not see YOE until #38 (ideally by switching it onto the shared helper) | Rerank is #38's file; touching its duplicated digest here would be a drive-by refactor into another issue's hot path |
| Review UI | Seniority select gets a field-level "Derived from experience" badge + hint when `seniority_source == "derived"`, and stays editable (editing → next save marks it user-set). YOE itself is display-only (hint: "Estimated from your experience dates") and **not** in the zod payload — the server always recomputes it | Issue DoD requires the derived seniority be visually distinct and correctable. YOE is a pure function of the experience dates the user can already edit; an editable YOE field would let payload values disagree with the parser |

## Scope

### Migration

None. `StructuredProfile` lives in the `profile.structured_profile` JSONB
(`models/profile.py:20`); both new fields are additive pydantic fields with
defaults, so old rows `model_validate` cleanly. Per plan-of-record: promote to
real columns only if SQL filtering on them is ever needed.

### Backend (`backend/app/`)

- **New `services/profile_derivation.py`**:
  - `parse_years_of_experience(experience: list[ExperienceItem]) -> int | None`
    — tolerant parsing of verbatim strings ("Mar 2021", "2019", "2019 - Present",
    "January 2018 – March 2021", month names / year-only / "Present" / "Current");
    ignores unparseable items; returns `None` if nothing parseable; future
    start dates are clamped/ignored (future-proof formats).
  - `derive_seniority(yoe: int) -> SeniorityLevel` — band lookup from Settings.
  - `apply_derived_fields(profile: StructuredProfile) -> bool` — computes YOE,
    stores it, and fills `preferences.seniority` **only** when it is `None` or
    `seniority_source == "derived"` (creating `preferences` if absent);
    marks/maintains `seniority_source = "derived"` for filled values; returns
    whether anything changed.
- `schemas/profile.py`: `StructuredProfile.years_of_experience: int | None`;
  `Preferences.seniority_source: Literal["user", "derived"] | None = None`.
  Note: `ProfileResponse.missing_fields` (computed in `profile_service.py:148`
  from `gap_fill.missing_fields()`) automatically stops listing seniority once
  a derived value is stored — the two paths stay consistent because both read
  the same JSONB.
- `core/config.py`: the four band scalars above (pattern: existing flat
  `Annotated[int, Field(ge=…)]` scalars).
- `services/profile_extraction.py`: call `apply_derived_fields(result.data)`
  after `_enrich_link_labels` (line ~103), before persisting the draft. No
  prompt change; `PROFILE_PROMPT_VERSION` stays `profile_prompt_v5`
  (test `test_profile_extraction.py:19` keeps its exact-string assertion).
- `services/profile_service.py`:
  - `create_profile()` (~line 214): run `apply_derived_fields` on the payload's
    structured profile before persisting + hashing.
  - `save_profile()` (~lines 250–310): after `model_validate`, apply the
    payload-vs-stored seniority rule from the locked-decisions table, then run
    `apply_derived_fields` — both **before** the content-diff/revision
    computation — so derived fields land in the revision and in the
    embedding/refresh + query-hash scheduling that already follow.
- `services/gap_fill.py`:
  - `missing_fields()` (line 137): skip the seniority entry when set with
    source `"derived"`.
  - `_apply_answers()`: set `seniority_source = "user"` when seniority is
    applied; run `apply_derived_fields` on the post-apply profile (fills YOE;
    seniority is user-set). The turn-complete → `ensure_queries_fresh` hook
    from #31 then sees the derived fields via the hash automatically.
- `services/embedding.py`: new digest part in `profile_digest_parts()`
  (seniority line at ~38-39 already flows through unchanged); update the
  byte-stability docstring to record the amendment date.

### Frontend

- `npm run generate:api` after the backend schema change (structured_profile
  types regenerate).
- `frontend/lib/profile-schema.ts`: no payload change (YOE and
  `seniority_source` stay server-managed); `toFormValues` reads
  `years_of_experience`/`seniority_source` off the response for display.
- `ProfileReviewForm.tsx` (~237-242): seniority `SelectField` gets a
  `"Derived from experience"` badge + hint when derived (accessible label on
  the badge so screen readers announce it); an optional read-only
  "Years of experience" display field (hint: "Estimated from your experience
  dates"). Picking a value in the select overrides — the next save marks it
  user-set. No new components beyond the existing field/badge primitives.

### Tests (backend `tests/`)

- **New `test_profile_derivation.py`**:
  - Parser: empty dates → `None`; partial range ("2019" start only, current);
    "Mar 2021" alone; month-name ranges; year-only; future start dates
    (clamped); multi-role overlap → span, not sum; unparseable strings
    skipped; ISO dates.
  - Bands: exact boundaries at each Settings threshold; band override via
    settings monkeypatch.
  - `apply_derived_fields`: fills seniority when absent; re-derives when
    source is `"derived"` and YOE changed; **never** touches user-set
    (`"user"`) or legacy (`seniority` set, source `None`) values; creates
    `preferences` when absent.
- `test_profile_schema.py`: new fields validate / default to None.
- `test_profile_extraction.py`: draft carries YOE + derived seniority;
  `parse_version` assertion unchanged.
- `test_profile_endpoints.py`: `create_profile` persists derived fields;
  save with changed dates re-derives (revision diff shows the derived change);
  manual seniority edit flipped from derived → user-set and never overwritten
  on the next save; `missing_fields` excludes a derived seniority; response
  exposes `seniority_source`/`years_of_experience` through `structured_profile`.
- `test_gap_fill.py`: seniority answer → source `"user"`; derived seniority
  excluded from `missing_fields` (both the direct call and the turn flow).
- `test_embedding.py`: digest contains `Years of experience: N` when present,
  nothing when None.
- `test_query_builder.py`: `_candidate_context` output includes the YOE line
  (fake prompt capture); hash reacts to the new keys (already covered —
  sensitivity comes for free with the schema change).

## Gates

- Backend: `ruff check . && ruff format --check . && pytest` green (in
  `backend/`).
- Frontend: `npm run lint && npm run build` + `npm run generate:api`.
- No migration — stated explicitly in the change (JSONB additive only).
- `.env.example`: new `SENIORITY_BAND_*` settings documented.
- Docs: `docs/guide/02-upload-and-profile.md` (auto-estimated YOE, derived
  seniority badge, chat skips derived seniority), `docs/architecture.md`
  derivation flow addition. Re-run `node scripts/render-diagrams.mjs` only if
  a diagram actually changes.

## Risks

| Risk | Mitigation |
|---|---|
| Verbatim date strings are a zoo (locales, "5 yrs", seasons) | Parser whitelists common formats and returns `None` on anything else — degraded gracefully to no YOE/seniority signal, never a wrong one; fixture-driven unit tests |
| Career-span undercounts real experience (gaps between roles) | Span is the conservative choice; bands are Settings-tunable; per-job summation revisitable later without schema change |
| Derived seniority silently changes query specs + embeddings for every saved profile | Expected and bounded: exactly one regeneration/re-embed wave per profile edit, via the paths #31 landed; single-user app |
| User confusion about a seniority value they "never entered" | Field-level derived badge + hint in the review UI; first edit of the field converts it to user-set permanently |
| Legacy profiles with seniority set but no provenance | Treated as user-set — derivation never overwrites them |

## Out of scope (this issue)

- Rerank prompt consumption of YOE/seniority — #38 (which should reconcile
  `matching._profile_digest` with the shared `profile_digest_parts`).
- Promoting YOE/seniority to SQL columns (no SQL filtering need yet).
- One-off re-embed/re-generate across profiles that are never edited again.
- LLM-assisted YOE ("8 years" stated in a summary/headline but not in dates).
- Any change to `StoredSearchQueries`, router response models, or the
  `JobSource` connector layer.
