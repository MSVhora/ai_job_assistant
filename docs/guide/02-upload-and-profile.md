# 2 — Upload & Profile Review

**Status: mostly shipped** — resume upload + text extraction
([issue #2](../plans/v1-issue-002-resume-upload.md)), LLM extraction to a reviewable draft
([issue #3](../plans/v1-issue-003-llm-extraction.md)), and the review/edit UI with the
`profile_revision` audit trail ([issue #4](../plans/v1-issue-004-profile-persistence-review-ui.md))
are live; conversational gap-fill (#5) follows. This guide describes the finished v1 pipeline.

## The idea

You never hand-type a profile. You upload a resume, the AI turns it into a structured draft,
and **you** approve every field before it is saved. Every change — AI or human — is recorded
in an audit trail.

## The flow, end to end

<!-- diagram: profile-pipeline-flow -->
```mermaid
flowchart TD
    A["Upload resume (PDF or DOCX)"] --> B{"Valid type and size?"}
    B -- "no" --> B1["Clear error: 413 / 415"]
    B1 --> A
    B -- "yes" --> C["Save file with UUID name, extract text"]
    C --> D{"Readable text found?"}
    D -- "no" --> D1["Error 422: scanned/image PDFs not supported"]
    D1 --> A
    D -- "yes" --> E["AI drafts a structured profile<br/>(re-runnable draft,<br/>not a saved profile yet)"]
    E --> F["Review and edit every field<br/>AI-extracted fields highlighted"]
    F --> G{"Important fields missing?"}
    G -- "yes" --> H["Gap-fill chat asks only about<br/>the missing fields"]
    H --> F
    G -- "no" --> I["Save profile"]
    F -.-> J[("Every change recorded<br/>in profile_revision")]
    I -.-> J
```

![profile-pipeline-flow diagram](../assets/profile-pipeline-flow.svg)

## What happens on upload (behind the scenes)

<!-- diagram: upload-sequence -->
```mermaid
sequenceDiagram
    actor U as User
    participant B as Browser
    participant R as POST /api/resume
    participant S as Resume service
    participant X as Text extraction<br/>(pdfplumber / python-docx)
    participant E as POST /api/resume/{id}/extract
    participant L as Gemini via LiteLLM
    participant D as Postgres

    U->>B: select PDF / DOCX file
    B->>R: upload file (multipart)
    R->>S: handle upload
    S->>S: check size, type, magic bytes
    S->>D: get-or-create candidate
    S->>S: save file as uploads/uuid.pdf
    S->>X: extract text (off the event loop)
    X-->>S: extracted text + page count
    alt no extractable text
        S-->>B: 422 with clear message
    else text found
        S->>D: store resume metadata + text
        S-->>B: draft extracted text
    end
    B->>E: extract structured profile
    E->>L: resume text + JSON schema (prompt-instructed)
    L-->>E: profile JSON (pydantic-validated,<br/>one repair round-trip if invalid)
    E->>D: stamp parse_version, persist draft_profile on the resume row
    E-->>B: draft profile — still not a saved profile
```

![upload-sequence diagram](../assets/upload-sequence.svg)

Key guarantees baked into the design:

- **Type checking is real** — the server sniffs file magic bytes; renaming an `.exe` to
  `.pdf` gets rejected (415)
- **The file on disk is never named after your file** — it gets a UUID; your original
  filename is stored as metadata only
- **A "draft" is not a profile** — the AI draft (`draft_profile`) lives on the resume row as
  a re-runnable parse artifact; nothing becomes your profile until you review and save it
- **Extraction failures never corrupt anything** — the model output is validated against a
  strict schema (with one automatic repair round-trip); a failed extraction leaves the
  resume row exactly as it was

## Step-by-step (once the pipeline is live)

1. **Upload** — pick a standard single-column PDF or DOCX (up to 10 MB). Multi-column or
   image-only resumes parse poorly or fail with a clear message. The AI draft is generated
   right after upload; if it misses something, extraction can simply be re-run.
2. **Review the draft** *(live)* — the AI-extracted profile opens as an editable form with
   AI-extracted fields highlighted. Fix anything wrong; saving records your corrections in
   the `profile_revision` audit trail.
3. **Fill the gaps** *(#5, upcoming)* — the app asks conversational questions *only* about
   genuinely missing fields (typically: target location, salary band, seniority, work
   authorization, remote preference). Answers merge into the profile, also recorded as
   revisions.
4. **Done** — the saved profile drives job discovery and matching. Re-uploading a newer
   resume opens a merge/diff review; nothing is overwritten until you explicitly save the
   merge.

## How saving works (the API behind the UI)

- `GET /api/profile` returns the saved profile — `404` until the first save, which the UI
  shows as an empty state pointing back to upload
- `PATCH /api/profile` is an upsert: the first save writes the reviewed draft; every later
  save replaces the whole profile and writes one `profile_revision` row with a field-level
  diff (`{path: {old, new}}`, dotted paths for scalars, whole-list diffs for arrays)
- The revision `source` is decided by the server, never the client:
  - `ai_extraction` — the first save from a reviewed draft (the AI baseline; when you
    corrected fields during first review, an additional `manual_edit` row records exactly
    what you changed)
  - `manual_edit` — a normal edit save
  - `reupload_merge` — a save after the re-upload merge review
  - `gap_fill` — reserved for the conversational gap-fill flow (#5)
- `GET /api/resume/{id}/draft` returns the AI draft for a resume without re-running
  extraction (no token cost) — this is what makes the review UI refresh-safe
- No-change saves still record a revision row with an empty diff — the audit trail shows
  every save attempt, not only the ones that changed something

## Privacy

- Resume content is stored only in your local Docker volumes and Postgres
- The only party that ever sees resume text (besides you) is the LLM provider **you**
  configured with **your** key

## Next

[Job discovery & matching →](03-job-discovery-and-matching.md)
