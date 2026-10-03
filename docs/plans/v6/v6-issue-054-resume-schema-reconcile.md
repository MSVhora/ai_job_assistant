# Issue #54 — Canonical resume schema, JSON Resume mapping, reconciliation engine (Week 3)

**Status:** Implemented — branch `v6/54-resume-schema-reconcile` (awaiting merge into `v6/milestone`)
**Tracks:** GitHub issue #54 (milestone `v6`, branch `v6/54-resume-schema-reconcile`, cut from `v6/milestone`)
**Plan of record:** [v6-implementation-plan.md](v6-implementation-plan.md) §6.1, §6.2 step 2, §9 (migration `0026`)
**Depends on:** #52/#53 (approved achievements with `employer_ref`)
**Blocks:** #55, #56, #57

---

## Changes from the earlier draft

Checked against the code at the end of #53:

- Branch is `v6/54-…` (was `v6/46-…`); migration is `0026` with `down_revision = "0025"` (the head is `0025_add_achievements`; the old "continue from `0022`" line was stale).
- The migration creates **every** `resume_document` column in plan §9 now (`template`, `job_description`, `jd_hash`, `layout`, `conflicts`, `status`, `version` as well as `page_target`, `jd_weight`, `comments`), so #55/#56 need no ALTER.
- GitHub name/location are **not stored or read today** (`GitHubSource.identify()` keeps only login, node_id and email); see decision D1.
- `tests/eval/golden/profile.json` and the `resume_overlap_min_days` setting do not exist yet; this issue creates them.
- Date parsing reuses `profile_derivation.resolve_date` and `employer_mapping.load_profile_facts`; no new parser.
- There is no capped-revision pattern in the repo (`profile_revision`, `achievement_revision` are append-only), so the keep-last-20 prune is new.

## Goal

Define the one document shape the builder, renderer and editor share, map it losslessly to and from `structured_profile`, and implement the **reconciliation engine** that surfaces conflicts between evidence and the profile instead of overriding either side (hard requirement 5). No LLM calls and no rendering in this issue.

## Locked decisions

| Decision | Choice | Rationale |
|---|---|---|
| Schema | `ResumeContent` pydantic: JSON Resume-compatible sections (`basics`, `work`, `education`, `skills`, `projects`, `awards`, `certificates`) where highlights are `Bullet` objects (plan §6.1 incl. `from_private`) | Provenance per bullet; JSON Resume export by flattening |
| Mapping gaps | `headline` → `basics.label`, `summary` → `basics.summary`; `extra_sections` pass through; `preferences` and `years_of_experience` (server-managed) are excluded from the round trip; dates stay verbatim strings | Lossless round trip; the profile has no typed dates |
| Identity anchor | `basics`, `education`, employer names/titles/dates are copied from the chosen profile's `structured_profile` at document creation and re-synced on request; never taken from evidence or the LLM | Hard req. 5 |
| Profile bullets | Existing profile bullets can be carried verbatim as `origin='profile_verbatim'` (no `achievement_id`) | Don't force everything through generation |
| No profile normalization | `structured_profile` is not changed; the v1 "per-bullet table" idea is satisfied inside `resume_document.content` | Zero changes to existing tables |
| Conflicts | Deterministic detectors producing `Conflict(key, kind, severity, message, refs, suggested_actions)`; resolution is explicit: edit the profile (existing PATCH → `profile_revision`) or "keep as is" recorded on the document (`resume_document.conflicts`) | Surface, never override |
| Conflict key | Stable hash of `(kind, sorted refs)` so resolutions persist across re-runs | Re-run safety |
| Employer join | `employer_ref` joins to `ExperienceItem` on `(company, start_date raw string)`. Refs with `source: "suggested"` are unconfirmed and ignored by `employer_not_in_profile`; `user`/`scope` refs are checked; `{kind: "personal"}` is exempt | Matches `services/employer_mapping.py` |
| Dates | Profile dates through `resolve_date`; achievements use `time_start`/`time_end` (`date`); unparsable ⇒ no conflict, never a false one | Fuzzy verbatim strings |
| Document ownership | `candidate_id` (RESTRICT) + `profile_id` (CASCADE) + optional `match_id` (SET NULL); every route checks the document's candidate and its profile's candidate, 404 otherwise (pattern: `owned_achievement`) | Single-user today, ownership-ready |
| Revisions | `resume_document_revision` snapshots written on every content save; the oldest beyond 20 are pruned in the same transaction | Reviewability; first cut-line item if time slips |

### D1 — GitHub identity for `identity_mismatch` (decided: on-demand fetch, nothing persisted)

Name/location come only from GitHub's `/user` call, and the codebase discards them. **Decision:** extend `SourceIdentity` and `identify()` to carry `name` and `location`; `reconcile()` takes an optional `GitHubIdentity` DTO, and the conflicts endpoint fetches it on demand when a token is configured (explicit timeout, shared retry policy). No token or a failed call ⇒ detector 3 is skipped and the response says so. Nothing is persisted, so no existing table changes and no extra personal data is stored. *Alternative (rejected, owner decision):* persist name/location on `evidence_source`, which needs a migration on an existing table; revisit later as a small follow-up migration if offline reconciliation is wanted. If a `GET` that calls out proves unwelcome, move the fetch to an explicit `POST …/conflicts/refresh`.

### Conflict detectors (pure functions over profile + achievements + optional GitHub identity)

1. `date_outside_employment` — achievement dated outside the mapped employer's window.
2. `employer_not_in_profile` — confirmed scope/user mapping to a company absent from the profile.
3. `identity_mismatch` — GitHub name/location vs `contact` (never email: contact info is not sent to or read from the LLM; the GitHub public email, when present, is compared locally).
4. `skill_missing_in_profile` — evidence-backed skills the profile lacks (suggest add).
5. `skill_without_evidence` — profile skills with zero evidence (informational; kept).
6. `metric_contradiction` — profile bullet number conflicts with a confirmed metric for the same project/employer. Only metrics with `verified in ("evidence","user")` count (never `needs_confirmation`); numbers are extracted from the metric `text` and compared on the same unit/percent token, conservatively.
7. `overlapping_roles` — two employment roles overlapping by ≥ `resume_overlap_min_days` (informational; resolved by the priority rule in #55, which keeps the higher-priority role and lists the other as omitted).

## Scope

### Migration (`0026_add_resume_document.py`, `down_revision = "0025"`)

Modelled on `0025_add_achievements.py` (local `_uuid_pk/_jsonb/_created/_updated` helpers, `op.f(...)` names).

- `resume_document`: `id`, `candidate_id` (FK RESTRICT), `profile_id` (FK CASCADE), `match_id` (FK SET NULL, nullable), `title`, `page_target smallint`, `jd_weight real`, `template`, `job_description`, `jd_hash`, `content`, `layout`, `conflicts`, `comments` (JSONB, default `[]`), `status` (enum `resume_document_status`: draft, final), `version`, `created_at`, `updated_at`. CHECK `page_target BETWEEN 1 AND 4`; CHECK `jd_weight BETWEEN 0 AND 0.5` (default 0). Every FK indexed. `create_updated_at_trigger("resume_document")`.
- `resume_document_revision`: `id`, `document_id` (FK CASCADE, indexed), `version`, `content`, `source`, `created_at` (no `updated_at`, so no trigger).
- Downgrade: drop the trigger, then children before parents, then `DROP TYPE IF EXISTS resume_document_status`. No existing table is touched.

### Backend (`backend/app/`)

- `models/resume_document.py` (registered in `models/__init__.py`); `schemas/resume_document.py` (`ResumeContent`, `Bullet`, `Layout`, `Conflict`, create/update/response). Do not collide with the uploaded-file `models/resume.py`, `routers/resume.py`, `schemas/resume.py`.
- `services/resume_mapping.py`: `profile_to_content(profile)`, `content_to_structured_profile(content)` (only for the sections the builder may write back — none are written back automatically; used for round-trip testing and the editor's "apply to profile" action, which goes through the normal profile PATCH), `to_json_resume(content)`.
- `services/resume_reconcile.py`: detectors above plus `reconcile(profile, achievements, github_identity) -> list[Conflict]`; reuses `resolve_date` and `load_profile_facts`.
- `services/resume_documents.py` (CRUD only): create an empty document from a profile (identity fields copied), read, list, delete, save content with revision snapshot and prune to 20, `resolve_conflict(key, action)`. Services use `flush`, never `commit`.
- `services/resume_export.py`: pure `to_plain_text`, `to_markdown`, `to_json_resume`; output is **clean** (no private marks, no badges, no provenance) and is the same content the PDF is built from.
- `routers/resume_documents.py` (registered in `main.py` after `achievements.router`): `POST/GET/DELETE /api/resume-documents` (list uses `pagination()` and `X-Total-Count`), `GET/PATCH /api/resume-documents/{id}`, `GET …/conflicts`, `POST …/conflicts/{key}/resolve`, `GET …/export?format=text|markdown|json_resume` (declares its media types instead of a `response_model`). No PUT.
- `core/errors.py`: `ResumeDocumentNotFoundError` (404), `ConflictNotFoundError` (404), `InvalidResumeDocumentError` (400).
- `adapters/evidence_sources/base.py` + `github.py`: `SourceIdentity` gains `name`/`location`; `identify()` fills them (D1).
- `core/config.py` + root `.env.example`: `resume_overlap_min_days: Annotated[int, Field(ge=1, le=366)] = 60`.

### Tests

- `tests/eval/golden/profile.json` (validated with `StructuredProfile.model_validate`): one deliberate instance of each of the seven kinds, an overlapping-roles pair, extra sections, awards, a current role and missing dates. Add `name` and `location` to `tests/eval/golden/github/user.json`.
- `tests/services/test_resume_mapping.py`: `profile → content → profile` loses nothing for the fixture profiles; a schema-introspection test fails when `StructuredProfile` gains a field the mapping neither carries nor explicitly excludes; JSON Resume export validates against the JSON Resume field names; profile-verbatim bullets keep `origin`.
- `tests/services/test_resume_reconcile.py` on the golden profile: all seven kinds detected, each exactly once; no false positives on a clean profile; suggested employer refs and `needs_confirmation` metrics ignored; unparsable dates yield nothing; no GitHub identity ⇒ detector 3 skipped; resolutions keyed stably across re-runs; "keep as is" suppresses without editing the profile; the profile row is **never** modified (asserted).
- `tests/services/test_resume_documents.py`: CRUD, `page_target` and `jd_weight` bounds (0/5 and 0.6 rejected; 1–4 accepted), revision snapshot prune at 20, cascade on profile delete, ownership 404s.
- `tests/services/test_resume_export.py`: plain text and Markdown contain every included bullet exactly once, contact comes from the profile, **no** private marker or provenance text in any format, JSON Resume validates, output stable across two calls.
- `tests/routers/test_resume_documents.py`: status codes, `X-Total-Count`, export media types, error contract; extend `tests/routers/test_logging_privacy.py`; adapter test for `identify()` returning name/location.
- **DB test touch-ups required by the new table:** in `tests/db/test_schema_standards.py` bump the head `_updated_at_triggers()` count from 11 to 12 (three places; leave the older-state counts 5 and 9) and add a `0026` round-trip test modelled on `test_achievements_migration_round_trip` (downgrade to `0025`; CHECKs reject `page_target` 0/5 and `jd_weight` 0.6; `comments` default `[]`); add `"resume_document"` to `TABLES_WITH_UPDATED_AT` in `tests/db/test_updated_at_trigger.py`; `alembic check` and the schema audit stay clean.

### Standards from v5 (must hold from the first commit)

- **Lint/types:** ruff `ALL` and pyright strict pass with no new `noqa`; untyped third-party values are narrowed through small typed helpers (the pattern in `adapters/llm.py`); a `# pyright: ignore` needs a reason comment. Functions stay within the configured limits (args 6, branches 13, returns 8, complexity 14).
- **Coverage and layout:** the 90 % floor holds with `TEST_DATABASE_URL` set; new code ships with its tests in the mirrored folders (`tests/adapters/`, `tests/services/`, `tests/routers/`, `tests/db/`, `tests/core/`; recorded/golden suites in `tests/eval/`).
- **Config:** every new `Settings` field appears in `.env.example` (`tests/core/test_env_example.py` fails otherwise); no `os.getenv`/`os.environ` and no provider SDK imports outside their one module.
- **API:** new routes keep `response_model` (binary/text downloads declare their media type), use only the CORS-allowed methods (`GET`, `POST`, `PATCH`, `DELETE`, `OPTIONS` — **never PUT**) and headers (`Content-Type`, `Accept`), raise `DomainError` subclasses (checked by `tests/core/test_error_contract.py`), and bound every list with the shared `pagination()` dependency and `X-Total-Count`.
- **Privacy:** no resume/evidence text, prompts, tokens or keys in logs; outbound HTTP (the on-demand GitHub identity call) has an explicit timeout.
- **Schema (v5 #43 conventions):** `create_updated_at_trigger`/`drop_updated_at_trigger` for every table with `updated_at`; every FK indexed with an explicit ON DELETE; named `uq_`/`ix_`/`fk_`/`ck_` constraints; bounded scalars get a `CHECK`; `alembic check` clean; downgrade works. Revision numbers continue from `0025`.

### Gates / docs

Backend gate (`ruff check . && ruff format --check . && pyright && pytest --cov=app` with a scratch `TEST_DATABASE_URL`) and `pre-commit run --all-files`. Docs: `docs/architecture.md` ER block (append `resume_document`, `resume_document_revision`, their `candidate`/`profile`/`match` relations and the enum after `llm_output_cache`) then `node scripts/render-diagrams.mjs`; a "Reconciliation" section in `docs/guide/04-evidence-and-resume.md` before "Not yet verified against live GitHub".

## Risks

| Risk | Mitigation |
|---|---|
| Verbatim date strings in the profile make window checks fuzzy | `resolve_date`; unparsable dates yield no conflict rather than a false one |
| Conflict noise annoys the user | Severity levels; informational kinds collapsed by default; suggested employer refs ignored |
| `metric_contradiction` false positives | Only confirmed metrics; compare same unit/percent token; one golden positive and clean-profile negatives |
| Mapping drift if `StructuredProfile` gains fields later | Schema-introspection test fails loudly |
| GitHub identity fetch fails or no token | Detector 3 skipped with an explicit note; never blocks the conflicts response |

## Out of scope

LLM generation (#55), rendering (#56), UI (#57), writing resolved conflicts back to the profile automatically, persisting GitHub identity.

## Implementation notes — deviations from the plan above

- **Conflicts endpoint shape:** `GET …/conflicts` returns `{open, resolved, github_checked, note}` rather than a bare list, so the UI can show kept-as-is items, and whether the GitHub identity check ran. `POST …/conflicts/{key}/resolve` takes `action: "keep_as_is" | "reopen"`; `resume_document.conflicts` stores only the resolutions (`key`, `action`, `resolved_at`), and the conflicts themselves are always recomputed. An unknown key is a 404.
- **Extra endpoint:** `POST /api/resume-documents/{id}/resync-identity` implements the "re-synced on request" decision: it re-copies `basics` (keeping the document's own summary), `education` and, for work entries matched on `(company, start_date)`, title, location, end date and current flag; bullets are untouched. It is the only addition beyond the planned route list.
- **Identity mismatch** emits one conflict per differing field (`name`, `location`, `email`, key refs `{field}`); comparison is by shared word tokens, and the email is compared only when GitHub exposes one. `SourceIdentity` gained `name` and `location` and `GitHubSource.identify()` fills them (D1).
- **Skill detectors** only run when the candidate has at least one approved achievement, so an empty evidence base does not flag every profile skill.
- **Date check** compares at month granularity and treats a year-only end date as 31 December, so month- and year-level profile dates cannot produce false conflicts; unparsable or missing dates yield nothing. `experiences_of(profile)` was extracted from `load_profile_facts` in `employer_mapping.py` (behaviour unchanged) so the detectors and the mapping share one window computation.
- **`metric_contradiction`** requires a shared topic (at least two non-stopword words) and the same unit (`%`, `x`, time and size units); it checks employer-scoped bullets via the confirmed `employer_ref`, or project bullets via the repository name in `project_key`.
- **Golden profile:** `tests/eval/golden/profile.json` carries one instance of each kind (plus an undated role, extra sections, awards, certifications and preferences); the achievements that trigger the other detectors are built in the tests, not in the fixture. `golden/github/user.json` gained `name` and `location`.
- **Revisions:** `version` increments only when the saved content differs, creation writes version 1 (`source="create"`), and the newest 20 are kept in the same transaction.
- **`template`** defaults to `classic`; `jd_weight`, `job_description`, `jd_hash`, `layout` and `comments` exist but are written by #55/#56.
- **Frontend:** only `lib/api/schema.d.ts` was regenerated (from the running backend; the response models are now typed for #57).
- **Verification:** backend gate green against a scratch database (1030 tests, 92.7 % coverage; ruff, format and pyright clean), `pre-commit run --all-files` clean, `alembic check` and the schema audit clean, frontend typecheck and format check pass. The GitHub identity call was tested through fakes and a `MockTransport` only, not against live GitHub.
