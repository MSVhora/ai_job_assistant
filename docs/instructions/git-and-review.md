# Git, Commit & Review Standards

Branching rules (milestone branch per version, one branch per issue, merge on close, owner review of the milestone merge) live in `AGENTS.md` and are not repeated here. This file covers commit messages, plans, pull requests and review.

## Branch names

- Version work: `v{N}/milestone`, `v{N}/{issue-number}-{slug}` (see `AGENTS.md`).
- Docs-only changes may go straight to `main`; larger documentation efforts use `docs/{slug}`.

## Commit messages

`type(scope): summary` in the imperative, lowercase type. Scope is `v{N}/{issue}` for issue work, otherwise the area.

```
feat(v4/39): engagement signals (open/apply/save/dismiss), status views, and confirm-gated tune-my-queries
fix(v4/37): priority slider commits match-list refetch on drag settle
refactor(v4/34): Adzuna contract filters become a single job_type select
docs(v4/39): mark issue 39 plan implemented with notes
merge issue #39 — engagement signals ...
merge milestone v4 — search relevance & smarter matching (issues #31–#39)
```

- Types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `merge`.
- One logical change per commit; no drive-by refactors inside a feature commit.
- Body explains **why**, not what the diff already shows. Reference the issue plan when one exists.
- Agent-authored commits end with the co-author trailer configured for the session.

## Plans

- Non-trivial work starts with a plan file (`docs/plans/{version}/…-issue-NNN-*.md`: goal, locked decisions, scope, tests, gates, risks, out of scope). Do not silently drift from the plan of record; if it is wrong or changed, say so in the PR and update the plan.
- When an issue merges, mark its plan **Implemented** with notes about anything that deviated.

## Pull requests

- Small, one issue, linked to its plan. Description: what changed, why, how it was tested, doc impact, migration notes.
- Checklist before requesting review:
  - [ ] Definition of done in `AGENTS.md` passes (lint, format, types, tests, build as applicable).
  - [ ] Model changes include a reviewed migration; downgrade works.
  - [ ] New settings are in `Settings` and `.env.example`.
  - [ ] User-facing behaviour, API surface, schema or architecture changes are reflected in `docs/guide/`, `docs/architecture.md` and any diagram (re-rendered with `node scripts/render-diagrams.mjs`).
  - [ ] No secrets, real resumes or personal data.
  - [ ] New dependencies are justified.

## Review

Reviewers check, in order: correctness and edge cases; security and privacy ([security-privacy.md](security-privacy.md)); layering and standards ([backend-fastapi.md](backend-fastapi.md), [frontend-nextjs.md](frontend-nextjs.md), [database-postgres.md](database-postgres.md)); tests that would fail without the change; docs and migrations. Findings are fixed in follow-up commits on the same branch — never rewrite the milestone branch history mid-milestone.
