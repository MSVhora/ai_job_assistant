# AI Job Assistant

Self-hosted, single-user, BYOK (bring-your-own-key) web app: upload a resume → review the AI-extracted profile → discover jobs from multiple sources → ranked matches with explanations.

See [docs/plans/v1-implementation-plan.md](docs/plans/v1-implementation-plan.md) for scope and the [coding standards](docs/instructions/) enforced in this repo.

## Documentation

- **[User guide](docs/guide/README.md)** — step-by-step: setup, profile pipeline, job discovery
- **[Architecture](docs/architecture.md)** — diagrams (flow, sequence, ER schema) and layering rules
- **Plans** — [v1 plan](docs/plans/v1-implementation-plan.md) · [issue #2: resume upload + parsing](docs/plans/v1-issue-002-resume-upload.md)

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

## Development

| Where | Command |
|---|---|
| `backend/` | `uvicorn app.main:app --reload` |
| `backend/` | `ruff check . && ruff format .` / `pytest` |
| `frontend/` | `npm run dev` |
| `frontend/` | `npm run lint` / `npm run build` |
| `frontend/` | `npm run generate:api` (regenerate API types from backend OpenAPI; backend must be running) |
| repo root | `docker compose up -d` |

## License

MIT — see [LICENSE](LICENSE).
