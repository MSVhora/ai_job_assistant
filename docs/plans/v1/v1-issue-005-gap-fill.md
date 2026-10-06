# Issue #5 — Conversational Gap-Fill for Missing Fields

**Status:** Done (2026-09-01)
**Tracks:** GitHub issue #5 (Day 4, Week 1)
**Plan of record:** [v1-implementation-plan.md](v1-implementation-plan.md) §6, §7, §8
**Depends on:** Issue #4 (profile persistence + revisions — done), Issue #6 (multi-profile — done)

---

## Goal

Close the gap between "AI extracted what was on the resume" and "profile is ready to drive job
discovery" with a short conversation. `POST /api/profiles/{id}/gap-fill` asks targeted questions
about **genuinely missing fields only** (current/target location, remote preference, salary band,
seniority, work authorization), validates answers via pydantic, merges them into the profile, and
records each applied turn as a `gap_fill` revision row. The frontend gets a chat card on the
profile editor with loading/error states and `aria-live` updates.

**Acceptance (from the issue):** gap-fill asks only about missing fields; nothing saved without
validation.

## Locked decisions

| Decision | Choice | Rationale |
|---|---|---|
| DB schema | **No migration** — new fields live in `structured_profile` jsonb; the `gap_fill` revision enum value was pre-created in migration 0004 | Per issue #4's locked storage decision (prefs inside `structured_profile`); jsonb is the documented home for flexible payloads |
| New profile fields | `preferences.seniority` (enum: intern → executive) + `preferences.work_authorization` (free text ≤200 chars) land in the shared profile schema | The issue names seniority + work auth as gap-fill targets; they had no home. Seniority is intrinsically enumerable (drives ranking later); work auth varies too much by country to enumerate safely in v1 — matching treats it as context, not a hard filter |
| Salary validation tightened | `salary_min`/`salary_max` now `ge=0` | "Nothing saved without validation" — negative salaries were previously accepted by the schema |
| Conversation state | **Stateless** — the client sends the full message history with each turn; nothing persisted | No schema change, no conversation table to clean up; chat history is ephemeral client state, the durable outcome is the profile + revision trail |
| Missing-field computation | Deterministic, server-side (`missing_fields()`); the LLM is *told* the missing list and the merge step only accepts values for those keys | Acceptance is "asks only about missing fields" — never trusted to the LLM. Answers for already-present fields are dropped (defense in depth) |
| LLM call shape | One `parse_structured` call per turn via the LiteLLM wrapper: `GapFillTurn{answers: GapFillAnswers, reply}` | Same validation + one-repair pipeline as extraction; one round-trip per turn instead of two |
| Status & missing list | Server-computed after the merge, never taken from the LLM reply | The LLM may misjudge what was answered; the server recomputes `missing_fields` from the merged profile |
| Salary band | One logical field: missing iff **both** min and max are null; inverted min > max bands are dropped server-side and re-asked | A single-sided band ("at least 70k") is a complete answer — requiring both would loop; an inverted band is a misunderstanding, not data |
| Nothing to ask | Short-circuits with a canned reply, **no LLM call** | Free status reporting; no token cost on complete profiles |
| Response includes the profile | `GapFillResponse.structured_profile` returns the merged profile each applied turn | The editor form is initialized once at mount; without the fresh profile, saving the form would clobber chat-filled values with stale ones. The chat resets the form to server truth per applied turn |
| Endpoint path | `POST /api/profiles/{profile_id}/gap-fill` (plan §6 exact shape) | Follows the plural per-profile API convention established by issue #6 |
| Chat UI placement | Card at the top of the profile editor page (`/profile?profile=<id>`), above the editor form; explicit "Start conversation" (no auto-start). Originally below the form; owner feedback moved it to the top | Gap-fill is the step after review/save; auto-start would burn tokens on every page load |
| Error handling | LLM failure → 502 `LLMGapFillError`; not configured → 503; unknown profile → 404; malformed messages → 422 | Standard domain-error mapping; chat keeps the user's draft message in the input on error for one-click retry |

## Scope

### Backend

- **Schemas** — `schemas/profile.py`: `Preferences` gains `seniority` + `work_authorization`;
  `RemotePreference`/`SeniorityLevel` extracted as shared type aliases. New `schemas/gap_fill.py`:
  `GapFillMessage` (role + content ≤2000), `GapFillRequest` (≤30 messages), `GapFillField`
  (key + label), `GapFillAppliedField` (field + label + display value), `GapFillResponse`
  (reply, status, missing_fields, applied_fields, structured_profile, revision)
- **Service** — `services/gap_fill.py`: deterministic `missing_fields()`, prompt builder
  (known-data context + missing-field descriptions + transcript), one `parse_structured` turn,
  pydantic-validated answers, merge-only-into-missing with blank-string cleanup, `gap_fill`
  revision with the standard field-level diff, deterministic status/missing recomputation.
  Structured logging with durations and counts — never message content
- **Router** — `POST /api/profiles/{profile_id}/gap-fill` in `routers/profile.py`
- **Errors** — `LLMGapFillError` (502) in `core/errors.py`
- **Extraction** — `PROFILE_PROMPT_VERSION` bumped to `profile_prompt_v4` (the extraction prompt
  embeds the profile JSON schema, which grew two fields); `parse_version` stamps stay truthful

### Frontend

- `lib/api/schema.d.ts` regenerated from the backend OpenAPI (no hand-written types)
- `lib/api/index.ts`: `gapFillTurn` + `GapFillMessage`/`GapFillResponse` types
- `hooks/use-gap-fill.ts`: mutation with profile query invalidation
- `components/features/profile/GapFillChat.tsx`: start panel → message log (`role="log"`,
  `aria-live="polite"`, thinking indicator), missing-field chips, cumulative "Saved:" chips,
  complete state, optimistic send with revert-on-error (draft restored to the input), retry by
  resending
- `ProfileEditor.tsx`: mounts the chat; on applied turns resets the editor form to the returned
  profile (stale-overwrite guard)
- `lib/profile-schema.ts` + `ProfileReviewForm` + new `SelectField` primitive: seniority select
  and work-authorization input in Job preferences (manual-edit parity with gap-fill fields)

### Tests

`tests/test_gap_fill.py` (DB-backed, httpx ASGI client, mocked `litellm.acompletion`):

- complete profile → canned reply, no LLM call (spy asserts zero calls)
- opening turn (empty history) → question, correct missing list, no revision written
- full answers → merged into preferences, `gap_fill` revision with dotted-path diff, status
  complete, currency normalized (eur → EUR)
- inverted salary band dropped, band still missing, only valid fields applied
- answers for present fields ignored (contact.location preserved)
- unknown profile → 404; LLM not configured → 503; LLM failure → 502
- message validation: >30 messages / empty content / bad role → 422

## Doc impact

- This plan doc; `docs/guide/02-upload-and-profile.md` — gap-fill marked live, endpoint +
  revision-source semantics documented
- `docs/architecture.md` — profile pipeline sequence gains the gap-fill interaction; re-rendered
  via `node scripts/render-diagrams.mjs`
- `docs/guide/README.md` — feature status updated
- No `.env.example` changes (no new configuration); no migration

## Definition of done

- `ruff check . && ruff format --check . && pytest` green in `backend/` (79 passed)
- `npm run lint && npm run build` green in `frontend/`
- No schema change → no migration (enum value pre-created in 0004; new fields are jsonb content)
- Acceptance met: only missing fields are ever asked/merged; every applied turn is pydantic-
  validated and recorded as a `gap_fill` revision

## Out of scope (later issues)

Server-side conversation persistence (client-held history is sufficient for v1), revising
already-filled fields through chat (use the editor form — it records `manual_edit` revisions),
gap-fill during first review before a profile exists (chat operates on saved profiles),
embeddings/matching (#7+) that consume these preference fields.
