# Issue #3 — LLM Structured Extraction (Resume Text → Profile JSON)

**Status:** Done (2026-08-31)
**Tracks:** GitHub issue #3 (Day 2–3, Week 1)
**Plan of record:** [v1-implementation-plan.md](v1-implementation-plan.md) §4, §6, §8
**Depends on:** Issue #2 (resume upload + text extraction — done)

---

## Goal

`POST /api/resume/{resume_id}/extract` runs schema-constrained extraction over the stored
`extracted_text` via Gemini Flash and returns a **draft** `StructuredProfile`. The draft is
persisted as `resume.draft_profile` (a parse artifact); `candidate.structured_profile` is
untouched until issue #4 saves reviewed data. Re-running the endpoint re-extracts and overwrites.

**Acceptance (from the issue):** >95% section bucketing on standard resumes; unreviewed data
never auto-saved.

## Locked decisions

Decided during planning (deviations from plan §6 are additive and accepted):

| Decision | Choice | Rationale |
|---|---|---|
| Endpoint shape | Separate `POST /api/resume/{id}/extract`, not folded into upload | Upload stays fast and robust; extraction is retryable independently. Plan §6's sketch had the draft on `POST /api/resume` — issue #2 already split the flow, so this completes that split |
| Draft persistence | `resume.draft_profile` (jsonb, nullable) written on success | Refresh-safe review UI in issue #4; no token cost to recover a lost draft. It's a parse artifact, not the profile — nothing touches `candidate` |
| Preferences block | Optional `preferences` extracted **only when stated on the resume** | Plan §4 includes prefs in `structured_profile`; gap-fill (#5) asks only about what extraction couldn't find |
| Structured output | Prompt-instructed JSON (schema in system prompt) + tolerant extraction + pydantic validation; **one repair round-trip** on validation failure | Amended during build: Gemini 2.5 Flash via LiteLLM `response_format` loops/truncates on large responseSchema payloads (observed live 2026-08-31 — repetition + dropped fields + multi-minute hangs); the backend standard's real requirement (pydantic-validated, repair-once) is met either way |
| `parse_version` semantics | Overwritten on successful extraction to `<model>+<prompt_version>` (e.g. `gemini-2.5-flash+profile_prompt_v2`); `parsed_at` moves with it | Follows issue #2's locked decision: the columns track the **latest** transform of the row (upload time remains visible via `created_at`); the prompt version bumps whenever extraction rules change |
| Extraction mode | Synchronous request (single LLM call) | Plan reserves `BackgroundTasks` for ingestion/batch work; one call fits the <30s acceptance |

## Scope

### Pydantic schema (`schemas/profile.py`)

`StructuredProfile` (the contract issue #4 persists into `candidate.structured_profile`):

```
contact:      full_name, email, phone, location, links[] {label, url}
headline:     str | None
summary:      str | None
skills:       list[str]
experience:   [{company, title, location?, start_date?, end_date?, is_current, bullets[]}]
projects:     [{name, role?, url?, start_date?, end_date?, description?, bullets[], technologies[]}]
education:    [{institution, degree?, field?, start_date?, end_date?}]
certifications: [{name, issuer?, issued_date?}]
awards:        [{title, issuer?, issued_date?}]
extra_sections: [{title, entries[]}]   -- Publications, Languages, Volunteer, ... (catch-all)
preferences:  {target_title?, target_location?, remote_preference?, salary_min?, salary_max?, currency?} | None
```

- Amended after first live runs: `projects` + `extra_sections` catch-all added so no resume
  section is ever dropped (user feedback); unlabeled links get deterministic labels from the
  URL domain in the service (`LinkedIn`, `GitHub`, ... fallback `Website`) — never trusted
  to the model alone

- Dates stay **verbatim strings** as written on the resume ("Mar 2021", "2019 – Present") —
  no date parsing/coercion in v1; normalization happens at matching time if needed
- Everything optional except `contact.full_name` and one of skills/experience — empty
  resumes must fail validation, not produce an all-null draft
- Prompt rules: extract only what is present, null for missing, never invent; skills
  lightly normalized (dedupe, trim)

### Adapter — `parse_structured` in `adapters/llm.py`

- `async def parse_structured[T: BaseModel](prompt, *, schema: type[T], system=None) -> StructuredResult`
  where `StructuredResult = {data: T, prompt_tokens, completion_tokens}`
- Sends the JSON schema in the system prompt and requests a single JSON object (no
  provider `response_format` — see the locked-decision amendment); robust extractor
  strips fences/prose and validates against the pydantic schema
- On pydantic `ValidationError` (or unparseable JSON): **one** repair call that includes the
  prior output's validation errors; second failure → `LLMError`
- Logs model + duration + token counts, same pattern as `generate` — never prompt or content

### Service — `services/profile_extraction.py`

- `PROFILE_PROMPT_VERSION = "profile_prompt_v1"` constant
- Resume text truncated to `extraction_max_chars` (default 20 000) before prompting
- `extract_resume_profile(session, resume_id) -> DraftProfileResponse`:
  1. load resume → 404 if missing; `extracted_text` empty/None → 409
  2. `is_llm_configured()` false → 503 before any call (plan §10: warn before failure time)
  3. run `parse_structured`, log operation + duration + tokens
  4. stamp `resume.parse_version = f"{settings.llm_model}+{PROFILE_PROMPT_VERSION}"`,
     `resume.parsed_at = now()`, persist `resume.draft_profile`
  5. return the response — **no candidate writes anywhere** (acceptance)

### Migration `0003_add_resume_draft_profile`

- `resume.draft_profile jsonb null`
- Models first, autogenerate, hand-review; downgrade drops the column (drafts are
  reproducible by re-running extraction — data loss acceptable, noted in docstring)

### Errors (`core/errors.py`, existing central handler)

- `ResumeTextUnavailableError` → 409 (resource exists, wrong state)
- `LLMNotConfiguredError` → 503
- `LLMExtractionError` → 502 (wraps adapter `LLMError` after repair fails)

### Router + response schema

- `routers/resume.py`: `POST /api/resume/{resume_id}/extract`, `response_model=DraftProfileResponse`
  (`{resume_id, candidate_id, draft_profile, parse_version, parsed_at}`), 200 even on
  re-extract (upsert semantics)
- Reuses the existing resume router/tags; no new router

### Config (`core/config.py` + `.env.example`)

- `extraction_max_chars: int = 20_000` → `EXTRACTION_MAX_CHARS`
- No new keys — LLM settings already exist from the scaffold

### Tests (`tests/`)

- `test_profile_schema.py` — schema validation: full profile, minimal valid, all-null
  rejected, junk dates tolerated as strings
- `test_llm_parse_structured.py` — mocked `litellm.acompletion`: valid JSON passes;
  malformed → repair round-trip succeeds; repair also fails → `LLMError`; token counts logged
- `test_profile_extraction.py` (DB-backed via `clean_tables`) — upload fixture PDF → extract
  with mocked adapter: 200 + `draft_profile` persisted + `parse_version`/`parsed_at`
  restamped; candidate row unchanged (acceptance); unknown id → 404; resume without text → 409;
  unconfigured key → 503; always-invalid LLM → 502
- Section-bucketing acceptance: deterministic fixture resume with known sections — golden
  assertions that entries land in experience/education/skills/certifications buckets
  (statistical >95% verified manually on real resumes; CI asserts the fixture)

## Doc impact

- `docs/guide/` (upload/profile flow): document the extract endpoint and that drafts are
  re-runnable, not auto-saved
- `docs/architecture.md`: extraction service appears in the backend flow; re-render affected
  diagram via `node scripts/render-diagrams.mjs`
- `.env.example`: `EXTRACTION_MAX_CHARS`
- No frontend changes; openapi types regenerate in issue #4 when the frontend consumes the draft

## Definition of done

- `ruff check . && ruff format --check . && pytest` green in `backend/`
- Migration generated, reviewed, and included in the same change
- Acceptance met: fixture bucketing assertions pass; no candidate/profile persistence anywhere
- `.env.example` + docs updated, diagrams re-rendered

## Out of scope (later issues)

Profile persistence + review UI + revision audit (#4), conversational gap-fill (#5),
embeddings/matching (#6+).
