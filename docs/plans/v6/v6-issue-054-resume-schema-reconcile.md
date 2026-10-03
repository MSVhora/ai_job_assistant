# Issue #54 — Canonical resume schema, JSON Resume mapping, reconciliation engine (Week 3)

**Status:** Proposed — for owner review
**Tracks:** GitHub issue #54 (milestone `v6`, branch `v6/46-resume-schema-reconcile`)
**Plan of record:** [v6-implementation-plan.md](v6-implementation-plan.md) §6.1, §6.2 step 2, §9 (migration `0026`)
**Depends on:** #52/#53 (approved achievements with `employer_ref`)
**Blocks:** #55, #56, #57

---

## Goal

Define the one document shape the builder, renderer and editor share, map it losslessly to and from `structured_profile`, and implement the **reconciliation engine** that surfaces conflicts between evidence and the profile instead of overriding either side (hard requirement 5). No LLM calls and no rendering in this issue.

## Locked decisions

| Decision | Choice | Rationale |
|---|---|---|
| Schema | `ResumeContent` pydantic: JSON Resume-compatible sections (`basics`, `work`, `education`, `skills`, `projects`, `awards`, `certificates`) where highlights are `Bullet` objects (plan §6.1 incl. `from_private`) | Provenance per bullet; JSON Resume export by flattening |
| Identity anchor | `basics`, `education`, employer names/titles/dates are copied from the chosen profile's `structured_profile` at document creation and re-synced on request; never taken from evidence or the LLM | Hard req. 5 |
| Profile bullets | Existing profile bullets can be carried verbatim as `origin='profile_verbatim'` (no `achievement_id`) so a user can keep their own wording | Don't force everything through generation |
| No profile normalization | `structured_profile` is not changed; the v1 "per-bullet table" idea is satisfied inside `resume_document.content` | Zero changes to existing tables |
| Conflicts | Deterministic detectors producing `Conflict(key, kind, severity, message, refs, suggested_actions)`; resolution is explicit: edit profile (existing PATCH → `profile_revision`) or "keep as is" recorded on the document | Surface, never override |
| Document ownership | `candidate_id` + `profile_id` (cascade) + optional `match_id` (set null); `page_target` CHECK BETWEEN 1 AND 4 (owner: the user chooses 1, 2, 3 or 4 pages); `comments` JSONB for section/bullet comments (#55) | Output is per track |
| Revisions | `resume_document_revision` snapshots (last 20), written on every content save | Reviewability; first cut-line item if time slips |

### Conflict detectors (all pure functions over profile + achievements + GitHub identity)

1. `date_outside_employment` — achievement dated outside the mapped employer's window.
2. `employer_not_in_profile` — scope mapped to a company absent from the profile.
3. `identity_mismatch` — GitHub name/location vs `contact` (never email: contact info is not sent to or read from the LLM; the GitHub profile email, when public, is compared locally).
4. `skill_missing_in_profile` — evidence-backed skills the profile lacks (suggest add).
5. `skill_without_evidence` — profile skills with zero evidence (informational; kept).
6. `metric_contradiction` — profile bullet number conflicts with a confirmed metric for the same project.
7. `overlapping_roles` — two employment roles overlapping by ≥ `RESUME_OVERLAP_MIN_DAYS` (informational; resolved by the priority rule in #55, which keeps the higher-priority role and lists the other as omitted).

## Scope

### Migration (`0026_add_resume_document.py`)

`resume_document` and `resume_document_revision` as in plan §9; enum `resume_document_status`; CHECK constraint `page_target BETWEEN 1 AND 4`; `comments` JSONB (default `[]`); `jd_weight real` (CHECK 0 ≤ x ≤ 0.5, default 0); FKs indexed. No existing table touched.

### Backend (`backend/app/`)

- `models/resume_document.py`; `schemas/resume_document.py` (`ResumeContent`, `Bullet`, `Layout`, `Conflict`, create/update/response schemas).
- `services/resume_mapping.py`: `profile_to_content(profile)`, `content_to_structured_profile(content)` (only for the sections the builder may write back — none are written back automatically; used for round-trip testing and the editor's "apply to profile" action, which goes through the normal profile PATCH), `to_json_resume(content)`.
- `services/resume_reconcile.py`: detectors above + `reconcile(profile, achievements, github_identity) -> list[Conflict]`; stable `key` hashes so resolutions persist across re-runs.
- `services/resume_documents.py` (CRUD only here): create empty document from a profile (identity fields copied), read, list, delete, save content with revision snapshot, `resolve_conflict(key, action)`.
- `services/resume_export.py`: pure `to_plain_text(content, contact)`, `to_markdown(content, contact)`, `to_json_resume(content)`; output is **clean** (no private marks, no badges, no provenance) and is the same content the PDF is built from.
- `routers/resume_documents.py`: `GET /api/resume-documents/{id}/export?format=text|markdown|json_resume`, `POST/GET/DELETE /api/resume-documents`, `GET/PATCH /api/resume-documents/{id}`, `GET …/conflicts`, `POST …/conflicts/{key}/resolve`; ownership by candidate and profile → 404 otherwise.

### Tests

- `tests/services/test_resume_mapping.py`: `profile → content → profile` round trip loses nothing for the fixture profiles (incl. extra sections, awards, current roles, missing dates); JSON Resume export validates against the JSON Resume field names; profile-verbatim bullets keep `origin`.
- `tests/services/test_resume_reconcile.py` on `tests/eval/golden/profile.json` (deliberate conflicts): all seven kinds detected, each exactly once (incl. an overlapping-roles pair), no false positives on a clean profile; resolutions keyed stably across re-runs; "keep as is" suppresses without editing the profile; the profile row is **never** modified by reconciliation (asserted).
- `tests/services/test_resume_documents.py`: CRUD, `page_target` constraint (0 and 5 → 422/IntegrityError mapped; 1–4 accepted), revision snapshot cap at 20, cascade on profile delete, ownership 404s.
- `tests/services/test_resume_export.py`: plain text and Markdown contain every included bullet exactly once, contact comes from the profile, **no** private marker or provenance text appears in any format, JSON Resume validates; output is stable across two calls.
- `tests/db/test_migrations.py` (+ `tests/db/test_schema_standards.py` picks the new tables up): `0026` round trip (incl. `page_target` CHECK rejecting 0 and 5, `comments` default).

### Standards from v5 (must hold from the first commit)

- **Lint/types:** ruff `ALL` and pyright strict pass with no new `noqa`; untyped third-party values are narrowed through small typed helpers (the pattern in `adapters/llm.py`); a `# pyright: ignore` needs a reason comment. Functions stay within the configured limits (args 6, branches 13, returns 8, complexity 14).
- **Coverage and layout:** the 90 % floor holds with `TEST_DATABASE_URL` set; new code ships with its tests in the mirrored folders (`tests/adapters/`, `tests/services/`, `tests/routers/`, `tests/db/`, `tests/core/`; recorded/golden suites in `tests/eval/`).
- **Config:** every new `Settings` field appears in `.env.example` (the settings↔env guard test fails otherwise); no `os.getenv`/`os.environ` and no provider SDK imports outside their one module.
- **API:** new routes keep `response_model` (binary downloads declare their media type instead), use only the CORS-allowed methods (`GET`, `POST`, `PATCH`, `DELETE`, `OPTIONS` — **never PUT**) and headers (`Content-Type`, `Accept`), raise `DomainError` subclasses (checked by `tests/core/test_error_contract.py`), and bound every list with the shared `pagination()` dependency and `X-Total-Count`.
- **Privacy:** no resume/evidence text, prompts, tokens or keys in logs (extend `tests/routers/test_logging_privacy.py` for the new flows); LLM calls log `cost_usd=`; outbound HTTP has an explicit timeout.
- **Schema (v5 #43 conventions):** every table with `updated_at` gets `create_updated_at_trigger(table)` / `drop_updated_at_trigger(table)` from `app.core.migration_helpers`; every FK is indexed and declares its ON DELETE (CASCADE owned children, RESTRICT identity/audit, SET NULL provenance); constraints and indexes are named (`uq_`/`ix_`/`fk_`/`ck_`); bounded scalars get a `CHECK`; `alembic check` is clean and the schema audit (`tests/db/test_schema_standards.py`) reports nothing; downgrade works. Revision numbers continue from `0022`.

### Gates / docs

the backend gate (`ruff check . && ruff format --check . && pyright && pytest --cov=app` with a scratch `TEST_DATABASE_URL`) and `pre-commit run --all-files`; `architecture.md` ER (resume_document tables); guide 04 "Reconciliation" section.

## Risks

| Risk | Mitigation |
|---|---|
| Verbatim date strings in the profile make window checks fuzzy | Reuse the deterministic parsing already used for `years_of_experience` (#32); unparsable dates yield no conflict rather than a false one |
| Conflict noise annoys the user | Severity levels; informational kinds collapsed by default |
| Mapping drift if `StructuredProfile` gains fields later | Round-trip test over a schema-introspected fixture so new fields fail loudly |

## Out of scope

LLM generation (#55), rendering (#56), UI (#57), writing resolved conflicts back to the profile automatically.
