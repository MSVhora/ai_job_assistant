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

- Live: stack scaffold, health check (`GET /api/health`)
- In progress: resume upload + text extraction ([issue #2 plan](../plans/v1-issue-002-resume-upload.md))
- Planned: LLM profile extraction, review UI, gap-fill, job sources, matching
