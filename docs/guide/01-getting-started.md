# 1 — Getting Started

**Status: live** (scaffold + health check)

## What you need

- **Docker Desktop** (recommended — everything runs in containers), or the manual stack:
  Python 3.12, Node.js 20+, and Postgres 16 with the `pgvector` extension
- A **Gemini API key** — the default LLM provider. Free tier works:
  create one at [Google AI Studio](https://aistudio.google.com/apikey)

Later (job discovery) you can optionally add an [Adzuna](https://developer.adzuna.com/) key
(free) and an [Apify](https://apify.com) token (paid usage) — nothing else is needed for the
profile pipeline.

## Step 1 — Clone and configure

```bash
git clone <repo-url> ai_job_assistant
cd ai_job_assistant
cp .env.example .env
```

Open `.env` and fill in:

```ini
GEMINI_API_KEY=your-key-here     # required
```

Keys stay in `.env` (gitignored). They are read only by *your* backend and used only for
*your* requests — that is the BYOK model.

## Step 2 — Start the stack

```bash
docker compose up -d
```

This starts three services:

| Service | URL | What it is |
|---|---|---|
| `web` | http://localhost:3000 | Next.js frontend |
| `api` | http://localhost:8000 | FastAPI backend (interactive docs at `/docs`) |
| `db` | localhost:5432 | Postgres 16 + pgvector |

Both app containers bind-mount their source (`backend/app`, and the frontend's
`app`/`components`/`hooks`/`lib`/`public`), so code edits hot-reload without a rebuild —
only dependency or Dockerfile changes need `docker compose up -d --build`.

## Step 3 — Apply database migrations

From the repo root, using the API container:

```bash
docker compose exec api alembic upgrade head
```

Or from `backend/` with a host Python 3.12 environment (see the README quickstart).

## Step 4 — Verify

```bash
curl http://localhost:8000/api/health
```

```json
{"status":"ok","database":true,"llm_configured":true}
```

- `"status":"ok"` — database reachable
- `"llm_configured":false` — your `GEMINI_API_KEY` isn't set; re-check `.env` and restart the
  `api` container

Then open **http://localhost:3000**.

Upload a resume on the home page, then save its AI draft as one or more named profiles —
each profile is an independent track (e.g. "Senior Android Developer" and "Senior Software
Engineer") that you review, edit, and later match separately. See the next guide.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `database:false` in health | The `db` container isn't ready yet or port 5432 is taken by another Postgres — `docker compose ps`, stop the conflicting service, retry |
| Port 3000/8000 already in use | Stop the other process or change the port mapping in `docker-compose.yml` |
| Frontend shows stale UI after code changes | The `web` container is missing the live source mounts (or predates them) — `docker compose up -d --build web`, then hard-refresh the browser |
| `llm_configured:false` | `GEMINI_API_KEY` missing in `.env`; restart `api` after editing |
| Frontend can't reach API | `NEXT_PUBLIC_API_BASE_URL` should be `http://localhost:8000` |

## Next

[Upload & profile review →](02-upload-and-profile.md)
