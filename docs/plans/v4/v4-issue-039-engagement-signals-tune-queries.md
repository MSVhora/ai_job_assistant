# Issue #39 — Engagement signals + on-demand tune-my-queries (M6 / Phase F)

**Status:** Planned (branch `v4/39-engagement-signals-tune-queries`, cut from `v4/milestone`)
**Tracks:** GitHub issue #39 (milestone `v4`, Phase F — feedback loop, Problem 10)
**Plan of record:** [v4-search-relevance-plan.md](v4-search-relevance-plan.md) Problem 10
**Depends on:** #31 (`queries_input_hash` guard — tuning must leave a matching hash),
#37 (`skill_hit` word-boundary SQL semantics — aggregation mirrors them),
#38 as merged (canonical matches; aggregation runs on live `match` rows so deduped
matches are counted once for free). No other hard dependencies.
**Blocks:** nothing in v4; applied/status tracking is explicitly its own future plan.

---

## Goal

Nothing records whether the user opened, saved on, or dismissed a match, and query
specs only change when manually regenerated hot. This issue adds (1) zero-effort
implicit signals, (2) one-click explicit signals, and (3) a manual "tune my
queries" action that feeds aggregated signal buckets to an LLM and rewrites the
profile's stored queries — without getting silently reverted by the #31 freshness
guard.

### Plan-of-record drift (flagged, not silently changed)

| Plan-of-record text | Reality | Resolution |
|---|---|---|
| "`saved_at` — the existing save/bookmark action" | **No save action exists** anywhere (no endpoint, no UI) | This issue builds save + dismiss endpoints and UI as "small card-menu additions"; not a reuse |
| "`clicked_apply_at` — fires when the user clicks through the external apply URL… the redirect/apply-link endpoint is the natural hook" | Apply links are raw `<a href={posting.url}>` client-side (MatchCard.tsx:144, JobDetailPanel.tsx:219); no server touchpoint exists | New server-side redirect endpoint becomes the hook |
| "cost-estimated like every batch op" via the wrapper | `estimate_cost` **does not exist** in `adapters/llm.py`; only per-call token logging + source-call caps | Tune returns/logs actual token usage; the confirm dialog states expected cost qualitatively. A token-price table is new surface — out of scope here |
| Plan lists `opened_count` / `dwell_ms` counters | Issue #39 scope narrows to `first_opened_at` only | Counters stay out ("later if needed"); `dwell_ms` needs new page-lifecycle instrumentation — skipped per "don't build new instrumentation" |

## Locked decisions

| Decision | Choice | Rationale |
|---|---|---|
| Signal write surface | One endpoint: `POST /api/matches/{match_id}/signals`, body `MatchSignalRequest {kind: MatchSignalKind}` where `MatchSignalKind = open \| save \| unsave \| dismiss \| undismiss` (StrEnum). Returns the updated `MatchResponse` | Five trivial mutations in one typed route keeps `routers/matches.py` thin and tests exhaustive over one surface; the response lets TanStack query cache update without a refetch round-trip. Idempotent server-side: `open/save/dismiss` set the column only if NULL (first-write-wins, `updated_at` untouched when no-op); `unsave/undismiss` NULL it back. `undismiss` must exist or dismissed rows are unrecoverable once the default list hides them |
| Apply-click hook | `GET /api/matches/{match_id}/apply` → records `clicked_apply_at` (if NULL), then 302-redirects to `posting.url`; 404 when the posting has no URL (both ends: 404 before recording) | The honest hook: the click literally transits the server — protects `clicked_apply_at` from JS failure and popup blockers, and keeps the timestamp trusted without trusting the client. It is a redirect, not a JSON route (documented response_model exception) |
| Open hook | **Frontend** fires `POST …/signals {kind: "open"}` once per detail-open (a `useRef` guard per open in `JobDetailPanel`'s mount effect, scoped to the match id); server remains idempotent anyway | Every JobDetailPanel mount is reachable from a match context (`JobsPageClient` passes the full `MatchResponse`), so `first_opened_at` needs no GET-side magic; a stray duplicate open is harmless |
| Schema | Migration `0020_add_match_engagement_signals`: four nullable `DateTime(timezone=True)` columns on `match` — `first_opened_at`, `clicked_apply_at`, `saved_at`, `dismissed_at`. No new indexes (single-user scale; `ix_match_profile_final_score` still serves the default sort) | Problem 10 item 4 word-for-word, minus counters. Downgrade drops the columns — signal timestamps are unrecoverable history (stated in docstring) |
| Default list semantics | `GET /api/matches` gains an optional `status: MatchListStatus` param (`active \| saved \| dismissed \| all`, default `active`) where `active` = `dismissed_at IS NULL`. Default behavior changes: dismissed matches disappear from the list | Dismissal that doesn't hide anything is a no-op; an explicit param keeps saved-only and graveyard views one param away. Sort order unchanged — within a bucket the existing sorts stand |
| Signal bucket definitions (prompt inputs) | Per profile: **positive** = `clicked_apply_at IS NOT NULL OR saved_at IS NOT NULL`; **negative** = `dismissed_at IS NOT NULL`; **weak** = all remaining matches (including never-opened). Aggregated terms per bucket: top-N titles, top-N normalized companies (by match count), and per-profile-skill hit counts (word-boundary, case-insensitive regex over `coalesce(title,'') \|\| ' ' \|\| coalesce(description,'')` — same `\m…\M` semantics as #37's `skill_score` SQL, implemented as one bulk SQL pass with a bound skill array) | The issue's exact bucket language ("clicked+saved vs never-opened vs dismissed"), sharpened: a dismissed match that was also saved bucketed negative — dismiss is the later, stronger act. Skill counting reuses #37 semantics instead of inventing a second matcher; joined on live `match` rows so #38's dedupe means no double counting |
| Aggregation caps | `tune_query_top_terms: Annotated[int, Field(ge=1)] = 10` (Settings) — max terms per category per bucket | Keeps the prompt bounded on token cost; 25-skill × 3-bucket × 10-term ceiling stays a few hundred prompt tokens |
| Tune endpoint | `POST /api/profiles/{profile_id}/tune-queries` (synchronous single LLM call, like the existing hot regen endpoint): aggregate → single `parse_structured` call (`_GeneratedQueries` schema, temperature **0.2** — evidence-driven, not variant-creative) → write `profile.search_queries` + set `profile.queries_input_hash = compute_queries_input_hash(current structured profile, enabled sources, declarations)` → return `SearchQueriesResponse`. LLM failure: stored queries and hash untouched (warning-logged, 502 raised) | Manual rewrite of the same machinery `regenerate_for_profile` uses, so per-source spec shape, validation, and serialization are identical. Writing the **current-inputs hash** (not clearing it) is the issue's "must overwrite the hash" clause: `ensure_queries_fresh` then sees a hit and will not clobber the tuned queries behind the user's back. Low temperature because tuning edits a working artifact; the hot 0.8 is for creative variants |
| Tune response & cost awareness | Response is plain `SearchQueriesResponse` (matches the regen endpoint shape); token usage logged server-side per standards. Cost awareness lives in the **frontend confirm step**: modal names the operation ("one Gemini Flash call, typically a few thousand tokens"), requires an explicit confirm, and the result toast shows the queries changed | No `estimate_cost` exists to reuse; adding a price table now would be invented pricing on one manual, confirm-gated call — the knob we actually need is the confirm step the issue asks for. Token-price estimation goes on the wrapper's own future list |
| API additions | `MatchResponse` gains `first_opened_at`, `clicked_apply_at`, `saved_at`, `dismissed_at` (all `datetime \| None`). Regenerate `openapi.json` + `schema.d.ts` | Signals are user-visible (saved/dismissed state drives card UI); exposing timestamps keeps save/dismiss state inspectable without extra endpoints. Additive/optional — safe for openapi-typescript |

## Scope

### Migration (`backend/alembic/versions/0020_add_match_engagement_signals.py`)

1. `op.add_column("match", ...)` × 4: `first_opened_at`, `clicked_apply_at`,
   `saved_at`, `dismissed_at` — `DateTime(timezone=True)`, `nullable=True`.
2. Downgrade: drop the four columns (loses signal history; docstring says so).
3. No data migration — no backfill is possible from anything already stored.

### Backend (`backend/app/`)

- `models/match.py`: four nullable `Mapped[datetime | None]` columns.
- `schemas/matching.py`: `MatchResponse` four new fields; new
  `MatchSignalKind`/`MatchSignalRequest`; `MatchQueryParams` gains `status`.
- `schemas/profile.py` (or a small `tuning.py`): tune response reuses
  `SearchQueriesResponse`; no new response models beyond that.
- `routers/matches.py`:
  - `POST /{match_id}/signals` → `matches.record_match_signal` (service).
  - `GET /{match_id}/apply` → redirect (302) to `posting.url`.
- `routers/profile.py`: `POST /profiles/{profile_id}/tune-queries` →
  `query_tuner.tune_for_profile`.
- `services/match_signals.py` (new, small): `record_match_signal(session, match_id,
  kind)` — resolve match + posting (404 on missing match / missing URL for apply),
  timestamp upsert per kind; `resolve_apply_target(session, match_id) -> str`.
- `services/query_tuner.py` (new):
  - `aggregate_signal_buckets(session, profile_id) -> SignalBuckets` — one SQL
    pass (match ⋈ job_posting, profile-scoped), skill hits via bound text-array +
    `regex_count ... 'i'` mirroring `matching.skill_score` branch semantics;
    returns top-N titles/companies per bucket + per-skill positive/weak/negative counts.
  - `tune_for_profile(session, profile_id)` — build prompt from
    `profile_digest_parts(profile)` + serialized buckets (compact line format,
    counts only — **never match/posting text tails**), one `parse_structured`
    (schema `_GeneratedQueries` from `query_builder`), validate per-source specs,
    then overwrite `profile.search_queries` + set the current-inputs hash
    (reusing `query_builder.compute_queries_input_hash` and the same enabled-source
    + declaration resolution `regenerate_for_profile` uses). No `session.commit()`
    (DbCommitMiddleware owns it).
- `services/matching.py` `list_matches()` / `_SORT_ORDERS`: honor the `status`
  param (a `dismissed_at IS NULL` predicate branch by default) — sort logic
  otherwise untouched.
- Untouched: connector layer, ingestion, scoring, `ensure_queries_fresh` guard logic.

### OpenAPI / types

- Regenerate `frontend/lib/api/schema.d.ts` from the running backend after the
  `MatchResponse` + new routes land. All additions are additive.

### Frontend

- `lib/api/index.ts`: `recordMatchSignal(matchId, kind)`, `applyMatchUrl(matchId)`
  (builds the redirect href string for `<a href>`), `tuneSearchQueries(profileId)`.
  No raw fetch anywhere.
- `hooks/use-match-signals.ts` (new): `useMatchSignal` mutation — optimistic card
  state, invalidates `["matches", profileId]` on settle; distinct
  pending/error surfaces per action (cards show disabled-retry on failure; never
  silent). `aria-live` polite region announces save/dismiss outcome.
- `components/features/jobs/MatchCard.tsx`: bookmark save toggle + kebab-menu
  "Dismiss" (and "Restore" on saved/dismissed tabs); Apply anchor href becomes
  `/api/matches/{id}/apply` (keeps `target="_blank" rel="noreferrer"`).
- `components/features/jobs/JobDetailPanel.tsx`: apply link via redirect URL;
  fires the open signal once on mount (per-open ref guard); saved state shown.
- `components/features/jobs/MatchList.tsx`: view tabs above the list (Active / Saved /
  Dismissed / All) wired through a local `status` state into `useMatches` params — a
  view of the list, not a posting filter, so it lives in the list header rather than
  `MatchFilterPanel` (implementation note).
- `components/features/jobs/SearchQueriesCard.tsx` + `hooks/use-job-search.ts`:
  "Tune my queries" button → confirm modal (what it changes, one-LLM-call cost
  note, per standards: focus trap + escape + labels) → mutation → invalidate
  `["profile"]` and `["matches"]`; pending/disabled/empty-signal states handled
  (button disabled with explanation when the profile has <1 signal-bearing match).
- Server Components by default preserved; mutations live in the leaf components.
- Type regeneration only elsewhere; no new raw `fetch`.

### `.env.example` / docs

- `.env.example`: add `TUNE_QUERY_TOP_TERMS=10` (matching block neighbor).
- `docs/guide/03-job-discovery-and-matching.md`: what each signal is, that
  dismissal hides a match (and the Dismissed tab restores it), how tuning works,
  what it costs, and that tuned queries still refresh normally afterwards.
- `docs/architecture.md`: `match` entity diagram gains the four timestamp
  columns; endpoints list gains the two new routes; one note on the
  tune-overwrites-hash interplay with `ensure_queries_fresh`.
- Diagrams: run `node scripts/render-diagrams.mjs` (match entity text changes).

### Tests (`backend/tests/`, scratch Postgres via `migrated_database` — no SQLite)

- `test_matches_endpoint.py` (reuse `seed_matched_profile`, `client`, `get_matches`):
  - Open: sets `first_opened_at`; repeat open is a no-op (same value, no bump of
    `updated_at` beyond the write); unknown match id → 404.
  - Save/unsave, dismiss/undismiss round-trips; unsave on never-saved → clean no-op.
  - Apply: 302 to the seeded posting URL, `clicked_apply_at` set; second click
    keeps the first timestamp; posting without URL → 404 and **no** timestamp.
  - Listing: default excludes dismissed; `status=saved` returns only saved;
    `status=dismissed` the graveyard; `status=all` everything.
  - Tune endpoint contract lives with profile tests (below).
- `test_query_tuner.py` (new):
  - Aggregation buckets on fixtures: a clicked match, a saved match, an
    unopened match, a dismissed match — assert per-bucket skill counts
    (word boundaries: skill "go" must not hit "golang"), top-N title/company
    ordering by count, dismissed-overrides-saved precedence.
  - LLM prompt pinning: serialized bucket block contains aggregate counts and no
    raw title/description text beyond the aggregated term labels.
  - Success: `profile.search_queries` rewritten per enabled source,
    `queries_input_hash == compute_queries_input_hash(current inputs)`; a
    subsequent `ensure_queries_fresh` is a cache hit (no LLM call) — the
    anti-revert guarantee, tested end-to-end.
  - LLM failure: raise → stored queries AND hash unchanged.
  - Disabled sources: only enabled-source keys present in the output.
- `test_migrations.py`: `0020` up (four timestamp columns, nullable) and
  downgrade drops cleanly.
- Connector/query-rendering/scoring tests: unaffected, excluded.

### Gates

- `ruff check . && ruff format --check . && pytest` green in `backend/`.
- `npm run lint && npm run build` green in `frontend/`.
- Migration `0020` ships in the same change as the `Match` model edit.
- `.env.example` + guide 03 + architecture updated in the same change; diagrams
  re-rendered since the match entity changes.

## Risks

| Risk | Mitigation |
|---|---|
| Tune produces worse queries than the user had | Confirm modal + tuning never runs automatically; the user can immediately hit the existing hot "Regenerate" or re-run a search — and a tuned `queries_input_hash` matching current inputs means nothing silently reverts it, but nothing protects against a bad tune except the show-the-result step (new queries are displayed in the card post-tune) |
| Hash-overwrite masks a real profile change | The stored hash is computed from **current** inputs at tune time, so drift can only begin after a later profile edit — exactly the semantics `ensure_queries_fresh` expects |
| Redirect endpoint abused as open proxy | Target is 302 to the posting's own stored URL only; no user-supplied destination is accepted; match id is a UUID with 404 fallback |
| Dismissed-but-saved (or reverse) ordering ambiguities in aggregation | Locked precedence: dismiss outranks save/apply for bucketing; pinned by an aggregation test |
| Optimistic UI desync on signal failure | TanStack invalidation on settle; card state derives from server data on error — no permanent local truth |
| `first_opened_at` fires from detail refreshes (e.g. refetch on focus) | Client guard: one fire per detail-mount lifecycle keyed by match id; server first-write-wins makes accidental repeats inert |

## Out of scope (this issue)

- Application pipeline / status tracking, reminders, email parsing — separate
  detailed plan required before any work (plan-of-record Problem 10 item 5).
- `opened_count`, `dwell_ms` counters; any new page-lifecycle instrumentation.
- Auto-tuning (periodic/triggered) — manual on-demand only per the issue.
- Token-price cost estimation in `adapters/llm.py` (`estimate_cost`).
- Signal-aware scoring (feeding `saved/dismissed` into `final_score`) — signals
  feed query tuning only.
- New match sorts/filters beyond the `status` param (e.g. sort by saved_at).
- Match-detail "why did this get dismissed" UX expansions.
