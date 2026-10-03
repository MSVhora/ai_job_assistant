# Issue #61 — Privacy hardening, documentation, milestone close-out (Week 4)

**Status:** Proposed — for owner review
**Tracks:** GitHub issue #61 (milestone `v6`, branch `v6/53-privacy-docs-milestone-close`)
**Plan of record:** [v6-implementation-plan.md](v6-implementation-plan.md) §12, §13 (milestone acceptance), AGENTS.md definition of done
**Depends on:** #48–#60
**Blocks:** merging `v6/milestone` into `main`

---

## Goal

Prove the privacy and honesty guarantees hold end to end, finish all documentation, and run the full milestone acceptance script so the owner can review one coherent milestone.

## Locked decisions

| Decision | Choice | Rationale |
|---|---|---|
| Redaction coverage | A test **enumerates every call site** of `llm.generate`/`parse_structured` in `services/` and asserts each is reachable only through a path that redacts its evidence-derived inputs (or documents why it takes none, e.g. contact-free profile digests) | Plan §12: PII redaction before any LLM call |
| Token hygiene | A test boots the app with a sentinel `GITHUB_TOKEN`, exercises sync/status/error paths, and asserts the sentinel appears in no response body, log record, DB row, or exception message | ADR-4 |
| Private provenance audit | A test walks the pipeline with one private repo and asserts the flag at every layer (item → chunk → achievement → bullet → citation → UI-facing responses) | Owner decision 2026-10-02 |
| Disclosure | The disclosure modal wording for private repos is final here: lists exactly what text categories leave the machine (commit messages, PR/issue text, review comments, README excerpts, notes), what never does (code, diffs, file contents), and that outputs derived from private data are marked | Informed opt-in |
| Data deletion | Removing a scope offers "also delete its evidence": cascades items/chunks; achievements that cite deleted evidence are **archived** with a revision (never silently deleted) and flagged | Honest audit trail |
| Docs rule | All doc updates required by AGENTS.md "Docs kept in sync" land here if not already in earlier issues | Definition of done |

## Scope

### Backend

- Redaction call-site enumeration test and any fixes it finds.
- Scope-removal service path with evidence purge + achievement archival + revision rows; endpoint `DELETE /api/evidence/github/scopes/{id}?purge=true`.
- Sentinel-token, private-flag and sweeper/guard regression tests consolidated under `tests/core/test_v6_security.py`.
- Final `GET /api/setup/check` shape (token presence, per-task models, redaction enabled).
- `.env.example` completed and sorted: `GITHUB_*`, `EVIDENCE_*`, `LLM_MODEL_*`, `LLM_MAX_CONCURRENCY`, selection/agent weights, `RESUME_FIT_MAX_COMPILES`, `AGENT_*`, each with a one-line comment.

### Frontend

Disclosure modal copy, scope-removal confirm dialog (with the purge option), `/setup` additions; final nav check; empty states for Evidence, Review, Resume builder and Interview.

### Documentation (all in this change if not already done)

| Doc | Update |
|---|---|
| `docs/instructions/` | `llm-ai.md` (task routing, output cache, redaction), `security-privacy.md` (GitHub PAT, private-data marking, redaction call-site test), `testing.md` (`tests/eval/`, recorded vs live suites, `live_llm` marker), `backend-fastapi.md` (binary-download exception to `response_model`), `api-design.md` (export/PDF routes) |
| `docs/architecture.md` | Header link to the v6 plan; system-overview diagram (evidence sources, new services); new sequences (evidence ingest → extract → review; resume build; agent turn); ER with all v6 tables; privacy-posture section (token handling, redaction, private marking, local-only note); the single-user note retained |
| `docs/guide/04-evidence-and-resume.md` | Final: connect, scopes, refresh vs full, review, private marks, tailoring, conflicts, page fit, downloading |
| `docs/guide/05-interview-agent.md` | Final: grounding, citations, no-evidence replies, job prep |
| `docs/guide/README.md`, `README.md` | Index and feature list |
| `docs/plans/v6/*` | Plan §9 updated with `EvidenceSourceAccount`, `achievement_extraction_run`, `evidence_stale_at`, draft embeddings, resume ingestion source (#48/#51/#52 drift notes); each issue plan marked Implemented with notes |
| Diagrams | `node scripts/render-diagrams.mjs`; commit regenerated SVGs |

### Standards from v5 (must hold from the first commit)

- **Lint/types:** ruff `ALL` and pyright strict pass with no new `noqa`; untyped third-party values are narrowed through small typed helpers (the pattern in `adapters/llm.py`); a `# pyright: ignore` needs a reason comment. Functions stay within the configured limits (args 6, branches 13, returns 8, complexity 14).
- **Coverage and layout:** the 90 % floor holds with `TEST_DATABASE_URL` set; new code ships with its tests in the mirrored folders (`tests/adapters/`, `tests/services/`, `tests/routers/`, `tests/db/`, `tests/core/`; recorded/golden suites in `tests/eval/`).
- **Config:** every new `Settings` field appears in `.env.example` (the settings↔env guard test fails otherwise); no `os.getenv`/`os.environ` and no provider SDK imports outside their one module.
- **API:** new routes keep `response_model` (binary downloads declare their media type instead), use only the CORS-allowed methods (`GET`, `POST`, `PATCH`, `DELETE`, `OPTIONS` — **never PUT**) and headers (`Content-Type`, `Accept`), raise `DomainError` subclasses (checked by `tests/core/test_error_contract.py`), and bound every list with the shared `pagination()` dependency and `X-Total-Count`.
- **Privacy:** no resume/evidence text, prompts, tokens or keys in logs (extend `tests/routers/test_logging_privacy.py` for the new flows); LLM calls log `cost_usd=`; outbound HTTP has an explicit timeout.

### Standards from v5 (must hold from the first commit)

- **Gate:** `npm run lint && npm run format:check && npm run typecheck && npm test && npm run build` in `frontend/`; Prettier (width 100) with the Tailwind plugin.
- **Components ≤ 200 lines** (ESLint `max-lines` is an error in `app/` and `components/`): split into subcomponents and hooks from the start.
- **Types:** no `any`, no `!` on API data (use TanStack Query's `skipToken` for nullable ids); optional props are declared `?: T | undefined`; payloads omit empty keys instead of sending `undefined` (`exactOptionalPropertyTypes`, `noUncheckedIndexedAccess`).
- **Structure:** every route segment that fetches data has `loading.tsx`, `error.tsx` and `not-found.tsx`; all calls go through `lib/api` with regenerated types (`npm run generate:api`); read the Next 16 docs in `node_modules/next/dist/docs/` before using framework APIs.
- **Tests:** co-located Testing Library tests for every new component and hook, mocking at the `lib/api` boundary.

### Milestone acceptance run (recorded in the PR)

From a clean clone: set `GITHUB_TOKEN` and the Gemini key → `docker compose up` → connect → opt in 3 repos (one private, with disclosure) → sync; kill the API mid-run and restart (resume from cursors) → incremental **Refresh** then **Full re-sync** (no lost approvals) → estimate and confirm extraction → review/approve ≥ 10 achievements incl. a metric confirmation → resume from a pasted JD (review view first, copy as Markdown, one comment applied, 1-page PDF) and from a ranked match (2- and 3-page PDFs): each within its page target with the highest-priority content kept, aligned work boosted but non-aligned work still present, conflicts and JD gaps shown, private marks visible in the review view and absent from the PDF and copied text → agent: intro, behavioral, technical-why, unanswerable (refusal → add note → approve → re-ask) → live eval suite table attached. Gates: `ruff check . && ruff format --check . && pytest`, `npm run lint && npm run build`.

### Milestone merge procedure (AGENTS.md)

`git merge main` into `v6/milestone` (resolve drift), gates green, then — after **owner review** — `git switch main && git merge --no-ff v6/milestone`, `git pull`, delete `v6/milestone` locally and on the remote.

## Risks

| Risk | Mitigation |
|---|---|
| Last-week docs crunch | Per-issue doc impact is already assigned; this issue is verification and gaps, not first drafts |
| Call-site enumeration test is brittle | Based on an AST walk with an explicit allow-list file reviewed in PRs |
| Purge cascades surprise the user | Confirmation dialog states what is deleted and what is archived |

## Out of scope

New features, template/connectors for v7, encrypted token storage, local-only mode testing.
