> **Note (2026-10):** this prompt was written when the Developer Evidence Engine was going to be v5. The hardening work became **v5** (`docs/plans/v5/`), so this milestone is **v6**: issue numbers continue from #48 (not #40), migrations from `0023`, and every "v5" below means v6. The prompt body is kept unchanged as the original input.

You are a principal engineer and product architect with experience in LLM
applications, RAG systems, and developer tooling. Produce a detailed,
phased implementation plan for the **v5 milestone** of an existing product.
Be opinionated: pick one option per decision, justify it in 1-2 lines, and
name a fallback. Do not re-decide anything listed under "Existing
foundation"; extend it.

## Product
**AI Job Assistant** is a shipped (v1-v4) self-hosted, single-user, BYOK web
app: resume upload -> AI-extracted, human-reviewed profile -> multi-source
job discovery -> ranked matches with explanations.

v5 adds a **Developer Evidence Engine** with two features on top of the
existing profile:

### Feature A: Evidence-grounded resume builder
Ingests developer evidence from multiple sources:
- GitHub: repos, commit history, commit messages, PRs (descriptions, review
  comments), issues, READMEs, languages, stars/forks, contribution timeline
- The existing uploaded resume PDF (already parsed by v1; reuse
  `resume_service` / `text_extraction` / `profile_extraction`)
- Free-form notes, project write-ups, links (portfolio, blog, Play Store /
  App Store pages)
- Extensible to GitLab, Bitbucket, LinkedIn export, Jira tickets later

It rebuilds the resume as a 1-page or 2-page document, optionally tailored
to a job description. The JD can be pasted **or picked from an existing
ranked match** (`job_posting` / `match`), which is the tie-in with the job
discovery flow.

### Feature B: Knowledge-base interview agent
Uses the same evidence as a knowledge base and answers interview-style
questions in the user's voice, with citations to the underlying evidence.
Examples: "Tell me about yourself", "What was the hardest technical problem
you faced?", "Describe a time you disagreed with a teammate", "Why did you
choose X over Y in project Z?". Optionally prepares for a specific matched
job (pull the posting and the match rationale into context).

## Existing foundation (fixed; do not re-litigate)
- **Backend:** Python 3.12, FastAPI, SQLAlchemy 2.0 async, pydantic v2,
  pydantic-settings. Layering: `routers/` (HTTP only) -> `services/`
  (business logic) -> `models/` (ORM, source of truth for schema) with
  `schemas/` for request/response models and `adapters/` for external I/O.
- **Frontend:** Next.js App Router, TypeScript strict, Tailwind; structure
  `app/`, `components/ui` + `components/features`, `lib/`, `hooks/`.
- **DB:** Postgres + pgvector, Alembic. Every schema change is a new,
  reviewed migration (current head: `0020_add_match_engagement_signals`).
  Embeddings are pinned to Gemini `gemini-embedding-001` at 768 dims; a
  dimension change means a new column plus backfill, never a silent change.
- **LLM:** all calls go through the LiteLLM wrapper `app/adapters/llm.py`
  (structured output validated by pydantic, retries via
  `adapters/retry.py`). Default provider Gemini Flash. Never import a
  provider SDK in routers or services.
- **Data model to extend, not replace:** `candidate` (multi-user-ready
  owner), `profile` (JSONB `structured_profile`, embedding, preferences),
  `profile_revision` (audit trail of human edits), `resume`, `job_posting`,
  `match`, `source_state`.
- **Existing patterns to reuse:** the human-review UI for extracted profile
  content, content-hash caching of LLM outputs (v4 #31), run guards against
  duplicate concurrent runs (v4 #36), backoff/seed/buffer for rate-limited
  sources (v1 #12), the `JobSource` connector interface for job sources.
- **Deploy/config:** Docker Compose, `.env` / `.env.example`, BYOK keys
  only, never committed.
- **Conventions:** `AGENTS.md` and `docs/instructions/*` (type hints
  everywhere, minimal comments, no drive-by refactors). Definition of done
  includes `ruff check`, `ruff format --check`, `pytest`, `npm run lint`,
  `npm run build`, migrations, and doc updates (`docs/guide/`,
  `docs/architecture.md`, Mermaid diagrams re-rendered with
  `node scripts/render-diagrams.mjs`).
- **Git workflow:** milestone branch `v5/milestone` cut from `main`; one
  branch per issue `v5/{issue-number}-{slug}`; issues merge into the
  milestone on close; the milestone merges to `main` with `--no-ff` after
  owner review. Plans live in `docs/plans/v5/` (one overall plan plus
  `v5-issue-NNN-*.md` per issue, numbering continues from #40).

## Constraints
- Self-hosted, BYOK, no hosted SaaS; LLM provider stays swappable through
  the existing wrapper
- Single user, but every new table is owned via `candidate_id` (as today)
- Private repos supported via a user-provided GitHub token; data stays local
- Resume input is PDF only (already supported); no new resume formats in v5
- Solo developer; scope v5 to **3-4 weeks**, split into issues sized like
  the v4 ones (roughly one focused change each)

## Hard requirements
1. No fabricated claims. Every resume bullet and every agent answer must
   trace back to evidence (commit, PR, note, resume line). Metrics are only
   used if present in the evidence or confirmed by the user.
2. The user stays in the loop: review/edit/approve extracted "achievements"
   before they enter the knowledge base (reuse the profile review pattern
   and record edits in an audit trail like `profile_revision`).
3. Output must be ATS-friendly and fit exactly 1 or 2 pages
   deterministically.
4. Respect GitHub rate limits; ingestion must be incremental and resumable
   (model on `source_state`, `retry.py`, and the run guard).
5. The existing profile stays the single identity anchor: resume
   generation and the agent must reconcile with `structured_profile`
   (contact info, education, employers) and surface conflicts rather than
   silently overriding either side.

## The plan must include
1. Product scope: v5 MVP vs v6 vs later, with explicit non-goals. State
   which existing screens and endpoints change.
2. System architecture: components, data flow diagram (Mermaid, matching
   the style of `docs/architecture.md`), and tech-stack decisions with
   trade-offs. Only add a dependency if the current stack cannot do it, and
   justify each new one.
3. Ingestion pipeline: per-source connectors (GitHub as a new connector
   family; decide whether it fits the `JobSource` interface or needs a
   sibling `EvidenceSource` interface, and why), normalization into a
   common "Evidence" schema, chunking strategy for commits/PRs/notes,
   dedupe, noise filtering (merge commits, bots, lockfile bumps,
   "fix typo").
4. Knowledge layer: an achievement/story extraction step (STAR: situation,
   task, action, result) with tags for skills, impact, difficulty. Compare
   plain RAG vs structured "achievement graph + RAG" and recommend one,
   using pgvector in the same Postgres.
5. Resume generation: canonical structured resume schema (JSON Resume
   compatible, mapped to and from `structured_profile`), bullet-writing
   prompts (action verb + scope + impact), ranking/selection of the best
   evidence for the page budget, JD tailoring (including from an existing
   match), and the rendering approach for guaranteed 1-page/2-page fit
   (compare HTML->PDF, Typst, LaTeX; recommend one that runs inside the
   Docker Compose setup) with an auto-trim loop.
6. Interview agent design: retrieval strategy, question-type routing
   (behavioral vs technical vs intro), answer templates, citation format,
   guardrails against hallucination, and conversation memory.
7. LLM layer: how this extends `app/adapters/llm.py` (not a second
   abstraction), model selection per task (cheap model for
   classification/extraction, stronger model for writing), structured
   output validation, retries, content-hash caching, and cost estimation
   per full ingestion.
8. Data model: new tables with key fields as SQLAlchemy models, plus the
   Alembic migration sequence and how existing tables change (if at all).
9. API surface (new routers following current naming) and UI screens as
   Next.js routes (connect/upload, evidence review, resume editor with live
   preview, template picker, agent chat), reusing existing
   `components/ui` pieces.
10. Evaluation: how to test bullet quality, faithfulness (groundedness),
    retrieval quality, and page-fit; include a small golden dataset plan
    and where it lives in `backend/tests/`, runnable in CI without live
    LLM calls (recorded fixtures) plus an opt-in live-LLM suite.
11. Security and privacy: token handling and storage (GitHub PAT, at-rest
    encryption, scope minimization), secrets via `.env`, local-only
    processing options, PII redaction before sending to LLMs, private-repo
    risks (code and commit content leaving the machine to the LLM
    provider; per-repo opt-in).
12. Phased roadmap with week-by-week milestones expressed as numbered
    issues on the `v5/` branch scheme, with deliverables, acceptance
    criteria, and doc impact per issue.
13. Top 10 risks with mitigations, and open questions you need me to
    answer.
14. Recommended libraries, MCP servers, Claude skills/plugins, and dev
    tooling for each phase (prefer what the repo already uses).

## Output format
- Start with a one-page executive summary and the recommended architecture.
- Use tables for trade-off comparisons.
- Write it as the plan of record for `docs/plans/v5/v5-implementation-plan.md`.
- End with a prioritized "first 10 tasks" checklist I can start on today,
  starting with cutting `v5/milestone` from `main`.
- Read `docs/plans/v1/v1-implementation-plan.md`,
  `docs/plans/v4/v4-search-relevance-plan.md`, `docs/architecture.md`, and
  the models in `backend/app/models/` before answering; if anything in them
  conflicts with this prompt, say so.
- Ask at most 5 clarifying questions, only if they would change the
  architecture; otherwise state your assumptions and proceed.
