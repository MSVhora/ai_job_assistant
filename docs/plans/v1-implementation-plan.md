# AI Job Assistant — v1 Implementation Plan

**Status:** Approved plan for v1
**Synthesizes:** `~/Downloads/Job Platform.md` (PRD) + `~/Downloads/PROJECT_PLAN.md` (execution plan)
**License:** MIT

---

## 1. What v1 Is

A self-hosted, single-user, BYOK web app:

> Upload a resume → review/edit the AI-extracted profile → discover jobs from 3+ sources → get ranked matches with plain-language explanations.

### In scope
1. **Profile pipeline** — resume upload/parse → structured profile via LLM → human review/edit → conversational gap-filling → persistent profile with revision audit trail.
2. **Job discovery** — Adzuna (official API) + 2 Apify actors (Google Jobs, Indeed) behind a `JobSource` plugin interface. New actors added via **config + mapper, not core code**. Scraping-based sources show a ToS disclosure and require per-source acknowledgment before enabling.
3. **Matching** — pgvector cosine similarity + hard filters (location/remote/salary/type) + LLM re-rank of top N with rationale + priority weighting (role-fit vs. company-fit).

### Explicitly out of scope (deferred)
| Item | When |
|---|---|
| ATS single-JD scorer (keyword + semantic + structural breakdown) | v1.1 fast-follow — highest-priority next feature |
| Resume rewriting / health check | v1.2 |
| Multi-profile ("Data Analyst" vs "PM" tracks) | ~~v2~~ **moved into v1** (owner decision 2026-09-01 — see [issue #6 plan](v1-issue-006-multi-profile-resume-list.md)) |
| Auth / multi-user | v2 |
| Redis/Celery queue (BackgroundTasks suffice at single-user scale) | v2 |
| JSearch, LinkedIn/Naukri actors, company career-page scraper, alerts | Phase 3+ |
| Auto-apply / form autofill | Never in core (Phase 4 Chrome extension, separate) |

---

## 2. Locked Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Backend | **Python / FastAPI** | Both plans converge; async-native, pydantic for schema enforcement |
| Frontend | **Next.js + TypeScript** | Upload/review UI + dashboard need a real SPA |
| Database | **Postgres + pgvector** | Structured data + embeddings in one store |
| LLM abstraction | **LiteLLM** | Don't hand-roll provider adapters; swapping = config change |
| Default LLM | **Gemini Flash** | Free tier = zero-cost demo for every forker; strong structured output |
| Embeddings | Gemini `text-embedding-004` (via LiteLLM) | Same key as generation; note: Anthropic-only users will need a second provider for embeds — detect and warn at setup |
| Job sources | **Adzuna + 2 Apify actors** | Adzuna proves the connector pattern with zero setup; Apify adds LinkedIn/Indeed-grade coverage under the user's own account |
| Scraping posture | User runs actors under **their own Apify key**; per-source disclosure + acknowledgment in UI | Ships a tool, not a scraping service (PRD §9) |
| Profile storage | `structured_profile` **jsonb** + `profile_revision` audit table | Field-level diffing at the app layer; normalized child tables deferred until rewriting needs per-bullet references |
| Auth | None — single implicit user, localhost/Docker | Speed |
| Background work | FastAPI `BackgroundTasks` | No Redis dependency for v1 |
| Deployment | Docker Compose, `.env.example` for all keys | Fork → fill keys → run |

---

## 3. Architecture

```
[Next.js Frontend]
   ├─ Setup check (keys configured? source disclosures)
   ├─ Resume upload + profile review/edit
   ├─ Conversational gap-fill
   └─ Job dashboard: filters, source badges, ranked matches + rationale

[FastAPI Backend]
   ├─ Resume Parser      (pdfplumber / python-docx → text)
   ├─ Extraction Service (text → structured JSON profile via LiteLLM → Gemini, schema-constrained)
   ├─ Profile Service    (CRUD + revision audit + gap-fill chat)
   ├─ Ingestion Service  (JobSource registry: Adzuna native, Apify actor runner)
   └─ Matching Engine    (pgvector cosine + hard filters → LLM re-rank top N → rationale)

[Postgres + pgvector]
```

---

## 4. Data Model

```sql
candidate
├── id (uuid, pk)
├── structured_profile (jsonb)        -- contact, headline, skills[], experience[], education[], prefs
├── preferences (jsonb)               -- weights (role vs company), filters, target title/location
├── completeness (jsonb)              -- which fields present/missing (drives gap-fill)
├── created_at, updated_at

resume
├── id (uuid, pk), candidate_id (fk)
├── file_path, parsed_at, parse_version   -- LLM model + prompt version, for reproducibility

profile_revision                     -- audit: AI extraction vs human fixes (showcase-able)
├── id (uuid, pk), candidate_id (fk)
├── source ('ai_extraction' | 'manual_edit' | 'gap_fill' | 'reupload_merge')
├── diff (jsonb)                     -- field-level {field: {old, new}}
├── created_at

job_posting
├── id (uuid, pk)
├── source ('adzuna' | 'apify_google_jobs' | 'apify_indeed' | ...)
├── external_id                      -- dedupe key: (source, external_id) unique
├── title, company, location, job_type, remote_type
├── description (text), posted_at, salary_min, salary_max, currency
├── raw_payload (jsonb)              -- original source data for debugging/re-mapping
├── embedding (vector)               -- computed on ingest
├── fetched_at, search_query_id (fk, nullable)

match
├── id (uuid, pk), candidate_id (fk), job_posting_id (fk)
├── vector_score, final_score        -- pre-weight and post-weight/rerank
├── rationale (text)                 -- LLM "why this matches", top N only
├── created_at
```

---

## 5. Connector Interface & Apify Config

```python
class JobSource(Protocol):
    name: str
    is_official_api: bool          # drives UI badge + disclosure requirement
    def search(self, query: JobSearchQuery) -> list[RawJobPosting]: ...
    def normalize(self, raw: RawJobPosting) -> JobPosting: ...
```

Adding a new Apify actor = a YAML entry + thin mapper, no core changes:

```yaml
# connectors.yaml
sources:
  - name: adzuna
    type: native_api
    disclosure: none
  - name: apify_google_jobs
    type: apify_actor
    actor_id: <chosen from Apify Store at build time>
    input_mapping: { keywords: "{query}", location: "{location}" }
    output_path: dataset.items
    disclosure: required
  - name: apify_indeed
    type: apify_actor
    actor_id: <chosen at build time>
    disclosure: required
```

**Apify runner contract:** start run → poll until `SUCCEEDED` → fetch dataset items → per-actor mapper → normalized `JobPosting`. Actor failures degrade gracefully (source skipped, warning surfaced in UI), never break the whole search.

---

## 6. API Surface

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/setup/check` | Which keys are configured; embedding-capable provider present? |
| POST | `/api/resume` | Upload PDF/DOCX → parse → draft profile (not saved yet) |
| GET/PATCH | `/api/profile` | Read/update profile; every PATCH writes a `profile_revision` |
| POST | `/api/profile/gap-fill` | Conversational missing-field flow (location, salary band, seniority, work auth, remote pref) |
| GET | `/api/sources` | Available sources + `is_official_api` + disclosure text |
| POST | `/api/sources/{name}/enable` | Enable; body must include `acknowledged_disclosure: true` for scraping sources |
| POST | `/api/jobs/search` | `{query, filters, sources[], seed: "profile"\|"manual"}` → ingestion run (background) |
| GET | `/api/matches` | Ranked matches + rationale; filter/sort params |

---

## 7. Frontend Pages

1. **Setup** — key status per provider, embedding-gap warning, source list with Official API / Third-party scraper badges + disclosure modal on enable.
2. **Upload & Profile Review** — parsed profile form, AI-extracted fields highlighted, inline edit, re-upload → merge/diff review.
3. **Gap-fill chat** — targeted questions for missing fields only.
4. **Job Dashboard** — search bar (seeded from profile), filters (location/remote/type/date), source badges, ranked match cards with expandable "why this matches", priority-weight slider (role-fit ↔ company-fit).

---

## 8. Build Plan (2 Weeks)

### Week 1 — Profile pipeline
| Day | Task |
|---|---|
| 1 | Scaffold: docker-compose (api, web, db+pgvector), `.env.example`, MIT LICENSE, LiteLLM wired to Gemini Flash, health check endpoint |
| 1–2 | Upload endpoint + text extraction (pdfplumber for PDF, python-docx for DOCX) |
| 2–3 | Structured extraction: text → JSON profile via Gemini with pydantic-validated schema; `parse_version` stamping; retry/repair on invalid JSON |
| 3 | Profile persistence + review/edit UI + `profile_revision` audit |
| 4 | Conversational gap-fill for missing fields |
| 5 | Buffer / end-to-end polish of profile flow (upload → review → gap-fill → saved profile) |

### Week 2 — Ingestion + matching
| Day | Task |
|---|---|
| 6 | `JobSource` interface + Adzuna adapter (free key only) + normalization + `(source, external_id)` dedupe |
| 7 | Apify connector framework + Google Jobs actor + Indeed actor config; source disclosure UI + enable flow |
| 8 | Embeddings: profile + job descriptions → pgvector; hard filters in SQL |
| 9 | Matching: cosine ranking + LLM re-rank of top N + rationale generation |
| 10 | Priority-weight slider wired into ranking; README + `.env.example` docs + demo GIF |
| Buffer | Seed data, error states, rate-limit backoff |

---

## 9. v1 Acceptance Criteria

- From a clean clone: fill `.env`, `docker compose up`, upload a standard single-column resume → editable profile in <30s on the free Gemini tier.
- User can correct every AI-extracted field; every correction is recorded in `profile_revision`.
- Gap-fill asks only about genuinely missing fields.
- All 3 sources return normalized postings; dedupe across sources works; a new Apify actor can be added via `connectors.yaml` + mapper without touching matching logic.
- Ranked matches with a "why this matches" rationale for at least the top 10.
- Scraping sources cannot be enabled without acknowledging the ToS disclosure; badge visible on every card.
- No resume content ever leaves the deployment except to the user's own configured LLM/Apify providers.

---

## 10. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Apify actor quality/breakage varies | `raw_payload` retained; mapper isolated per actor; failed source degrades gracefully |
| Gemini free-tier rate limits | Backoff + retry; batch embeddings; cap re-rank to top N |
| Adzuna geo coverage gaps | Source status surfaced per search; more connectors are config-only additions |
| Embedding provider gap (e.g., Anthropic-only user) | Setup check warns before first search, not at failure time |
| Actor output schema drift | Mappers versioned alongside `connectors.yaml` |

---

## 11. Fast-Follows (post-v1)

1. **ATS scorer** (v1.1) — single JD vs. profile: keyword overlap + semantic + structural sub-scores with plain-language explanation (PRD §5.2, minus the resume-file structural checks until we keep the raw file handy).
2. **Resume rewriting** (v1.2) — requires normalized child tables for per-bullet edits; plan that migration before starting.
3. JSearch adapter · saved searches · multi-profile support · Redis queue · multi-user auth.
