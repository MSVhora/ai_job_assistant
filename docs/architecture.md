# Architecture

How AI Job Assistant fits together — components, data flows, and the database schema.
For day-to-day usage see the [user guide](guide/README.md); for scope see the
[v1 implementation plan](plans/v1-implementation-plan.md).

## System overview (flow diagram)

<!-- diagram: system-overview -->
```mermaid
flowchart TB
    U["User (browser)"]
    W["Next.js frontend :3000<br/>App Router · TanStack Query"]
    A["FastAPI backend :8000<br/>routers → services → adapters"]
    subgraph Stores
        DB[("Postgres + pgvector :5432")]
        FS["data/uploads volume<br/>(resume files, UUID names)"]
    end
    subgraph External["External services — all BYOK, your keys"]
        LLM["Gemini via LiteLLM<br/>generation + embeddings"]
        ADZ["Adzuna API<br/>(official)"]
        APY["Apify actors<br/>(Google Jobs, Indeed scrapers)"]
    end

    U --> W
    W -- "typed API client<br/>(lib/api)" --> A
    A --> DB
    A --> FS
    A -- "LLM calls only via<br/>adapters/llm.py" --> LLM
    A -- "source calls only via<br/>JobSource connectors" --> ADZ
    A --> APY
```

![system-overview diagram](./assets/system-overview.svg)

Non-negotiable layering rules (enforced by the
[coding standards](instructions/)):

- `routers/` — HTTP only: parse, call a service, return a response model
- `services/` — business logic; raise domain errors
- `models/` — SQLAlchemy 2.0 ORM; the schema source of truth
- `adapters/llm.py` — the **only** place that talks to an LLM provider
- `JobSource` connector protocol — the **only** way a job source is added
- Every schema change ships as an Alembic migration in the same change
- `DbCommitMiddleware` commits each request's session **before the response reaches the
  client** — a response that returned 2xx implies durable state (fixed the upload → extract
  race where the client read a row before its transaction committed)

## Profile pipeline (sequence)

See the full walkthrough in [guide 02](guide/02-upload-and-profile.md):

<!-- diagram: profile-pipeline-sequence -->
```mermaid
sequenceDiagram
    participant B as Browser
    participant A as FastAPI
    participant G as Gemini (LiteLLM)
    participant D as Postgres

    B->>A: POST /api/resumes — PDF / DOCX (multipart)
    A->>D: candidate + resume row (draft text only)
    A-->>B: extracted text
    B->>A: POST /api/resumes/{id}/extract
    A->>G: resume text + JSON schema → profile JSON
    Note over A,G: prompt-instructed JSON — pydantic-validated<br/>with one repair round-trip on failure
    A->>D: stamp parse_version + persist draft_profile (parse artifact)
    A-->>B: draft profile — NOT a saved profile
    B->>A: PATCH /api/profiles/{id} — reviewed profile (content save)
    A->>D: save profile.structured_profile + profile_revision diff rows
    A-->>B: saved profile with revision audit (issue #4)
    Note over B,D: a draft can also be saved as an additional profile (multi-profile, issue #6)
    loop gap-fill turns (issue #5)
        B->>A: POST /api/profiles/{id}/gap-fill — conversation so far
        A->>A: compute genuinely missing fields (server-side, deterministic)
        A->>G: transcript + missing fields → validated answers + next question
        A->>D: merge pydantic-validated answers + gap_fill revision row
        A-->>B: reply, applied fields, still-missing, updated profile
    end
    Note over A: nothing missing → canned reply, no LLM call
```

![profile-pipeline-sequence diagram](./assets/profile-pipeline-sequence.svg)

## Search + matching (sequence)

See the full walkthrough in [guide 03](guide/03-job-discovery-and-matching.md):

<!-- diagram: search-matching-sequence -->
```mermaid
sequenceDiagram
    participant B as Browser
    participant A as FastAPI
    participant C as JobSource connectors
    participant G as Gemini (LiteLLM)
    participant D as Postgres + pgvector

    B->>A: POST /api/jobs/search
    A-->>B: background run accepted
    A->>C: query enabled sources
    C-->>A: raw postings (failures skip + warn)
    A->>A: normalize + dedupe (source, external_id)
    A->>G: embed descriptions
    A->>D: upsert postings + embeddings
    A->>D: hard filters + cosine → top N
    A->>G: re-rank top N + rationale
    A->>D: store matches
    B->>A: GET /api/matches → ranked + "why this matches"
```

![search-matching-sequence diagram](./assets/search-matching-sequence.svg)

## Database schema (v1, ER diagram)

Source of truth: `backend/app/models/` + Alembic migrations. See
[plan §4](plans/v1-implementation-plan.md#4-data-model) for the data model narrative.

<!-- diagram: database-schema-er -->
```mermaid
erDiagram
    candidate ||--o{ resume : "uploads"
    candidate ||--o{ profile : "tracks"
    profile ||--o{ profile_revision : "audit trail"
    candidate ||--o{ match : "ranked against"
    job_posting ||--o{ match : "produces"

    candidate {
        uuid id PK
        timestamptz created_at
        timestamptz updated_at
    }

    profile {
        uuid id PK
        uuid candidate_id FK
        text name "track name, e.g. Senior Android Developer"
        jsonb structured_profile "contact, headline, skills, experience, projects, education, certifications, extra sections, embedded preferences"
        uuid source_resume_id FK "resume whose draft seeded this profile (provenance)"
        timestamptz created_at
        timestamptz updated_at
    }

    resume {
        uuid id PK
        uuid candidate_id FK
        text file_path "relative path under uploads_dir"
        text original_filename "metadata only, never used for storage path"
        text content_type
        integer size_bytes
        text extracted_text "stored at parse time (issue #2)"
        integer page_count "PDF only"
        timestamptz parsed_at
        text parse_version "text_v1 at upload; model+prompt version after extraction (issue #3)"
        jsonb draft_profile "AI-extracted draft — parse artifact, not a saved profile (issue #3)"
        timestamptz created_at
    }

    profile_revision {
        uuid id PK
        uuid profile_id FK "revisions belong to a profile, not the candidate"
        text source "ai_extraction | manual_edit | gap_fill | reupload_merge"
        jsonb diff "field-level {field: {old, new}}"
        timestamptz created_at
    }

    job_posting {
        uuid id PK
        text source "adzuna | apify_google_jobs | apify_indeed | ..."
        text external_id "unique together with source — dedupe key"
        text title
        text company
        text location
        text job_type
        text remote_type
        text description
        timestamptz posted_at
        integer salary_min
        integer salary_max
        text currency
        jsonb raw_payload "original source data for debugging/re-mapping"
        vector embedding "pgvector, dim 768 (text-embedding-004)"
        timestamptz fetched_at
        uuid search_query_id FK "nullable; search_query table lands with ingestion (issue #7)"
    }

    match {
        uuid id PK
        uuid candidate_id FK
        uuid job_posting_id FK
        real vector_score "pre-weight cosine similarity"
        real final_score "post-weight/rerank"
        text rationale "LLM why-this-matches, top N only"
        timestamptz created_at
    }
```

![database-schema-er diagram](./assets/database-schema-er.svg)

Deferred from plan §4 (issue #4 locked decision): the separate `preferences` (weights) and
`completeness` jsonb columns. Preferences extracted from the resume stay inside the
profile's `structured_profile`; the priority-weight column lands with the matching work
that consumes it, and gap-fill (#5) derives completeness from the profile instead of
storing it. Multi-profile moved the opposite way — from v2 into v1 (issue #6, owner
decision 2026-09-01): `profile` is now the home of `structured_profile` and the revision
audit.

Schema conventions and index rules (FK columns indexed, `(source, external_id)` unique,
`match(candidate_id, final_score DESC)` for the dashboard query, embedding dimension pinned
to the embedding model) live in
[instructions/database-postgres.md](instructions/database-postgres.md).

## Privacy posture

- Single implicit user, no auth — designed for localhost / your own Docker host
- BYOK: only your configured LLM and job-source providers are called, with your keys
- Resume text is stored locally (Postgres + uploads volume) and sent only to your LLM provider
- Scraping-based sources run under your own Apify account after an explicit disclosure
  acknowledgment
