# Issue #59 — Interview agent UI: chat, citations, job prep, memory (Week 4)

**Status:** Proposed — for owner review
**Tracks:** GitHub issue #59 (milestone `v6`, branch `v6/51-agent-chat-ui-job-prep`)
**Plan of record:** [v6-implementation-plan.md](v6-implementation-plan.md) §2.5, §7, §10.2
**Depends on:** #58
**Blocks:** #61 (acceptance run)

---

## Goal

A chat screen for the knowledge-base agent: pick a profile (and optionally a ranked match to prep for), ask questions, see answers with clickable citations and a grounding status, and resume sessions later. Plain request/response (no streaming).

## Locked decisions

| Decision | Choice | Rationale |
|---|---|---|
| Routes | `/interview` (sessions list + new) and `/interview/[sessionId]` (chat) | Plan §10.2 |
| Prep for a match | New-session form has a match picker (same list component as the resume JD picker); `MatchCard` gets "Prep interview" → `/interview/new?match=…&profile=…`; chat header shows the pinned job with its rationale expandable | Tie-in with discovery |
| Citations | Inline markers rendered as chips; click opens a side panel with the achievement (STAR) and the evidence quote with an external link to the commit/PR/note | Verifiability |
| Private marker | Any answer using private-derived evidence shows a badge and the note "Generated from private repository data"; the markers inside the text remain clickable | Owner decision 2026-10-02 |
| Grounding status | Badge per answer: `Grounded` / `Partially grounded — see gaps`; flagged sentences underlined with the reason | Honest UI |
| No-evidence replies | Render a clear "Not in your evidence" card with an "Add a note" button that opens a note form prefilled with the question and, once saved, offers "Re-ask" | Fills gaps through the normal evidence → review path |
| Suggested questions | Static starter chips per type (intro, behavioral, technical, motivation); motivation chip disabled without a pinned job | Discoverability, no LLM |
| Memory | No UI for the summary beyond a "Conversation summary" disclosure; "New session" resets context | Simple |
| Copy/export | "Copy answer" (plain text without markers) and "Copy with citations" | Practical use while practising |
| Errors | Rate-limit/timeouts show the existing friendly provider messages; the unsent question stays in the input | Reuse error mapping |

## Scope

### Frontend (`frontend/`)

- `app/interview/page.tsx`, `app/interview/[sessionId]/page.tsx`.
- `components/features/interview/`: `SessionList`, `NewSessionForm` (profile select, optional match picker, style notes), `ChatThread`, `AnswerCard` (text with `CitationChip`s, `GroundingBadge`, `PrivateBadge`, gaps list), `CitationPanel`, `NoEvidenceCard`, `StarterQuestions`, `PinnedJobHeader`.
- `lib/api/` + `hooks/` (`useAgentSession`, `useSendMessage` with optimistic user message and rollback on failure).
- `MatchCard` button, `SiteHeader` nav entry; regenerate API types.

### Backend

None expected beyond bug fixes found while integrating; any change must come with a test and be called out in the PR.

### Tests / verification

- `npm run lint && npm run build`.
- Manual script in the PR: intro, behavioral, technical-why (with and without rationale evidence), motivation with and without a pinned job, unanswerable question → refusal card → add note → approve in review → re-ask → now answered with citations; reload keeps the thread; summary kicks in after the configured number of turns (set `AGENT_HISTORY_TURNS=2` for the check); private-derived answer shows the badge and note.

### Standards from v5 (must hold from the first commit)

- **Gate:** `npm run lint && npm run format:check && npm run typecheck && npm test && npm run build` in `frontend/`; Prettier (width 100) with the Tailwind plugin.
- **Components ≤ 200 lines** (ESLint `max-lines` is an error in `app/` and `components/`): split into subcomponents and hooks from the start.
- **Types:** no `any`, no `!` on API data (use TanStack Query's `skipToken` for nullable ids); optional props are declared `?: T | undefined`; payloads omit empty keys instead of sending `undefined` (`exactOptionalPropertyTypes`, `noUncheckedIndexedAccess`).
- **Structure:** every route segment that fetches data has `loading.tsx`, `error.tsx` and `not-found.tsx`; all calls go through `lib/api` with regenerated types (`npm run generate:api`); read the Next 16 docs in `node_modules/next/dist/docs/` before using framework APIs.
- **Tests:** co-located Testing Library tests for every new component and hook, mocking at the `lib/api` boundary.

### Gates / docs

Gates green; `docs/guide/05-interview-agent.md` completed with screenshots; README feature list.

## Risks

| Risk | Mitigation |
|---|---|
| Users treat answers as verbatim scripts | Copy buttons and guide copy encourage using them as practice material; grounding badge stays visible |
| Long answers overwhelm the UI | Collapse evidence panel by default; answer templates already cap length |
| Optimistic message state diverges on failure | Rollback path tested manually and by hook tests where the repo has frontend tests |

## Out of scope

Streaming tokens, voice input/output, mock-interview scoring and feedback, saving answers as reusable "talking points" (v7).
