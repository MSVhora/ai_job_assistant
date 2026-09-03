# User Guide — AI Job Assistant, Step by Step

A self-hosted, single-user, **BYOK** (bring-your-own-key) web app:

> Upload a resume → review the AI-extracted profile → discover jobs from multiple sources → get ranked matches with plain-language explanations.

**BYOK means:** every AI call (resume parsing, matching, embeddings) uses *your* API key, from
*your* machine, to *your* configured provider. Resume content never goes anywhere else.

## Reading order

| Step | Guide | What you'll learn |
|---|---|---|
| 1 | [Getting started](01-getting-started.md) | Install, configure keys, run the app |
| 2 | [Upload & profile review](02-upload-and-profile.md) | The resume → profile pipeline, editing, gap-fill |
| 3 | [Job discovery & matching](03-job-discovery-and-matching.md) | Sources (official vs scraper), search, ranked matches |
| — | [Architecture](../architecture.md) | How the pieces fit, diagrams, database schema |

## Feature status

The app is being built issue by issue (see [the v1 plan](../plans/v1-implementation-plan.md)).
Each guide marks what is **live now** vs **planned**:

- Live: stack scaffold, health check (`GET /api/health`), resume upload + text extraction
  ([issue #2](../plans/v1-issue-002-resume-upload.md)), LLM profile extraction to a reviewable
  draft ([issue #3](../plans/v1-issue-003-llm-extraction.md)), profile persistence + review/edit
  UI + revision audit ([issue #4](../plans/v1-issue-004-profile-persistence-review-ui.md)),
  conversational gap-fill ([issue #5](../plans/v1-issue-005-gap-fill.md)), multi-profile tracks
  + resume list ([issue #6](../plans/v1-issue-006-multi-profile-resume-list.md)), job sources +
  ingestion ([issue #7](../plans/v1-issue-007-jobsource-adzuna-dedupe.md), [#8](../plans/v1-issue-008-apify-connectors-disclosure.md)),
  embeddings + hard filters ([issue #9](../plans/v1-issue-009-embeddings-pgvector-hard-filters.md)),
  ranked matches with LLM re-rank + rationale ([issue #10](../plans/v1-issue-010-matching-rerank-rationale.md)),
  priority weighting (role-fit ↔ company-fit slider, issue #11)
- Planned: seed data, rate-limit backoff polish (issue #12 buffer)
