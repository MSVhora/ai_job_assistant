# Architecture

How AI Job Assistant fits together — components, data flows, and the database schema.
For day-to-day usage see the [user guide](guide/README.md); for scope see the
[v4 search-relevance plan](plans/v4/v4-search-relevance-plan.md) (earlier:
[v1](plans/v1/v1-implementation-plan.md), [v2](plans/v2/v2-implementation-plan.md),
[v3](plans/v3/v3-implementation-plan.md)).

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
        APY["Apify actor<br/>(LinkedIn jobs scraper,<br/>config-driven framework)"]
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

- `routers/` — HTTP only: parse, call a service, return a response model (evidence: `routers/evidence.py` → `services/evidence_sync.py`, `evidence_chunks.py`, `evidence_notes.py`, `evidence_items.py`, `achievement_extraction.py`, `achievements.py`; pure stages in `services/evidence_pipeline/`: `noise`, `chunking`, `dedupe`, `resume_ingest`)
- `services/` — business logic; raise domain errors
- `models/` — SQLAlchemy 2.0 ORM; the schema source of truth
- `adapters/llm.py` — the **only** place that talks to an LLM provider; it prices calls
  (`estimate_cost`: LiteLLM's price map, optional `LLM_PRICE_*` overrides, `unknown` when
  neither knows the model), logs `cost_usd` on every call and backs the confirm-gated
  cost estimates; it routes a model per task (`LLMTask`: classify, extract, write, judge, each
  with an optional `LLM_MODEL_<TASK>` override, falling back to `LLM_MODEL`), caps concurrent
  provider calls (`LLM_MAX_CONCURRENCY`, one semaphore per event loop) and meters tokens and
  cost per run (`usage_meter()`). Around it, `services/redaction.py` strips emails, phone
  numbers, IPs, tokens and keys from evidence text before it is sent or cached, and
  `services/llm_cache.py` caches structured outputs in `llm_output_cache` keyed by a SHA-256 of
  task, model, prompt version and the redacted inputs (a hit costs no tokens). It also owns
  resilience: the shared retry policy (`adapters/retry.py`, configurable via
  `LLM_RETRY_*`, default 3 attempts) applies exponential backoff with jitter on
  429/5xx/transport errors across LLM and job-source calls, honouring a provider's
  `Retry-After` hint (free-tier rate limits), plus the structured-output validation
  repair pass. Service-level errors wrap the cause hint, so the client sees
  "rate limited" / "timed out" instead of an opaque 502
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
    Note over A,G: a second small LLM call drafts per-source<br/>search-query specs into resume.search_queries<br/>(never fails the extraction)
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

    B->>A: POST /api/jobs/search (one source per run, with profile_id and filters)
    A->>A: resolve omitted filters from the profile (country, location, salary — request values always win)
    A->>D: sweep runs stuck in pending/running past MAX_RUN_AGE_MINUTES → marked failed (lock released)
    A->>D: active-run check — a non-terminal run for the same (profile, source)? → 409 + active run id
    A-->>B: background run accepted (resolved payload echoed on the run)
    A->>D: job_search row (status + per-source outcomes)
    A->>C: query the run's single source (freshness: Adzuna max_days_old, LinkedIn datePosted bucket)
    C-->>A: raw postings (failures skip + warn)
    A->>A: normalize + dedupe (source, external_id) — upsert refresh
    A->>G: embed descriptions
    A->>D: upsert postings + embeddings + search_posting rows (append-only)
    A->>D: cross-source dedupe pass — trigram+company+country grouping → canonical_id, merge rules (issue #38)
    A->>D: hard filters + hybrid signals (cosine, skill overlap, recency, salary fit) → ranked candidates (issue #37)
    A->>G: re-rank top N by hybrid score + rationale
    A->>D: store matches
    B->>A: GET /api/jobs/searches (profile_id) -> recent runs
    B->>A: GET /api/jobs/searches/{id}?profile_id= → run status + warnings (404 unless owned)
    B->>A: GET /api/jobs/searches/{id}/postings?profile_id= → unranked run results (404 unless owned)
    B->>A: GET /api/matches → ranked + "why this matches"
    B->>A: POST /api/matches/{id}/signals · GET /api/matches/{id}/apply → engagement signals (issue #39)
    B->>A: POST /api/profiles/{id}/tune-queries → confirm-gated LLM rewrite of stored query specs (issue #39)
    B->>A: POST · GET /api/profiles/{id}/rebuild-matches → scoped corpus rebuild run (issue #25)
```

![search-matching-sequence diagram](./assets/search-matching-sequence.svg)

## Evidence sync (sequence)

See [guide 04](guide/04-evidence-and-resume.md). The `EvidenceSource` interface
(`adapters/evidence_sources/`) is a stateful sibling of `JobSource`; the registry builds one source
instance per run because it owns the request budget and rate trackers.

<!-- diagram: evidence-sync-sequence -->
```mermaid
sequenceDiagram
    participant B as Browser
    participant A as FastAPI
    participant S as GitHubSource
    participant H as GitHub (REST + GraphQL)
    participant D as Postgres

    B->>A: GET /api/evidence/github/scopes
    A->>D: read the stored repository list (no GitHub call)
    B->>A: POST /api/evidence/github/scopes/refresh (first visit, or the Refresh button)
    A->>S: identify + list_scopes
    S->>H: GET /user, GET /user/repos, GraphQL contributionsCollection per year
    A->>D: upsert evidence_scope (new repos disabled), scopes_refreshed_at, token scopes
    B->>A: PATCH /api/evidence/github/scopes (enable, private needs the disclosure)
    B->>A: POST /api/evidence/github/sync (mode: incremental | full)
    A->>D: sweep stale runs, active-run check, insert evidence_sync_run (partial unique index)
    A-->>B: 202 sync_id
    loop each enabled scope, each page
        A->>S: sync_scope(scope + cursor)
        S->>H: repo summary (ETag) · commits · PRs · reviews · issues (budget + rate-limit floor checked first)
        S-->>A: SyncPage(items, next_cursor, requests_used)
        A->>A: noise.classify, content hash
        A->>D: upsert evidence_item, cursor and progress in one commit
    end
    A->>D: attach squash commits to their PR, status succeeded | paused (resume_at) | failed
    A->>D: rebuild chunks (redact, hash, diff), embed only chunks without a vector
    B->>A: GET /api/evidence/syncs/{id}
```

![evidence-sync-sequence diagram](./assets/evidence-sync-sequence.svg)

## Achievement extraction (sequence)

See [guide 04](guide/04-evidence-and-resume.md). Extraction is confirm-gated: the estimate is
computed from the real chunk prompts, and `POST /api/evidence/extract` must quote the estimate's
id, which changes when the evidence, the prompt version or the routed model changes.

<!-- diagram: achievement-extraction-sequence -->
```mermaid
sequenceDiagram
    participant B as Browser
    participant A as FastAPI
    participant G as LLM (LiteLLM, extract task)
    participant D as Postgres

    B->>A: POST /api/evidence/extract/estimate
    A->>D: chunks whose extracted_hash differs, plus llm_output_cache hits
    A-->>B: estimate_id, chunk counts, tokens, cost (or unavailable), private share
    B->>A: POST /api/evidence/extract (confirmed_estimate_id)
    A->>D: sweep stale runs, active-run check, insert run (partial unique index)
    A-->>B: 202 run_id
    loop each pending chunk
        A->>D: cache lookup (task, model, prompt version, redacted chunk)
        A->>G: chunk text + labelled evidence list (only on a cache miss)
        G-->>A: 0-3 achievements (schema-validated, one repair at most)
        A->>A: validators - evidence labels, verbatim numbers, result quote, placeholders
        A->>D: draft achievements, evidence links, ai_extraction revision, chunk.extracted_hash
        A->>G: embed the drafts (failure keeps the draft without a vector)
    end
    A->>D: archive drafts of vanished chunks, flag approved ones evidence_stale_at
    B->>A: GET /api/evidence/extract/runs/{id}, GET /api/achievements?status=draft
```

![achievement-extraction-sequence diagram](./assets/achievement-extraction-sequence.svg)

### Review, audit trail and the approval gate

`services/achievement_review.py` and `achievement_merge.py` are the only writers of an achievement
after extraction. `services/achievement_rules.py` holds the pure parts: the state table
(`draft → approved | rejected`, `approved → draft | archived`, `rejected → draft`), the approval
gate (at least one evidence link and no `needs_confirmation` metric), the stricter bulk-approval
gate (also no private-derived, flagged or stale rows) and the field-level diff. Every mutation writes
exactly one `achievement_revision` row (`manual_edit`, `status_change`, `metric_confirmation`,
`merge`, `split`), so the history is complete without whole-row snapshots. "Evidence changed" is
detected without a snapshot column: an approved achievement is flagged when a linked item's
`updated_at` is later than its latest revision, and the unchanged-item upsert in the sync keeps that
signal precise; re-review (`acknowledge`) writes a revision, which resets the baseline.

### Resume documents and reconciliation

A `resume_document` is structured data, never a stored file (a PDF is rendered on request): `ResumeContent` (JSON Resume-shaped
sections whose highlights are provenance-carrying `Bullet`s) plus layout, comments and the
kept-as-is conflict resolutions. `services/resume_mapping.py` maps a profile into it and back
losslessly (the server-managed `preferences` and `years_of_experience` are excluded and supplied by
the caller) and `services/resume_export.py` produces the clean text, Markdown and JSON Resume
outputs from the same content. `services/resume_reconcile.py` holds pure detectors over the profile,
the *approved* achievements and an optional GitHub identity; it only reports, so the profile is never
modified (resolving means editing the profile through the existing PATCH, or recording
"keep as is" on the document under a stable conflict key). GitHub name, location and public email
are fetched on demand for the identity check and never stored; without a token or on failure that
detector is skipped and the response says so. Saving content snapshots a
`resume_document_revision` and keeps the newest 20.

#### Content generation (#55)

`POST /api/resume-documents` also generates the content (still data, no PDF). `resume_builder`
loads the approved achievements (optionally without private-derived ones), analyses the JD
(`resume_jd`, `classify` task, cached by text) and embeds its digest, then ranks:
`resume_priority` computes a JD-independent base (impact, difficulty, recency), blends in the
alignment with weight w (`light` / `balanced` / `strong`, 0 without a JD), orders by MMR, scores
roles and drops the lower-priority one of any employment pair overlapping by
`RESUME_OVERLAP_MIN_DAYS`. The top `ceil(budget × RESUME_CANDIDATE_OVERSAMPLE)` candidates (always
including each block's best) go to `resume_writer`, one `write` call per block with the evidence
fenced as data and only the allowed JD terms offered (`resume_terms`). `resume_verify` checks every
drafted bullet by code (numbers, versions, years, tools, tense, length, filler, ownership verbs);
a `judge` call checks entailment; a failing bullet is rewritten once, then flagged `needs_review`.
`resume_comments` regenerates only commented blocks with the comment as a subordinate instruction;
`resume_bullets` re-checks user edits by code and records overrides. Everything the run produced
besides the content (pool, omitted roles, gaps, warnings, usage) is stored in
`resume_document.generation`. After every content change `persist` runs the page fit
(`resume_render/fit.py`) in a worker thread: it orders the passing bullets (pinned, role anchors,
then priority), binary-searches the longest prefix that fits the page target under three
typography presets by compiling the Typst template (`resources/typst/resume.typ`, content passed as
one JSON string) in memory and counting pages with `pdfplumber`, and stores the winning preset and
the included / not-included lists in `resume_document.layout`. If nothing fits, content is kept and
the layout is empty with a warning. `POST …/fit` re-fits on demand (layout only) and `POST …/render`
fits again and returns the PDF, which is never stored.

Search runs start **only** from an explicit `POST /api/jobs/search` — never automatically —
and are tracked in `job_search` (status + per-source `{source, status, count, warning}`
outcomes, queryable via `GET /api/jobs/searches/{id}`). A failing source is a run warning,
never an error. Background runs open fresh sessions from `session_factory` and commit
explicitly, since they outlive the request scope.

**One source per run (v3 issue #30):** `JobSearchRequest.source` is a required single
source (no more `sources` list); `source_queries` may only refine that source (mismatched
keys → 422). The UI's Start search wizard enforces the same shape. With a single source a
run is `succeeded` or `failed` — the `partial` status remains only for older stored rows.

**One active run per (profile, source) (v4 issue #36):** a partial unique index
`uq_job_search_active_run ON job_search (profile_id, source) WHERE status IN ('pending',
'running')` (enforcement survives multi-worker; `job_search.source` was backfilled from the
query echo in migration 0017) rejects a duplicate start; `start_search` returns **409
Conflict with the active run's id** (`{"detail", "active_search_id"}`), and the wizard
offers a "Go to active run" button wired into the run banner. Runs on *other* sources for
the same profile stay concurrent. Runs stuck past `MAX_RUN_AGE_MINUTES` (default 30) are
marked failed by a sweeper at the top of `start_search`, releasing the lock.

**Profile scoping (v3 issue #24):** every search is owned by a profile —
`JobSearchRequest.profile_id` is required (400 when absent, 404 for an unknown profile),
`job_search.profile_id` is NOT NULL, and both run-status/read endpoints require a
`profile_id` query param and answer 404 when it does not match the run's owner
(single-user app: state ownership, never leak across profiles). There is no
`latest_profile_id` fallback anymore. The posting↔search link lives in the append-only
`search_posting` join table (a posting re-found by a later search gains a row; nothing is
overwritten), which also replaces the mutable `job_posting.job_search_id` pointer.

**Scoped matching corpus + rebuild (v3 issue #25):** `rescore_matches` scores only the
profile's own corpus (postings joined through `search_posting → job_search.profile_id`)
— never the global postings table. Pre-scoping matches are never auto-deleted: the
explicit `POST /api/profiles/{id}/rebuild-matches` runs the scoped rescore as a
background task (status/metadata queryable via `GET`, banner shows corpus size) and
deletes that profile's out-of-corpus matches. On `/jobs` the selected profile rides in
the `?profile=` URL param and the search form refuses to submit without one.

**Read-side freshness (v3 issue #26):** matches and search results share one SQL filter —
closed postings (`is_closed`) or expired postings (`expires_at < now()`) never surface;
with no source-reported expiry a posting goes stale after `STALE_POSTING_DAYS`
(default 45) since `posted_at`. A source-reported expiry is authoritative (LinkedIn
`expireAt`); Adzuna has none, so the grace window governs. `posted_within_days` stacks on
top. The filter is read-time only — the scoring corpus and rebuild cleanup are untouched.

**Query-time freshness (v3 issue #27):** the search request accepts `max_days_old`
(1–90), rendered by `query_rendering.py` into every connector query. Adzuna sends it
directly (`max_days_old`); the LinkedIn actor input's `datePosted` resolves through the
`{date_posted_bucket}` YAML placeholder (≤1 → `past24Hours`, ≤7 → `pastWeek`, ≤30 →
`pastMonth`, else `anyTime`). Sources without a native parameter ignore it; the value is
echoed in the run's stored query.

## Source enablement (issue #8)

Sources come from a code-level registry plus **`connectors.yaml`**-configured Apify actors
(`backend/app/adapters/job_sources/connectors.yaml`) — adding an actor is a YAML entry plus
a `mappers/<source>.py` file, with no changes to matching logic. Enablement is DB-backed:

- `source_state.acknowledged_at` records the per-source disclosure acknowledgment
  (`POST /api/sources/{name}/enable` with `acknowledged_disclosure: true`; 409 without it)
- **enabled = key configured AND (official API OR disclosure acknowledged)** — checked
  against the DB at both request time and inside the background run (a failing re-check
  marks the run `failed` instead of stranding it in `running`)
- Official-API sources (Adzuna) auto-enable once their keys exist; scraping sources
  additionally require the disclosure modal

`POST /api/setup/check` reports which provider keys the backend detected plus an
embedding-capability warning, driving the `/setup` page.

## Per-source search queries

Search queries are **profile data**: a second LLM call at extraction drafts per-source
specs (`{title, skills, exclude}` per enabled source) into `resume.search_queries`; saving a
profile copies them; `POST /api/profiles/{id}/search-queries` regenerates from the current
content (temperature 0.8 + anti-repeat instruction, so Regenerate observably changes the
result). Generated specs are stamped `prompt_version` (`search_query_v3` since #31).

Since #31, generation consumes the **full profile** (skills, preferences, country,
summary — a shared digest builder also feeds the embedding, kept byte-identical) and is
cached by a content hash: `profile.queries_input_hash` = SHA-256 over the canonical
structured profile + enabled source names + filter declarations + `prompt_version`.
Automatic generation (extraction, background-refresh after a content-changing profile
save or a completed gap-fill turn) runs at temperature 0 and fires only when the stored
hash no longer matches the recomputed one; the manual regenerate endpoint always forces a
hot variant and rewrites the hash. Refresh runs happen in background tasks that open
fresh sessions — never in the request path.

Since #32, the profile carries deterministic derived experience signals: `years_of_experience`
is parsed from the verbatim experience date strings purely in Python (no LLM), and when the
user never set `preferences.seniority`, it is filled from YOE via Settings band thresholds
(`SENIORITY_BAND_*`), stamped `seniority_source: "derived"`. Derivation re-runs on every
extraction/create/save and after applied gap-fill turns; user-set values are never overwritten
and legacy provenance is treated as user-set. Both values join the shared digest builder, so
they reach the query-generation prompt and the profile embedding (old profiles re-embed
opportunistically on their next save); the rerank prompt picks them up via #37.

## Source filter capabilities (v3 issue #28)

Each `JobSource` declares its advanced filters in one schema (`SourceFilterDecl`: key,
label, type, select options, help text): Adzuna in code (`adzuna.py`), YAML-configured
actors in `connectors.yaml` (`filters:` per source). `GET /api/sources` serves the
declarations (`filters` field, alongside the legacy `supports_exclusions`), the backend
validates `source_queries[name].options` against the declaring source (unknown key /
bad type / bad enum → 400 naming the key), and connectors map validated options to
native parameters — Adzuna in `_apply_options`, YAML sources via
`{option:<key>}` placeholders in `connectors.yaml` (native types preserved; keys omitted
when unset). `query_rendering.py` stays the single render seam; a new source = a
declaration + mapper, with no changes to search logic.

Searches are **filter-first, precedence-in-rendering** (v4 issue #33): the renderer builds
a per-source **term plan** (`TermPlan`, carried on `JobSearchQuery`) whose slots are named
after Adzuna's params (`what_phrase`, `what_and`, `what_or`, `what_exclude`, `what`) plus
the LinkedIn slots (`keywords` NL brief, `date_posted` bucket). Adzuna precedence:
`what_phrase` + `what_and`/`what_or` combined; `what` only when no phrase. LinkedIn
precedence (v4 issue #35): a user-typed request `query` overrides the synthesized NL
brief `"{title} with {skills}, {seniority} level"` (seniority resolved from the
profile; no salary text); the spec's exclude terms are appended as a `not …` clause
in either case — NL is the only LinkedIn exclusion channel post-Aug-2026, and
`limitPerSource` is clamped by `MAX_APIFY_RESULTS_PER_RUN`. The
connectors act as mechanical plan→param mappers (dumb guard when a plan is empty);
connectors.yaml apify actors consume `keywords: "{keywords}"`,
`location: "{location}"`, `datePosted: "{date_posted_bucket}"` with plan-first
resolution. Unknown sources keep the plain free-text pass-through (`query`). The
normative precedence tables live in the `TermPlan`/connector docstrings and in
`services/query_rendering.py`; test_query_rendering.py locks the matrix per source.
`job_search.query` stores exactly what was sent, and the run status echoes it.
`what_and` is filled from the spec's must-have `skills_all` list (v4 issue #34).

Adzuna runs are **multi-pass within a call budget** (v4 issue #34): the connector
issues a broad pass and, when a title phrase exists and `title_only` was not
explicitly set, a `title_only` pass — deduped by `external_id` (broad pass wins)
— and paginates to page 2 only when a page fills its 50 rows and
`results_wanted` exceeds what is collected. Calls per run = Σ(sub-queries ×
pages), capped by `max_adzuna_calls_per_run` (default 4) with a stop-and-log,
never a run failure. With no salary floor set the connector also sends
`salary_include_unknown=1`.

## Database schema (ER diagram)

Source of truth: `backend/app/models/` + Alembic migrations. See
[plan §4](plans/v1/v1-implementation-plan.md#4-data-model) for the data model narrative.

`updated_at` on `candidate`, `profile`, `job_search`, `match`, `match_rebuild` and (since `0026`) `resume_document` is maintained by a
`set_updated_at()` database trigger (migration `0021`), so bulk `UPDATE`s bump it too; an update that
changes nothing leaves it alone, and one that sets it explicitly keeps that value. New tables with the
column add the trigger through `app/core/migration_helpers.py`. `job_posting.canonical_id` is
`ON DELETE SET NULL` (migration `0022`). `backend/scripts/audit_schema.py` is the read-only audit
(unindexed FKs, missing `ON DELETE`, nullable timestamps, unconventional names) that a test keeps empty.

<!-- diagram: database-schema-er -->
```mermaid
erDiagram
    candidate ||--o{ resume : "uploads"
    candidate ||--o{ profile : "tracks"
    profile ||--o{ profile_revision : "audit trail"
    profile ||--o{ match : "ranked against"
    profile ||--o{ job_search : "owns searches"
    job_search ||--o{ search_posting : "found by run"
    job_posting ||--o{ search_posting : "found in search"
    job_posting ||--o{ match : "produces"
    profile ||--o{ match_rebuild : "rebuild runs"
    candidate ||--o{ evidence_source : "connects"
    candidate ||--o{ evidence_item : "owns evidence"
    candidate ||--o{ evidence_chunk : "owns chunks"
    evidence_source ||--o{ evidence_scope : "opted-in repos"
    evidence_source ||--o{ evidence_sync_run : "sync runs"
    evidence_scope |o--o{ evidence_item : "ingested from"
    evidence_chunk ||--o{ evidence_chunk_item : "built from"
    evidence_item ||--o{ evidence_chunk_item : "in chunks"
    candidate ||--o{ achievement : "owns"
    achievement ||--o{ achievement_evidence : "cites"
    evidence_item ||--o{ achievement_evidence : "cited by"
    achievement ||--o{ achievement_revision : "audit trail"
    candidate ||--o{ achievement_extraction_run : "extraction runs"
    candidate ||--o{ resume_document : "owns"
    profile ||--o{ resume_document : "tailored from (CASCADE)"
    match |o--o{ resume_document : "job description from (SET NULL)"
    resume_document ||--o{ resume_document_revision : "snapshots (newest 20)"

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
        jsonb search_queries "per-source query specs + generation stamp; Regenerate overwrites"
        text queries_input_hash "SHA-256 of the query-generation inputs (issue #31); stored specs regenerate only when it changes"
        jsonb preferences "dashboard view preference {priority: 0-1} — role-fit vs company-fit weighting at match read time (issue #11); distinct from resume-derived prefs inside structured_profile"
        uuid source_resume_id FK "resume whose draft seeded this profile (provenance)"
        vector embedding "pgvector, dim 768 (gemini-embedding-001, truncated via dimensions param); refreshed on every content save/gap-fill"
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
        jsonb search_queries "LLM-drafted per-source query specs (queries follow-up)"
        timestamptz created_at
    }

    profile_revision {
        uuid id PK
        uuid profile_id FK "revisions belong to a profile, not the candidate"
        text source "ai_extraction | manual_edit | gap_fill | reupload_merge"
        jsonb diff "field-level {field: {old, new}}"
        timestamptz created_at
    }

    job_search {
        uuid id PK
        uuid profile_id FK "owning profile — searches are profile-scoped (v3 #24); cascade on profile delete"
        text source "the one source this run targets (issue #36); partial unique index (profile_id, source) while pending/running"
        text status "pending | running | succeeded | partial | failed"
        jsonb query "validated search request (issue #7)"
        jsonb results "per-source {source, status, count, warning?}"
        jsonb matching "per-run MatchingOutcome: status, counts, rerank token usage (issue #10)"
        timestamptz created_at
        timestamptz updated_at
    }

    search_posting {
        uuid id PK
        uuid search_id FK "run that found the posting; CASCADE"
        uuid posting_id FK "CASCADE"
        timestamptz created_at "append-only: unique (search_id, posting_id), nothing overwritten (v3 #24)"
    }

    job_posting {
        uuid id PK
        text source "adzuna | apify_linkedin | ..."
        text external_id "unique together with source — dedupe key"
        text title
        text company
        text url "posting click-through link"
        text location
        text country "run's resolved 2-letter country — dedupe grouping key (issue #38); null for pre-#38 rows"
        text job_type "native enum, nullable"
        text remote_type "native enum, nullable"
        text description
        uuid canonical_id FK "self-FK: null = own canonical; duplicates point at the canonical row (issue #38) — trigram-merged, matches collapse onto it"
        jsonb source_urls "merged record [{source, url}] of duplicates folded into this canonical row (issue #38)"
        timestamptz posted_at
        timestamptz expires_at "source-reported (LinkedIn expireAt); null when unknown"
        boolean is_closed "not null, default false; future seam — no producing source yet (v3 #26)"
        numeric salary_min
        numeric salary_max
        text currency
        jsonb raw_payload "original source data for debugging/re-mapping"
        vector embedding "pgvector, dim 768 (gemini-embedding-001, truncated via dimensions param); null when the embed call failed"
        timestamptz fetched_at
    }

    match {
        uuid id PK
        uuid profile_id FK "matching unit is the profile (owner decision 2026-09-02); CASCADE on profile or posting delete"
        uuid job_posting_id FK
        real vector_score "clamped cosine similarity (1 - distance), SQL-computed; null for un-embedded postings (issue #37 fallback)"
        real skill_score "top-skill word-boundary hit fraction over title+description, SQL (issue #37)"
        real recency_score "exp(-days_since_posting/match_recency_decay_days), 0.5 for unknown dates (issue #37)"
        real salary_score "salary-band fit: 1.0 unknown, 0.5 without a preference band (issue #37)"
        real role_fit "LLM re-rank 0-10, null when not re-ranked; stored so #11 can re-weight without an LLM call"
        real company_fit "LLM re-rank 0-10, null when not re-ranked"
        real final_score "weighted blend (vector, skill, recency, salary + LLM verdicts; issue #37) — fallback rows renormalize skill+recency+salary"
        text rationale "LLM why-this-matches, top N only; cleared when profile content changes"
        timestamptz first_opened_at "first job-detail open, first-write-wins (issue #39)"
        timestamptz clicked_apply_at "first apply-URL redirect click via /api/matches/{id}/apply (issue #39)"
        timestamptz saved_at "explicit one-click save; unsave clears it (issue #39)"
        timestamptz dismissed_at "explicit dismiss — hides the match from the default list; undismiss clears (issue #39)"
        timestamptz created_at
        timestamptz updated_at
    }

    match_rebuild {
        uuid id PK
        uuid profile_id FK "CASCADE"
        text status "pending | running | succeeded | failed"
        integer corpus_count "postings found by this profile's searches (scoped corpus size)"
        integer scored_count "corpus postings that had embeddings to score"
        text warning "degraded-notice, e.g. re-rank unavailable"
        timestamptz created_at
        timestamptz updated_at
    }

    source_state {
        text source_name PK
        timestamptz acknowledged_at "disclosure acknowledgment — null until enabled (issue #8)"
    }

    evidence_source {
        uuid id PK
        uuid candidate_id FK "RESTRICT"
        text kind "github | notes | resume; unique per candidate"
        text account_login
        jsonb extra_identities "emails for commit matching"
        timestamptz acknowledged_at "private-repo disclosure ack"
        timestamptz last_synced_at
        timestamptz scopes_refreshed_at "when the repository list was last read from GitHub"
        jsonb token_scopes "classic token scopes at that refresh"
        timestamptz created_at
    }

    evidence_scope {
        uuid id PK
        uuid source_id FK "CASCADE"
        text ref "owner/repo; unique per source"
        boolean is_private
        boolean is_fork
        text description
        timestamptz pushed_at
        boolean contributed "GitHub contribution history includes it"
        boolean visible "listed by the latest refresh"
        boolean new_since_refresh "first seen in the latest refresh"
        boolean enabled "default false"
        text content_level "messages_and_prs | metadata_only"
        jsonb employer_ref
        jsonb cursor "per-scope resume point"
        text sync_state "pending | running | paused | succeeded | failed"
        timestamptz last_synced_at
        timestamptz created_at
        timestamptz updated_at
    }

    evidence_sync_run {
        uuid id PK
        uuid source_id FK "CASCADE; one pending/running run per source (partial unique index)"
        text status "pending | running | paused | succeeded | failed"
        jsonb progress
        jsonb rate_limit
        timestamptz resume_at
        text error
        jsonb usage
        timestamptz created_at
        timestamptz updated_at
    }

    evidence_item {
        uuid id PK
        uuid candidate_id FK "RESTRICT"
        uuid scope_id FK "SET NULL"
        text kind "commit | pull_request | review_comment | issue | readme | repo_summary | note | link | resume_line"
        text external_id "unique with candidate + kind"
        text project_key
        text body
        timestamptz occurred_at
        text status "kept | filtered | excluded"
        text filter_reason "noise-filter rule that dropped it"
        boolean is_private "copied from scope; drives provenance marking"
        jsonb meta
        text content_hash
        timestamptz created_at
        timestamptz updated_at
    }

    evidence_chunk {
        uuid id PK
        uuid candidate_id FK "RESTRICT"
        text kind
        text text
        integer token_count "CHECK >= 0"
        text content_hash
        text chunker_version
        text extracted_hash
        boolean contains_private
        vector embedding "vector(768), nullable, no ANN index"
        timestamptz created_at
        timestamptz updated_at
    }

    evidence_chunk_item {
        uuid chunk_id PK "FK CASCADE"
        uuid item_id PK "FK CASCADE"
    }

    achievement {
        uuid id PK
        uuid candidate_id FK "RESTRICT"
        text status "draft | approved | rejected | archived (only approved is used downstream)"
        text origin "ai_extracted | user_created | merged"
        text title
        text situation
        text task
        text action
        text result "null unless the evidence states an outcome"
        jsonb metrics "text, source_quote, evidence_ids, verified: evidence | user | needs_confirmation"
        jsonb skills "canonicalized tags"
        text impact_type
        smallint difficulty "CHECK 1-5"
        text project_key
        jsonb employer_ref "scope or suggested"
        date time_start
        date time_end
        vector embedding "vector(768), nullable, no ANN index"
        text source_chunk_hash "chunk the draft came from"
        jsonb review_flags
        boolean derived_from_private
        timestamptz evidence_stale_at
        timestamptz created_at
        timestamptz updated_at
    }

    achievement_evidence {
        uuid id PK
        uuid achievement_id FK "CASCADE"
        uuid item_id FK "RESTRICT, unique with achievement"
        text role "primary | supporting"
        text quote
    }

    achievement_revision {
        uuid id PK
        uuid achievement_id FK "RESTRICT"
        text source "ai_extraction | manual_edit | merge | split | metric_confirmation | status_change"
        jsonb diff
        timestamptz created_at
    }

    achievement_extraction_run {
        uuid id PK
        uuid candidate_id FK "RESTRICT, one pending/running run per candidate (partial unique index)"
        text status "pending | running | paused | succeeded | failed"
        jsonb estimate "the confirmed estimate"
        jsonb progress
        jsonb usage "tokens and cost"
        text error
        timestamptz created_at
        timestamptz updated_at
    }

    resume_document {
        uuid id PK
        uuid candidate_id FK "RESTRICT"
        uuid profile_id FK "CASCADE, the profile the identity is copied from"
        uuid match_id FK "SET NULL, nullable"
        varchar title
        smallint page_target "CHECK 1 to 4"
        real jd_weight "CHECK 0 to 0.5"
        varchar template
        text job_description
        varchar jd_hash
        jsonb content "ResumeContent with per-bullet provenance"
        jsonb layout "page-fit result: pages, preset, included and not-included bullets"
        jsonb conflicts "kept-as-is resolutions, keyed by conflict key"
        jsonb comments "open | applied | rejected, with reasons"
        jsonb generation "ranked pool, omitted roles, gaps, JD analysis, warnings, usage"
        text status "draft | final"
        integer version
        timestamptz created_at
        timestamptz updated_at
    }

    resume_document_revision {
        uuid id PK
        uuid document_id FK "CASCADE"
        integer version
        jsonb content
        varchar source "create | manual_edit | generate | bullet_edit | apply_comments"
        timestamptz created_at
    }

    llm_output_cache {
        text key PK "SHA-256 of task, model, prompt version, redacted inputs; not candidate-owned"
        text task
        text model
        text prompt_version
        jsonb output
        integer prompt_tokens
        integer completion_tokens
        timestamptz created_at
    }
```

![database-schema-er diagram](./assets/database-schema-er.svg)

Deferred from plan §4 (issue #4 locked decision): the separate `completeness` jsonb
column — gap-fill (#5) derives completeness from the profile instead of storing it. The
`preferences` (weights) column deferred alongside it landed with the priority slider
(issue #11): it holds the per-profile dashboard *view* weight
(`{priority: float 0–1}`, role-fit vs company-fit at match read time), distinct from the
resume-derived preferences inside `structured_profile`, and is deliberately
revision-free. Preferences extracted from the resume stay inside the profile's
`structured_profile`; the matching work (#10) reads blend weights from `Settings`
(`MATCH_WEIGHT_*` in `.env.example`) and stores the re-rank sub-scores on `match` so the
slider re-weights without an LLM call. Engagement timestamps (#39) land on `match`
as nullable timestamptz (`first_opened_at`, `clicked_apply_at`, `saved_at`,
`dismissed_at`): implicit signals ride existing behavior (detail open; the apply
redirect endpoint), the two explicit ones are one-click and reversible, and a manual
`tune-queries` pass aggregates them to rewrite stored query specs. The stored
`queries_input_hash` is overwritten with the current-inputs hash at tune time so the
freshness guard cannot revert the tuned specs. Multi-profile moved the opposite way — from v2
into v1 (issue #6, owner decision 2026-09-01): `profile` is now the home of
`structured_profile` and the revision audit.

Schema conventions and index rules (FK columns indexed, `(source, external_id)` unique,
`match(profile_id, final_score DESC)` for the dashboard query, embedding dimension pinned
to the embedding model) live in
[instructions/database-postgres.md](instructions/database-postgres.md).

## Privacy posture

- Single implicit user, no auth — designed for localhost / your own Docker host
- BYOK: only your configured LLM and job-source providers are called, with your keys
- Resume text is stored locally (Postgres + uploads volume) and sent only to your LLM provider
- Scraping-based sources run under your own Apify account after an explicit disclosure
  acknowledgment
- CORS allows only `CORS_ORIGINS`, the methods `GET/POST/PATCH/DELETE/OPTIONS` and the request
  headers `Content-Type`/`Accept`; `X-Total-Count` is exposed so the UI can read list totals
- Every outbound call has an explicit timeout: job-source clients 30 s, LLM and embedding
  calls `LLM_TIMEOUT_S` (default 60 s); a timeout is retried by the shared policy and reported
  as "request timed out"
- List endpoints are bounded (`limit` default 100, max 200, plus `offset`, total in
  `X-Total-Count`): profiles, resumes, matches; recent runs default to 20; a run's postings
  default to 250 (max 1000) so a full run is returned
- Error contract: every error body is `{"detail": "<message>"}`, with extra machine keys only
  where documented (`active_search_id` on the duplicate-run 409); a test enumerates every
  `DomainError` subclass against it
- Logs never contain resume text, prompts, job descriptions or key-shaped strings (a regression
  test runs upload → extract → profile → search under log capture)
