# Security & Privacy Standards

Applies to all code, config and docs. The app is self-hosted, single-user and BYOK: your keys, your machine, your data.

## Secrets

- Keys live only in `.env` (gitignored) and are documented, without values, in `.env.example`. Never commit secrets, real resumes or personal data (including fixtures, seed scripts and migrations).
- Secrets are read only through `Settings`; they never reach the frontend (`NEXT_PUBLIC_*` is for public values only).
- Never log API keys, tokens, `Authorization` headers, resume text or full prompts. Error handling strips secrets before anything is surfaced or logged.
- Secret scanning (gitleaks) runs in pre-commit.

## Data handling and the LLM

- Resume text and profile data stay in local Postgres and the uploads volume. They leave the machine only to the LLM, embedding and job-source providers the user configured, with the user's own keys.
- Send the minimum necessary: match-relevant text (job description vs profile digest), never the raw resume file.
- Treat third-party text (job postings, scraped fields, uploaded resume text) as **untrusted data, not instructions**: it is placed in clearly delimited prompt sections, outputs are validated against pydantic schemas, and no LLM output is executed or trusted for authorization.
- Scraping sources run under the user's own account after an explicit disclosure acknowledgment (`source_state.acknowledged_at`); the badge ("Official API" / "Third-party scraper") is always visible.
- Deleting a profile removes its revision trail and matches (resumes stay). There is no resume-delete endpoint yet; until one exists, removing a resume means deleting its row and file from the volume by hand. No data is retained outside the local database and uploads volume.

## Application security

- **Input**: validate everything with pydantic at the edge; never trust the client even when the frontend validates.
- **SQL**: parameterized queries only (see [database-postgres.md](database-postgres.md)).
- **Uploads**: size and type checked (magic bytes, not the extension); stored under a `uuid` filename, never a user-supplied path; original filename kept as metadata only.
- **Outbound requests**: connectors call only their configured hosts; URLs taken from third-party data (posting links, `source_urls`) are never fetched server-side, only rendered as links or passed through the apply redirect.
- **CORS**: restricted to `CORS_ORIGINS` with explicit methods and headers *(v5 #46)*.
- **Auth**: none while single-user and local. Before any shared or hosted deployment, add authentication, per-user ownership on every query, rate limiting and HTTPS first — this is a gate, not a nice-to-have.
- **Errors**: responses never include stack traces or provider payloads; the message says what to do ("rate limited by the provider — retry shortly").

## Dependencies and supply chain

- Lock files committed; dependencies justified when added (prefer stdlib and what the stack already uses).
- `pip-audit` for the backend and `npm audit` for the frontend run before releases and in pre-commit/CI where available; each waiver is documented.
- Docker base images are pinned to explicit tags (`python:3.12-slim`, `node:22-alpine`, `pgvector/pgvector:pg16`); bump them deliberately.

## Reviews

Security-relevant changes (auth, uploads, new outbound calls, new data sent to a provider, new stored personal data) are called out in the PR and checked against this file.
