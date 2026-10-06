# Issue #62 — Evidence chat: a general assistant over your evidence, in a floating panel

**Status:** Implemented (2026-10-06)
**Tracks:** GitHub issue #62 (milestone `v6`, branch `v6/62-evidence-chat`)
**Plan of record:** [v6-implementation-plan.md](v6-implementation-plan.md) §7, §10.2 (this issue replaces their interview framing)
**Supersedes:** #59 (interview UI); reworks the answering part of #58 (sessions, retrieval, grounding kept)
**Depends on:** #58
**Blocks:** #60 (the evaluation set is written for this chat), #61

---

## Goal

A chat where the user asks anything about their own work and gets a natural, cited answer built from
their profile, approved achievements and user-authored evidence (resume lines, notes). It lives in a
**floating panel reachable from every page**, with several conversations (new chat, history, delete),
plus a full `/chat` page.

## Why this replaces #58/#59's framing

#58/#59 were built as interview practice: a question-type router, STAR/intro templates, a pinned-job
"motivation" mode, an Interview tab and "Prep interview" buttons. The product wanted a general assistant.
A live "Tell me about yourself" also showed the context was wrong for any broad question: the intro
template supplied three commit-level achievements, and the answer listed implementation detail (framework
versions, design tokens, VAD thresholds). The model was fine; the prompt and the retrieved context were not.

## Locked decisions

| Decision | Choice | Rationale |
|---|---|---|
| Product shape | General "ask anything" chat; no question types, templates, router or interview wording | Owner decision 2026-10-06 |
| Entry point | Floating bubble on every page except `/` and `/get-started`; panel + `/chat` page | Owner decision |
| Conversations | New chat, history list (newest first), delete; titled from the first question; the open conversation is remembered across pages and reloads | Owner decision |
| Naming | Keep `agent_session` / `agent_message` and `/api/agent/...`; no migration | Avoid churn; "agent" is neutral |
| Answering | One general prompt (`chat_v1`): answer the question asked at the detail it calls for, natural prose, no implementation minutiae unless asked; a question addressed to "you" is answered in the first person as the user, one about "I/my" is answered to the user | Fixes the "Tell me about yourself" failure |
| Context | Full profile block (roles with dates, summary, years, skills, projects, education) + query-relevant approved achievements + always-included per-employer highlights (≤ 4, compact) + user-authored `resume_line` / `note` evidence by similarity. Commits and PRs are reached only through approved achievements | Broad questions work without a router |
| Grounding | Kept: markers resolve, numbers/versions/years/tools/ownership must be in the cited text, judge entailment, one repair, drop what fails, refuse when empty. Extended to second-person claims | Hard requirement: no invented claims |
| Citations | Each carries a readable `label` (achievement title, repo + PR/commit title, "Your profile") and a cleaned, unredacted quote (trailers removed, ≤ 240 chars); the prompt still sees redacted text. "Copy with citations" prints label, quote and link, never raw markers or commit trailers | Owner feedback on the copy output |
| Private provenance | Unchanged: `private` per citation, `used_private` per answer, "Generated from private repository data" | Owner decision 2026-10-02 |
| Job context | Backend keeps optional `match_id` (tested); no UI uses it in this issue | Page-aware context is a follow-up |

## Scope

### Backend (`backend/app/`)

Delete `services/agent_router.py`, the per-type templates and the rationale/note-offer logic; stop writing
`question_type` (column stays); new general prompt; richer `profile_block`; highlights and user-evidence
retrieval in `agent_retrieval.py`; second-person check in `agent_grounding.py`; `label` on `Citation`;
cleaned quotes; session title from the first question.

### Frontend (`frontend/`)

`components/features/chat/` (renamed from `interview/`): `ChatLauncher`, `ChatProvider`, `ChatPanel`,
`ChatHistoryMenu`, header actions (new chat, profile select, open full page), `/chat` page with a sidebar.
Reused: answer card, citation chips and panel, no-evidence card with Add a note → Re-ask, input, optimistic
send hook. Removed: new-session form, pinned job header, "Prep interview" link and the Interview header link.

### Tests

Backend: rewrite the answer tests (intro from profile + highlights, "what have I built with X", no-evidence,
injection ignored, second-person voice, titles), extend retrieval (highlights per employer, resume lines and
notes, drafts excluded) and grounding (second person), endpoint tests for labels and titles; delete the
router tests. Frontend: launcher (open, close, Escape, hidden routes), persistence, new chat / history /
delete, labelled citations and both copy formats, optimistic send with rollback, starters.

### Gates / docs

Backend `ruff check . && ruff format --check . && pyright && pytest --cov=app` (scratch `TEST_DATABASE_URL`);
frontend `npm run lint && npm run format:check && npm run typecheck && npm test && npm run build`;
`alembic check` (no schema change). Docs: `docs/guide/05-evidence-chat.md` (replaces the interview guide),
README, `architecture.md` chat sequence (diagram re-rendered), #58/#59 plans marked superseded.

## Verification (live)

On the dev stack with the real model: "Tell me about yourself" must read like a person's answer (current
role, years, career path, one or two recent themes) with no version numbers or configuration detail;
"What have I built with PostgreSQL?", an unanswerable question and a follow-up behave sensibly; citations
open readable cards; copied text has labels and no trailers or email placeholders.

## Risks

| Risk | Mitigation |
|---|---|
| Natural-sounding answers drift into invention | Validator kept and extended to second person; judge and one repair; live check |
| Highlights add noise to targeted questions | Compact and capped; the prompt says to use only what the question needs |
| Floating panel overlaps page UI or hurts accessibility | Non-modal, Escape and focus return, hidden on the landing pages, tested |

## Out of scope

Page-aware context (the job or profile on screen), job-prep links, streaming, voice, rename/search/pin of
chats, renaming the `agent_*` tables or routes, the #60 evaluation suite.

## Implementation notes

- Citations in the UI are numbered chips (order of first use) instead of the model's `A1`/`E1` markers; the stored answer text keeps the markers.
- Session creation is lazy: the first question creates the conversation, so an empty "New chat" never appears in the history.
- The no-evidence reply is used when the model cites nothing, and the "couldn't confirm" reply when it cited claims that failed the checks.
- The judge now sees up to 6000 characters of each cited block (the profile block is long); an earlier 700-character limit made it reject valid profile sentences.
- Backend also gained `job` and `summary` on the session detail and required response fields (from the earlier #59 work), kept for the generated types.
- Verification: backend gate (ruff, format, pyright, pytest with coverage) and frontend gate (lint, format, types, 338 tests, build) pass; the answers were checked live against the real model on the dev stack. Guide screenshots are not added.
