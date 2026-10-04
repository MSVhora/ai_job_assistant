# Issue #58 — Interview agent backend: router, retrieval, answers, citations, guardrails (Week 4)

**Status:** Proposed — for owner review
**Tracks:** GitHub issue #58 (milestone `v6`, branch `v6/50-agent-retrieval-router-answer`)
**Plan of record:** [v6-implementation-plan.md](v6-implementation-plan.md) §7, §9 (migration `0027`), §12
**Depends on:** #49, #52, #53 (approved achievements), #55's verifier utilities
**Blocks:** #59 (UI), #60 (agent eval)

---

## Goal

Answer interview-style questions in the user's voice from **approved** achievements and their evidence, with citations, a grounding check, and an honest refusal when evidence is missing. Persisted sessions and messages; optional job context from a match. Non-streaming (plan §0 #7).

## Locked decisions

| Decision | Choice | Rationale |
|---|---|---|
| Question types | `intro`, `behavioral`, `technical`, `motivation`, `hypothetical`, `out_of_scope` | Plan §7.2 |
| Router | Rules first (regex/keyword table, deterministic); `LLMTask.classify` only when no rule fires | Cheap, testable |
| Query rewrite | Cheap model, only when history exists and the question has references ("that project", "why?") | Memory without cost on every turn |
| Retrieval | Over `status='approved'` achievements only: `0.55 cosine + 0.25 skill/entity overlap + 0.10 recency + 0.10 impact`; weights in Settings; optional project/employer filter when the question names one; top 6 | v4 #37 style |
| Drill-down | For each of the top achievements: top 2 linked `evidence_chunk`s by cosine | Technical "why X over Y" needs decision text |
| No-evidence rule | Best score below `AGENT_MIN_RETRIEVAL_SCORE`, or zero approved achievements → templated "no evidence" reply + suggestion to add a note; no model improvisation | Hard req. 1 |
| Decision-rationale questions | If no cited text states a reason, answer says what the evidence shows but not why, and offers to turn the user's typed explanation into a note | Plan §7.2 |
| Answer model | `LLMTask.write` with the per-type template; output schema `{answer, claims[{text, marker}], gaps[]}` | Structured claims make grounding checkable |
| Citations | Context blocks carry markers `[A1]`/`[E1]`; response `citations[{marker, achievement_id, evidence_item_id, url, quote, private}]` | Plan §7.4 |
| Grounding validator | (1) every factual sentence has a marker; (2) numbers/versions/years/tool names appear in the cited evidence; (3) `LLMTask.judge` entailment. One repair call; if still failing, return the grounded subset + `gaps` + `grounding.status='partial'` | Guardrail |
| Voice | First person, concise, plain; optional per-session `style_notes` from the user; style is an instruction, not license to embellish | Plan §7.4 |
| Identity facts | Employers, titles, dates, contact injected from `structured_profile` by code, never generated | Hard req. 5 |
| Job context | Session optionally pins `match_id` → posting digest + `match.rationale`; used for `motivation` answers and relevance boosts, never as evidence about the user | Prep for a matched job |
| Private provenance | `citations[].private` and `messages.grounding.used_private=true` when any cited evidence is private; UI shows "Generated from private repository data" (#59) | Owner decision |
| Memory | Last `AGENT_HISTORY_TURNS` (default 6) turns verbatim + rolling `agent_session.summary` of older turns (cheap model); summary holds conversation state only, never new facts about the user | Plan §7.4 |
| Tools | None (no network, no writes beyond the message log) | Prompt-injection posture |
| Transaction shape | Persist user message → generate → persist assistant message within one request; no streaming | `DbCommitMiddleware` commits at response start |

## Scope

### Migration (`0031_add_agent_session.py`)

> Numbering: `0027` was taken by #55 (`resume_document.generation`) and `0028` by the repository-list cache (`evidence_scope` listing columns), `0029` by the employer merges (`candidate.employer_merges`) and `0030` by the organization employers (`evidence_source.owner_employers`), so this migration is `0031`.

`agent_session` and `agent_message` per plan §9 (FKs indexed; `agent_message(session_id, created_at)` index; role enum). No existing table touched.

### Backend (`backend/app/`)

- `models/agent.py`, `schemas/agent.py` (session/message/citation/grounding schemas).
- `services/agent_router.py` (rule table + fallback), `services/agent_retrieval.py` (hybrid scoring, SQL for approved set, drill-down), `services/agent_templates.py` + `services/prompts/agent.py` (`AGENT_PROMPT_VERSION`; evidence fenced as data), `services/agent_grounding.py` (validator reusing `resume_verify` claim extraction), `services/agent_memory.py` (turn window + summary updates), `services/agent.py` (orchestration: `answer(session_id, question)`).
- `routers/agent.py`: `POST /api/agent/sessions` (`profile_id`, optional `match_id`, `style_notes`), `GET /api/agent/sessions`, `GET /api/agent/sessions/{id}` (with messages), `DELETE`, `POST /api/agent/sessions/{id}/messages`. Ownership: candidate + profile; `match_id` must belong to the profile.
- Settings: `agent_history_turns`, `agent_min_retrieval_score`, retrieval weights.

### Tests

- `tests/services/test_agent_router.py`: labelled question set (≈ 40) → rules path correct for all that rules should catch; ambiguous questions reach the fallback (fake classifier asserted called).
- `tests/services/test_agent_retrieval.py` (Postgres, recorded vectors): recall@5 on `questions.yaml` ≥ 0.80; draft/rejected/archived achievements never returned; project filter works; empty KB → no-evidence path; thresholds respected.
- `tests/services/test_agent_grounding.py`: injected unsupported number, tool, year, and an unmarked sentence are each caught; one repair then partial result; marker → real evidence id resolution; private flag propagates.
- `tests/services/test_agent_answers.py` (recorded LLM): intro uses profile summary + top achievements; behavioral cites one achievement in STAR shape; technical drill-down includes chunk quotes; "why X over Y" without rationale evidence → says so and offers a note; unanswerable question refuses; hypothetical labelled as approach; prompt-injection text in evidence does not change behaviour.
- `tests/services/test_agent_memory.py`: window and summary rollover; summary never contains new factual claims (checked with the verifier against prior messages); session reload preserves order.
- `tests/routers/test_agent_endpoints.py`: ownership 404s, foreign match 404, message persistence on both paths, error path keeps the user message.
- `tests/db/test_migrations.py` (+ `tests/db/test_schema_standards.py` picks the new tables up): `0027` round trip.

### Standards from v5 (must hold from the first commit)

- **Lint/types:** ruff `ALL` and pyright strict pass with no new `noqa`; untyped third-party values are narrowed through small typed helpers (the pattern in `adapters/llm.py`); a `# pyright: ignore` needs a reason comment. Functions stay within the configured limits (args 6, branches 13, returns 8, complexity 14).
- **Coverage and layout:** the 90 % floor holds with `TEST_DATABASE_URL` set; new code ships with its tests in the mirrored folders (`tests/adapters/`, `tests/services/`, `tests/routers/`, `tests/db/`, `tests/core/`; recorded/golden suites in `tests/eval/`).
- **Config:** every new `Settings` field appears in `.env.example` (the settings↔env guard test fails otherwise); no `os.getenv`/`os.environ` and no provider SDK imports outside their one module.
- **API:** new routes keep `response_model` (binary downloads declare their media type instead), use only the CORS-allowed methods (`GET`, `POST`, `PATCH`, `DELETE`, `OPTIONS` — **never PUT**) and headers (`Content-Type`, `Accept`), raise `DomainError` subclasses (checked by `tests/core/test_error_contract.py`), and bound every list with the shared `pagination()` dependency and `X-Total-Count`.
- **Privacy:** no resume/evidence text, prompts, tokens or keys in logs (extend `tests/routers/test_logging_privacy.py` for the new flows); LLM calls log `cost_usd=`; outbound HTTP has an explicit timeout.
- **Schema (v5 #43 conventions):** every table with `updated_at` gets `create_updated_at_trigger(table)` / `drop_updated_at_trigger(table)` from `app.core.migration_helpers`; every FK is indexed and declares its ON DELETE (CASCADE owned children, RESTRICT identity/audit, SET NULL provenance); constraints and indexes are named (`uq_`/`ix_`/`fk_`/`ck_`); bounded scalars get a `CHECK`; `alembic check` is clean and the schema audit (`tests/db/test_schema_standards.py`) reports nothing; downgrade works. Revision numbers continue from `0022`.

### Gates / docs

the backend gate (`ruff check . && ruff format --check . && pyright && pytest --cov=app` with a scratch `TEST_DATABASE_URL`) and `pre-commit run --all-files`; `.env.example` agent settings; `architecture.md` agent sequence diagram (re-render); `docs/guide/05-interview-agent.md` drafted (how answers are grounded, what "no evidence" means, adding a note to fill gaps).

## Risks

| Risk | Mitigation |
|---|---|
| Fluent but ungrounded answers | Structured claims + two-layer validator + refusal path; adversarial golden cases |
| Retrieval misses the right story | Hybrid scoring + drill-down; recall@5 gate; weights tunable in Settings |
| Latency (rewrite + answer + judge) | Rewrite only when needed; judge uses the cheap model; typical turn is 2–3 calls |
| Voice drifts into embellishment | Style rules are tone-only; validator catches additions |

## Out of scope

Streaming, voice, mock-interview scoring, tools/web access, multi-session analytics, answers about the user from outside approved evidence.
