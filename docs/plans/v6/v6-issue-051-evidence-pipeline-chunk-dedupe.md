# Issue #51 — Evidence pipeline: chunking, dedupe, notes/links, resume ingestion, chunk embeddings (Week 2)

**Status:** Proposed — for owner review
**Tracks:** GitHub issue #51 (milestone `v6`, branch `v6/43-evidence-pipeline-chunk-dedupe`)
**Plan of record:** [v6-implementation-plan.md](v6-implementation-plan.md) §4.4–4.5, §12 (redaction)
**Depends on:** #48, #49 (redaction, `embed` usage), #50 (items to chunk)
**Blocks:** #52 (chunks are the extraction unit)

---

## Goal

Turn stored `evidence_item` rows into **chunks** (the extraction and retrieval unit), add the two non-GitHub evidence sources (notes/links and the existing resume), and embed only changed chunks. Re-running with no changes performs zero embedding calls.

### Plan-of-record drift (flagged)

Plan §1/§2 says resume evidence comes from "profile bullets **and** extracted-text lines". Evidence is candidate-scoped but `structured_profile` is per-profile, so this issue ingests **bullets and entries from a chosen profile's `structured_profile`** (`experience`, `projects`), keyed by content hash so the same bullet appearing in two profiles dedupes automatically. `resume.extracted_text` is not ingested: its bullets are already the extracted structure, and re-segmenting raw text would add noise without evidence value.

## Locked decisions

| Decision | Choice | Rationale |
|---|---|---|
| Chunk kinds | `pr`, `commit_cluster`, `repo_summary`, `issue`, `note`, `resume_entry` with the compositions and caps in plan §4.4 | Extraction unit = unit of meaning |
| Commit clustering | PR-less kept commits per repo, split into bursts by a ≥ 7-day gap, ≤ 30 commits per cluster | Cheap, deterministic, explainable |
| Token counting | `litellm.token_counter` for caps; fall back to `len(text)/4` if the model is unknown | No new dependency |
| Redaction | Chunk `text` is the **redacted** rendering (irreversible); original text stays on the items for the review UI | The LLM only ever sees redacted text; achievements containing placeholders are flagged for review in #52 |
| Hash | `content_hash = sha256(chunker_version + normalized redacted text)`; embeddings recomputed only when the hash changes | Cost control; matches the v4 #31 spirit |
| `contains_private` | OR over member items | Provenance (owner decision) |
| Links | Stored as `link` items (title, URL, optional pasted text); **never fetched** in v6; chunked only when text is present | Scope + privacy |
| Notes | Candidate-owned `note` items; editing a note creates a new item version (new hash) and supersedes the old one (`status='excluded'`, link kept in `meta.superseded_by`) | Audit-friendly |
| Cross-item dedupe | Exact `content_hash` equality at item and chunk level; semantic near-duplicates are **not** auto-merged here | Achievement-level merge proposals live in #53 |

## Scope

### Backend (`backend/app/`)

- `services/evidence_pipeline/chunking.py`: pure builders per chunk kind; stable ordering; `ChunkDraft(kind, project_key, title, text, item_ids, time_start, time_end, contains_private, token_count)`; overflow splitting (PR description vs. review threads; note paragraphs with 10 % overlap).
- `services/evidence_pipeline/dedupe.py`: item/chunk hash helpers; "squash commit attached to PR" resolution check (defensive second pass on top of #50).
- `services/evidence_pipeline/resume_ingest.py`: `ingest_profile(profile_id)` → one `resume_line` item per bullet (`external_id = sha256(company|title|bullet)`), one `resume_entry` chunk per experience/project entry; `project_key = "resume:<company or project>"`.
- `services/evidence_notes.py`: create/update/delete notes and links with validation (length caps, URL scheme allow-list `http/https`).
- `services/evidence_chunks.py`: `rebuild_chunks(candidate_id, scope=None)` — build drafts, diff against stored chunks by `(kind, project_key, content_hash)`, insert new / delete vanished (safe: achievements reference **items**, not chunks), embed only new ones via `embedding.embed_texts` in batches, `extracted_hash` untouched. Invoked at the end of a sync run and after note/resume ingestion.
- `routers/evidence.py`: `POST/GET/PATCH/DELETE /api/evidence/notes`, `POST /api/evidence/links`, `POST /api/evidence/resume/ingest` (`profile_id`), `GET /api/evidence/items` (filters: kind, project, status, private; paginated; filtered items opt-in), `PATCH /api/evidence/items/{id}` (restore a filtered item / exclude a kept one; writes nothing to profile tables), `GET /api/evidence/chunks/summary` (counts, tokens, private share — feeds the #52 estimate).

### OpenAPI / frontend

Regenerate types; no UI here (#53).

### Tests

- `tests/services/test_evidence_chunking.py` (pure, golden): expected chunk boundaries for the golden items (PR with 25 commits → capped at 20 deduped messages; bursts split by a 9-day gap; long README truncated at 4k chars; note paragraph overlap), cap enforcement via token counter, deterministic ordering, `contains_private` propagation.
- `tests/services/test_evidence_chunks_service.py` (Postgres, fake embedder): first run embeds N chunks; **second run with no changes → 0 embed calls**; editing one item changes exactly one chunk's hash and triggers exactly one embed; removed items delete their chunks; achievements referencing items are unaffected.
- `tests/services/test_evidence_notes.py`: CRUD, supersede-on-edit, URL validation, length caps, 404 on foreign ids.
- `tests/services/test_resume_ingest.py`: bullets become items/chunks; ingesting two profiles with the same bullet creates one item; re-ingest after a profile edit adds/supersedes correctly; `project_key` format.
- Redaction wiring test: a chunk built from an item containing a token-shaped string and an email has neither in `chunk.text` but both still in the item body.

### Standards from v5 (must hold from the first commit)

- **Lint/types:** ruff `ALL` and pyright strict pass with no new `noqa`; untyped third-party values are narrowed through small typed helpers (the pattern in `adapters/llm.py`); a `# pyright: ignore` needs a reason comment. Functions stay within the configured limits (args 6, branches 13, returns 8, complexity 14).
- **Coverage and layout:** the 90 % floor holds with `TEST_DATABASE_URL` set; new code ships with its tests in the mirrored folders (`tests/adapters/`, `tests/services/`, `tests/routers/`, `tests/db/`, `tests/core/`; recorded/golden suites in `tests/eval/`).
- **Config:** every new `Settings` field appears in `.env.example` (the settings↔env guard test fails otherwise); no `os.getenv`/`os.environ` and no provider SDK imports outside their one module.
- **API:** new routes keep `response_model` (binary downloads declare their media type instead), use only the CORS-allowed methods (`GET`, `POST`, `PATCH`, `DELETE`, `OPTIONS` — **never PUT**) and headers (`Content-Type`, `Accept`), raise `DomainError` subclasses (checked by `tests/core/test_error_contract.py`), and bound every list with the shared `pagination()` dependency and `X-Total-Count`.
- **Privacy:** no resume/evidence text, prompts, tokens or keys in logs (extend `tests/routers/test_logging_privacy.py` for the new flows); LLM calls log `cost_usd=`; outbound HTTP has an explicit timeout.

### Gates / docs

the backend gate (`ruff check . && ruff format --check . && pyright && pytest --cov=app` with a scratch `TEST_DATABASE_URL`) and `pre-commit run --all-files`; `docs/guide/04-evidence-and-resume.md` documents notes, links, resume ingestion, what "filtered" means and how to restore an item.

## Risks

| Risk | Mitigation |
|---|---|
| Chunk boundaries too coarse/fine for extraction quality | Boundaries are golden-tested and `chunker_version` is part of the hash, so tuning later re-chunks cleanly; quality is judged in #52/#60 |
| Redaction removes information the achievement needs (e.g. an email-like identifier) | Redaction counts are surfaced in the chunk summary; rare, acceptable |
| Embedding quota during a first big sync | Batching + `LLM_MAX_CONCURRENCY` + retry; embeddings of changed chunks only |

## Out of scope

Fetching link content, LinkedIn/Jira/GitLab items, LLM extraction (#52), UI (#53), ANN indexes.
