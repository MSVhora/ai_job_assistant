# AI Job Assistant

Self-hosted, single-user, BYOK (bring-your-own-key) web app: upload a resume → save its AI-extracted draft as one or more named profile tracks (e.g. "Senior Android Developer" and "Senior Software Engineer") → discover jobs from multiple sources → ranked matches with explanations per track.

See [docs/plans/v1-implementation-plan.md](docs/plans/v1-implementation-plan.md) for scope and the [coding standards](docs/instructions/) enforced in this repo.

## Documentation

- **[User guide](docs/guide/README.md)** — step-by-step: setup, profile pipeline, job discovery
- **[Architecture](docs/architecture.md)** — diagrams (flow, sequence, ER schema) and layering rules
- **Plans** — [v1 plan](docs/plans/v1-implementation-plan.md) · [issue #2: resume upload + parsing](docs/plans/v1-issue-002-resume-upload.md) · [issue #3: LLM structured extraction](docs/plans/v1-issue-003-llm-extraction.md) · [issue #4: profile persistence + review UI](docs/plans/v1-issue-004-profile-persistence-review-ui.md) · [issue #6: multi-profile tracks + resume list](docs/plans/v1-issue-006-multi-profile-resume-list.md) · [UI implementation](docs/plans/v1-ui-implementation-plan.md)

Diagrams are Mermaid blocks in the docs, kept in sync with rendered SVG copies in
`docs/assets/`. After editing any diagram, re-render:

```bash
node scripts/render-diagrams.mjs   # needs @mermaid-js/mermaid-cli
```

## Stack

FastAPI (Python 3.12) · Next.js (TypeScript) · Postgres + pgvector · LiteLLM (Gemini Flash default) · Docker Compose

## Quickstart

```bash
cp .env.example .env        # fill in GEMINI_API_KEY (others optional)
docker compose up -d        # db + api + web
```

Apply migrations (from `backend/`, using the host `DATABASE_URL`):

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
```

- Web: http://localhost:3000
- API: http://localhost:8000 (docs at `/docs`)
- Health: `GET /api/health` reports database + LLM key status

## How it works

A first successful match takes about five minutes (details in the [user guide](docs/guide/README.md)):

1. **Connect keys** — add `GEMINI_API_KEY` (and optionally Adzuna/Apify keys) to `.env`; enable sources on the **Setup** page. Scraping-based sources show a ToS disclosure you acknowledge once. [Getting started →](docs/guide/01-getting-started.md)
2. **Upload a resume** — the AI extracts a structured profile draft; review and correct every field before saving. Corrections are recorded in a revision audit trail. [Upload & profile review →](docs/guide/02-upload-and-profile.md)
3. **Fill the gaps** — a short conversational pass asks only about genuinely missing fields (location, salary band, seniority, work authorization, remote preference).
4. **Search** — the LLM drafts per-source search queries from your profile; ingestion runs in the background across all enabled sources, de-duplicating as it goes. You can leave the page while it runs. [Search & sources →](docs/guide/03-job-discovery-and-matching.md)
5. **Read ranked matches** — every posting gets a similarity score; the top N get an LLM re-rank with role-fit/company-fit ratings and a plain-language "why this matches". The priority slider re-weights role fit vs company fit live — per profile, with no extra AI cost. [Search & sources →](docs/guide/03-job-discovery-and-matching.md)

## Development

| Where | Command |
|---|---|
| `backend/` | `uvicorn app.main:app --reload` |
| `backend/` | `ruff check . && ruff format .` / `pytest` |
| `frontend/` | `npm run dev` |
| `frontend/` | `npm run lint` / `npm run build` |
| `frontend/` | `npm run generate:api` (regenerate API types from backend OpenAPI; backend must be running) |
| repo root | `docker compose up -d` |

DB-backed backend tests need a **scratch** Postgres database (the suite migrates up at
session start and downgrades to `base` at the end — never point it at your dev database):

```bash
docker exec ai_job_assistant-db-1 psql -U postgres -c "create database ai_job_assistant_test"
cd backend && TEST_DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/ai_job_assistant_test" pytest
```

To explore the UI without any keys or live searches, seed a synthetic demo dataset
(profile "Jane Doe (demo)" + deterministic postings and matches, zero LLM calls):

```bash
docker cp backend/scripts/seed_demo.py ai_job_assistant-api-1:/tmp/
docker exec ai_job_assistant-api-1 python /tmp/seed_demo.py            # seed (~30 postings)
docker exec ai_job_assistant-api-1 python /tmp/seed_demo.py --reset    # remove demo data
```

## License

MIT — see [LICENSE](LICENSE).
