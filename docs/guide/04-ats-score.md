# ATS Score — score & fix your resume

Score a resume against a specific job description and get an AI-generated report with
concrete fixes. Nothing is persisted: each run is computed live and lives only in the
browser.

## Flow

1. Open **Get started → AI ATS Score** (`/ats`).
2. Pick a source:
   - **Upload a resume** — the same PDF/DOCX upload used for profile creation; the file is
     parsed for text only, no profile is drafted or saved.
   - **Use a saved profile** — pick one of your saved profile tracks.
3. Paste the job description (min 50 chars, max 15,000).
4. Press **Check ATS score** — Gemini compares the resume against the job
   (`POST /api/ats/score`, one structured call with a single repair retry; expect
   10–30 seconds, the page shows staged progress).

## The report

- **Overall score (0–100) + verdict** — recomputed server-side as the weighted mean of
  the category scores, so the score always matches the breakdown shown.
- **Category breakdown** — e.g. keyword match, role alignment, each with score, weight,
  analyst notes and per-category issues.
- **Keywords** — matched (green) and missing (red/amber), each graded critical /
  important / nice to have.
- **Strengths & gaps** — what already works and what the job wants that the resume does
  not evidence.
- **Suggestions** — prioritized, actionable fixes with rewrite examples. The AI is
  instructed to never invent experience; suggestions surface honest rewordings.

## Endpoints

| Method | Path | Notes |
|---|---|---|
| `POST` | `/api/ats/score` | Body: `resume_id` **or** `profile_id` (+ `job_description`). 502 if the LLM call fails, 404 for unknown ids, 422 for short/missing input. |

Requires `GEMINI_API_KEY` in the backend `.env` (same BYOK key as profile extraction).
