# 3 — Job Discovery & Matching

**Status: planned** — lands in Week 2 of v1 (issues #6–#11). This guide describes the
finished v1 behaviour.

## The idea

You search once; the app fans out to multiple job sources, normalizes and de-duplicates the
results, then ranks them against your saved profile — with a plain-language "why this
matches" on the best ones.

## The flow

<!-- diagram: job-discovery-flow -->
```mermaid
flowchart LR
    P["Saved profile"] --> Q["Search query + filters"]
    Q --> C1["Adzuna<br/>(official API)"]
    Q --> C2["Google Jobs actor<br/>(Apify scraper)"]
    Q --> C3["Indeed actor<br/>(Apify scraper)"]
    C1 --> N["Normalize + de-duplicate<br/>(source, external_id)"]
    C2 --> N
    C3 --> N
    N --> E["Embed job descriptions<br/>(your embedding provider)"]
    E --> F["Hard filters:<br/>location / remote / salary / type"]
    F --> V["Vector similarity ranking<br/>(pgvector cosine)"]
    V --> R["LLM re-ranks top N<br/>+ writes rationale"]
    R --> M["Ranked matches with<br/>why-this-matches"]
```

![job-discovery-flow diagram](../assets/job-discovery-flow.svg)

A failing source never breaks the search — it is skipped with a warning surfaced in the UI.

## What happens on a search (behind the scenes)

<!-- diagram: search-sequence -->
```mermaid
sequenceDiagram
    actor U as User
    participant B as Browser
    participant A as FastAPI
    participant I as Ingestion run<br/>(background)
    participant C as Job source connectors
    participant G as Gemini (via LiteLLM)
    participant D as Postgres + pgvector

    U->>B: click Search
    B->>A: POST /api/jobs/search
    A->>I: start background run
    A-->>B: run accepted (search happens async)
    I->>C: query each enabled source
    C-->>I: raw postings (failed source = skipped + warned)
    I->>I: normalize + de-duplicate
    I->>G: embed job descriptions
    I->>D: store postings + embeddings
    I->>D: hard filters + cosine similarity → top candidates
    I->>G: re-rank top N, generate rationale
    I->>D: store matches
    U->>B: open dashboard
    B->>A: GET /api/matches
    A-->>B: ranked matches + rationale
```

![search-sequence diagram](../assets/search-sequence.svg)

Searches run in the background — you can navigate away; results appear when the run
finishes.

## Choosing sources: official API vs third-party scraper

| Source | Type | Badge | Needs |
|---|---|---|---|
| Adzuna | Official API | "Official API" | Free Adzuna key |
| Google Jobs actor | Third-party scraper | "Third-party scraper" | Your Apify account |
| Indeed actor | Third-party scraper | "Third-party scraper" | Your Apify account |

Before a scraper-based source can be enabled you must **acknowledge its terms-of-use
disclosure** in a modal. The badge stays visible on every job card so you always know where
a listing came from. Scraping happens through *your* Apify account under *your* responsibility
— the app ships a tool, not a scraping service.

## Reading the results

- **Rank** — blend of vector similarity, your hard filters, and the LLM re-rank
- **"Why this matches"** — a generated explanation on the top matches, so you can judge the
  ranking instead of trusting a black box
- **Priority slider** — shift weighting between *role fit* and *company fit*; the ranking
  updates accordingly
- **Filters** — location, remote, job type, posting date

## Privacy

- Job search calls go only to the sources you enabled, using your keys/tokens
- Re-ranking and rationale generation use your configured LLM provider; only match-relevant
  text (job description vs profile) is sent — never your raw resume file

## Back

[← Upload & profile review](02-upload-and-profile.md) · [Getting started](01-getting-started.md)
