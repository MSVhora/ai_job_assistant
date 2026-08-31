# Issue #2 — Resume Upload + Text Extraction (PDF/DOCX)

**Status:** Planned (not started)
**Tracks:** GitHub issue #2 (Day 1–2, Week 1)
**Plan of record:** [v1-implementation-plan.md](v1-implementation-plan.md) §4, §6, §8
**Depends on:** Issue #1 (scaffold — done)

---

## Goal

`POST /api/resume` accepts a PDF or DOCX, stores the file + metadata, extracts raw text, and
returns it as a **draft**. No profile is persisted here — issue #3 consumes the text for LLM
extraction, issue #4 persists the reviewed profile.

**Acceptance (from the issue):** a standard single-column resume extracts cleanly; invalid
type/size → 4xx with a clear message.

## Locked decisions

Decided during planning (small additive deviations from plan §4, accepted):

| Decision | Choice | Rationale |
|---|---|---|
| `resume.candidate_id` FK target | Create a minimal `candidate` table **now** (id, created_at, updated_at); profile columns arrive with issue #4's migration | Avoids a dangling table; candidate row is created on first upload (single-user get-or-create) |
| Extracted text storage | Store `extracted_text` (nullable) on `resume` | Issue #3+ can re-run without re-parsing; useful later for the ATS scorer |
| `parse_version` semantics | Issue #2 stamps `text_v1` (extraction pipeline version); issue #3 stamps its LLM model + prompt version when it runs | Column tracks the latest transform of the row |

## Scope

### API — `POST /api/resume` (multipart `file`)

- Type check: extension **and** content-type **and** magic bytes (`%PDF-` for PDF,
  `PK\x03\x04` for DOCX) — never trust the client's declared type
- Size cap via `Settings` (default 10 MB) → `413`; bad type → `415`; zero extractable text
  (e.g. scanned/image PDF) → `422`
- Save to `uploads_dir` with a UUID filename; the original filename is kept as metadata only,
  never used in the path
- Response model `ResumeUploadResponse`: `{resume_id, candidate_id, original_filename,
  content_type, size_bytes, extracted_text, page_count, parsed_at, parse_version}`
  — `file_path` is internal and never returned

### Migration `0002_add_candidate_and_resume_tables`

```sql
candidate:  id uuid pk (gen_random_uuid()), created_at timestamptz default now(),
            updated_at timestamptz default now()
resume:     id uuid pk, candidate_id uuid fk → candidate.id (indexed, ondelete restrict),
            file_path text not null, original_filename text not null,
            content_type text not null, size_bytes integer not null,
            extracted_text text null, page_count integer null,
            parsed_at timestamptz null, parse_version text null,
            created_at timestamptz default now()
```

- UUIDs client-side via `default=uuid4`; `updated_at` trigger on `candidate`
- Models first (`models/candidate.py`, `models/resume.py`, exported via `models/__init__.py`),
  then autogenerate, then hand-review the generated migration

### Config (`core/config.py` + `.env.example`)

- `uploads_dir: Path = ./data/uploads` (created on first write)
- `resume_max_upload_mb: int = 10`

### Domain errors + central handlers (`core/errors.py`, registered in `main.py`)

- `UnsupportedFileTypeError` → 415
- `FileTooLargeError` → 413
- `TextExtractionError` → 422

First central exception handlers in the repo — the pattern gets reused by issues #3–#5.

### Services

- `services/text_extraction.py` — pure sync functions: `extract_pdf(path) -> tuple[str, int]`
  (text, page count), `extract_docx(path) -> str`; dispatch on the sniffed type. Magic-byte
  sniffing helper shared with validation
- `services/resume_service.py` — `upload_resume(session, file) -> ResumeUploadResponse`:
  1. validate size + type (413/415 before touching disk)
  2. get-or-create the single candidate
  3. save to `uploads_dir/<uuid>.pdf|docx` (sync save + extract run via `asyncio.to_thread`
     so the event loop never blocks)
  4. empty/whitespace-only extracted text → `TextExtractionError`
  5. insert the `resume` row, return the response

### Router + schema

- `routers/resume.py`: `POST /api/resume`, multipart `UploadFile`,
  `response_model=ResumeUploadResponse`, tags `resume`; registered in `main.py`
- `schemas/resume.py`: pydantic v2 response model

### Dependencies (justification)

| Package | Why |
|---|---|
| `pdfplumber` | PDF text extraction — named in plan §3/§8 |
| `python-docx` | DOCX text extraction — named in plan §3/§8 |
| `python-multipart` | Required by FastAPI for multipart/form-data; unavoidable addition beyond the plan's named set |

### Tests (`tests/`)

- `conftest.py` — scratch-Postgres fixture (from `TEST_DATABASE_URL`, runs
  `alembic upgrade head`, skips DB-backed tests if unreachable). First DB-backed test
  infrastructure in the repo; reused by issues #3–#5
- `test_text_extraction.py` — committed tiny fixture PDF; DOCX generated in-memory via
  python-docx; multi-page page count; garbled file with a `.pdf` extension → error
- `test_resume_upload.py` — happy path (row persisted, UUID filename, text returned);
  oversize → 413; wrong type/magic → 415; empty text → 422

### Infra touch-ups

- docker-compose `api` service: named volume for `/app/data/uploads`
- `.env.example`: `UPLOADS_DIR`, `RESUME_MAX_UPLOAD_MB`

## Definition of done

- `ruff check . && ruff format --check . && pytest` green in `backend/`
- Migration generated, reviewed, and included in the same change
- Acceptance from the issue met: clean single-column extract; clear 4xx messages
- No frontend changes in this issue

## Out of scope (later issues)

LLM structured extraction (#3), profile persistence + review UI + revision audit (#4),
conversational gap-fill (#5).
