# Issue #56 — Typst rendering and the deterministic priority-first page fit (Week 3)

**Status:** Implemented (2026-10-04) — see *Implementation notes* for deviations (revised 2026-10-03 against the shipped #55 code; earlier revision 2026-10-02: targets 1–4 pages, priority-first, no fill thresholds, PDF only on explicit request)
**Tracks:** GitHub issue #56 (milestone `v6`, branch `v6/56-resume-typst-render-fit`)
**Plan of record:** [v6-implementation-plan.md](v6-implementation-plan.md) §3.4, §6.3, ADR-3
**Depends on:** #54 (schema), #55 (ranked pool, written bullets, and the content-only stub layout this issue replaces)
**Blocks:** #57 (review view needs `layout`; preview/download need `/render`)

---

## Goal

Decide **what is included** for the user's chosen page count (1, 2, 3 or 4) by maximizing the priority of included content, deterministically, and render an ATS-friendly PDF **only on explicit request**. Pages do not need to be full: the objective is the best-priority content for the space, never a blank resume. No LLM anywhere in this issue.

## Starting point (state after #55)

- `resume_builder.build_layout` is the content-only stub, called only from `persist()`, which is the single writer of `resume_document.layout` (generate, regenerate, include-anyway, write-on-demand, apply-comments, bullet edit, approve-anyway). The fit replaces its inclusion logic **inside `persist()`**, so no caller changes; the stub's non-fit `not_included` reasons (`needs_review`, `not_written`, `overlap_omitted`) are kept and `did_not_fit` is added.
- `PATCH /resume-documents/{id}` and `resync-identity` bypass `persist`; `POST …/fit` is the explicit re-fit for them.
- `Layout`, `NotIncluded` (already has `did_not_fit`) and the `layout`/`template`/`page_target` columns exist: **no migration**.
- Contact lives in `content.basics`, so the renderer needs only `ResumeContent`. Priority is `Bullet.score`. `template` is a free string today; validate against `{classic, compact}` (400 `InvalidResumeDocumentError`) at fit time.
- Eligible bullets: `check == "passed"` or `approved_anyway`; `needs_review`/`failed` → `not_included` (`needs_review`).
- `Settings` has no fit setting yet: add `resume_fit_max_compiles` (+ `.env.example`). `CannotFitError(DomainError)` is 422; extra body keys need a handler branch and an `allowed_extra` entry in `tests/core/test_error_contract.py`.
- The existing `GET …/export` route is the precedent for a non-`response_model` route (`response_class=Response`).

## Spike first (≈ 1 hour, recorded in this file before coding)

1. `uv add typst` (scratch branch) and build the backend image (`python:3.12-slim`, arm64 and amd64): no system libs, compiles a sample with bundled fonts.
2. Decide how data reaches the template as data: `sys_inputs` is string-only (one JSON string + `json.decode` in Typst) vs. a temp `data.json` under a temp root.
3. Compile a sample, count pages with `pdfplumber`, extract text, check reading order and headings.
4. Confirm font licences (OFL, e.g. Source Sans 3 / Libertinus); pin the compiler version.
5. Note whether the pinned Typst version emits tagged PDF. If any check fails, switch to the fallback (WeasyPrint behind `PageMeter`) **before** writing the fit and report back.

## Spike results (2026-10-03)

Run in a scratch venv (Python 3.12) and in `python:3.12-slim` (aarch64) with `typst` 0.15.0 and `pdfplumber`; nothing in the repo was changed.

| Check | Result |
|---|---|
| Wheel on `python:3.12-slim` | Installs and compiles with no system packages (aarch64 tested). PyPI ships abi3 manylinux wheels for x86_64 and aarch64 (≈ 35 MB), so amd64 should work too but was **not** run here. |
| Data as data | `sys_inputs={"data": json.dumps(...)}` with `json(bytes(sys.inputs.data))` in the template works. Names/bullets containing `# * $ @` backtick `\` quotes and `#raw("x")` rendered literally in the extracted text; nothing executed. **Decision: one JSON string via `sys_inputs`, no temp files.** |
| Page counting | `pdfplumber` counts pages correctly (1 page for a short sample, 3 for 60 × 40-word bullets). |
| Determinism | Two compiles of the same input are byte-identical. |
| Fonts | The compiler embeds Libertinus Serif, New Computer Modern and DejaVu Sans Mono (all OFL); with `ignore_system_fonts=True` the PDF used only Libertinus Serif. **Proposed change: use the embedded Libertinus Serif and ship no font files** (nothing to license or copy; still independent of host fonts). Revisit only if the owner wants a sans face. |
| Tagged PDF | The output contains `/StructTreeRoot` and `/MarkInfo`. Extraction order and heading detection on the real template are still asserted in `test_resume_ats.py`. |
| Speed | A reused `typst.Compiler` measured < 1 ms per compile on a trivial document (comemo caching); a real resume will be slower, so the `RESUME_FIT_MAX_COMPILES` bound stays. Re-measure on the real template. |
| Fallback | Not needed; WeasyPrint stays only as the documented fallback. |

Still to do before merge: pin the exact version in `pyproject.toml`/`uv.lock`, `pip-audit`, and one amd64 image build.

## Locked decisions

| Decision | Choice | Rationale |
|---|---|---|
| Renderer | `typst` PyPI package, version **pinned exactly** | ADR-3 |
| Fonts | The compiler's embedded Libertinus Serif with `ignore_system_fonts=True` (spike); never host fonts | Determinism, no font files to ship |
| Templates | One Typst source, two variants (`classic`, `compact`) via parameters | Plan §2.1 |
| Targets | `page_target ∈ {1,2,3,4}`; `RESUME_MAX_PAGES` (default 4) caps it | Owner decision: user chooses length |
| Objective | Maximize total priority of included bullets subject to `pages ≤ page_target`; **no fill thresholds** | Owner: priority is the crux, not fullness |
| Measurement | `PageMeter(content, layout) → pages` (compile → `pdfplumber` page count) | Existing dependency; renderer-agnostic seam |
| Two entry points | `POST …/fit` → layout only (in-memory compile, **no PDF returned**); `POST …/render` → PDF (re-runs the fit first) | Review-before-PDF flow (#57) |
| Persistence | PDFs not stored; `layout` stored on the document | No stale files |
| Loop bound | `RESUME_FIT_MAX_COMPILES` (default 30) | Worst case here ≈ 21 |
| Unfittable | `CannotFitError` listing items to review; never an extra page or sub-floor type | Hard requirement 3 |

### Fit algorithm (plan §6.3, precise)

Inputs: `page_target`, template, the priority-ordered list of **written, passing** bullets (`needs_review` excluded) grouped by kept roles/projects, the role anchors, pinned bullets, `omitted_roles` from #55.

1. **Ordering key:** pinned bullets first; then **role anchors** (each role's highest-scoring bullet, boosted so every included role appears before any role's second bullet); then remaining bullets by priority. Roles are ordered chronologically in the output regardless of inclusion order.
2. **Per typography preset** — P0 comfortable (10.5 pt, 0.7 in, normal spacing), P1 (10 pt, 0.6 in), P2 floor (9.5 pt, 0.5 in, tight spacing): binary-search the largest prefix of the ordering that compiles with `pages ≤ page_target` (≈ 6–7 compiles per preset).
3. **Choose the preset** whose included set has the highest total priority; ties → the roomier preset. This lets a tight preset win only when it keeps meaningfully more high-priority content.
4. If even the anchors do not fit at P2, drop whole roles from the lowest-priority end (they become `not_included` with reason `did_not_fit`). If nothing fits → `CannotFitError`.
5. **Output `layout`:** `{pages, preset, font_pt, margin_in, included_ids, not_included: [{id, priority, reason: did_not_fit | needs_review | overlap_omitted | not_written}], steps, short_on_evidence}`. `short_on_evidence` is true when every available bullet is already included and pages < target (informational — never padded).
6. Determinism: same inputs + same pinned compiler + bundled fonts ⇒ identical `layout`.

### ATS rules enforced by the template and asserted in tests

Single column; standard headings (Experience, Education, Skills, Projects); real text only (no images, tables, text boxes); contact in the body (not header/footer); plain bullet glyph; consistent date format; visible link text.

## Scope

### Backend (`backend/app/`)

- `resources/typst/resume.typ` (+ per-variant parameters).
- `services/resume_render/{typst_template.py,page_meter.py,fit.py}`: content → Typst data (passed to the template as **data**, never concatenated into markup), compile, measure, fit search, `RenderResult(pdf_bytes | None, layout)`.
- `services/resume_builder.py` integration point: `fit_document(document)` called after generation, after edits/add/remove, and before render.
- `routers/resume_documents.py`: `POST /api/resume-documents/{id}/fit`, `POST …/render` (binary download: declares `response_class=Response` and `responses={200: {"content": {"application/pdf": {}}}}`; update `backend-fastapi.md`, whose `response_model` exceptions currently list only redirect/204 routes; `application/pdf`, 422 `CannotFit` with details), `GET …/layout`. Contact info comes from `content.basics`; nothing private-marked is rendered into the file.
- Resources are `Path(__file__)`-relative like `resources/skill_aliases.yaml` (the Dockerfile copies `app/`). Compiles run in `asyncio.to_thread`.
- `pyproject.toml`: add `typst==<pinned>` to runtime `dependencies`, `uv lock`, rebuild the image (it installs with `uv sync --frozen --no-dev`), `pip-audit` clean. Pyright strict: wrap the compiler in one small typed function (`compile_pdf`) and narrow its return values there — no scattered ignores.
- `core/config.py`: `resume_fit_max_compiles`.

### Tests (no LLM, no network)

- `tests/services/test_resume_fit.py`: 30+ synthetic documents (varying role/bullet counts, long lines, unicode names, empty sections) × targets {1,2,3,4}: `pages ≤ target` always; included set equals the maximal-priority prefix for the chosen preset (verified against a brute-force reference on small inputs); role anchors included before second bullets; pinned bullets never dropped before unpinned; `needs_review` bullets never included; roles dropped whole only when anchors cannot fit; `CannotFitError` for an impossible 1-page document; a sparse document returns `short_on_evidence=True` without padding.
- `tests/services/test_resume_determinism.py`: same input twice → identical `layout`, `steps` and extracted text.
- `tests/services/test_resume_ats.py`: `pdfplumber` extraction — headings in order, bullets are text lines, no empty-glyph boxes, contact exactly once, no table objects, single column (x-position clustering).
- `tests/services/test_page_meter.py`: fixtures with known page counts; escape-safety (names/bullets containing `#`, `*`, `$`, `@`, backticks, `\`, quotes render literally and never execute Typst code).
- Router tests: `/fit` returns layout and **no PDF bytes**; `/render` returns a valid PDF (`%PDF`, page count ≤ target); 404 on foreign document; 422 shape on `CannotFit`.

### Standards from v5 (must hold from the first commit)

- **Lint/types:** ruff `ALL` and pyright strict pass with no new `noqa`; untyped third-party values are narrowed through small typed helpers (the pattern in `adapters/llm.py`); a `# pyright: ignore` needs a reason comment. Functions stay within the configured limits (args 6, branches 13, returns 8, complexity 14).
- **Coverage and layout:** the 90 % floor holds with `TEST_DATABASE_URL` set; new code ships with its tests in the mirrored folders (`tests/adapters/`, `tests/services/`, `tests/routers/`, `tests/db/`, `tests/core/`; recorded/golden suites in `tests/eval/`).
- **Config:** every new `Settings` field appears in `.env.example` (the settings↔env guard test fails otherwise); no `os.getenv`/`os.environ` and no provider SDK imports outside their one module.
- **API:** new routes keep `response_model` (binary downloads declare their media type instead), use only the CORS-allowed methods (`GET`, `POST`, `PATCH`, `DELETE`, `OPTIONS` — **never PUT**) and headers (`Content-Type`, `Accept`), raise `DomainError` subclasses (checked by `tests/core/test_error_contract.py`), and bound every list with the shared `pagination()` dependency and `X-Total-Count`.
- **Privacy:** no resume/evidence text, prompts, tokens or keys in logs (extend `tests/routers/test_logging_privacy.py` for the new flows); LLM calls log `cost_usd=`; outbound HTTP has an explicit timeout.

### Gates / docs

regenerate `backend/openapi.json` and `frontend/lib/api/schema.d.ts` (`npm run generate:api`) and run the frontend gate; update `docs/architecture.md` (~line 257 stub wording, ~706 ER note) and re-run `node scripts/render-diagrams.mjs`; the backend gate (`ruff check . && ruff format --check . && pyright && pytest --cov=app` with a scratch `TEST_DATABASE_URL`) and `pre-commit run --all-files`; README (font licences, pinned `typst`, rebuild note); `architecture.md` (fit/render in the resume sequence); guide 04 "Choosing a length", "What gets included", "ATS".

## Risks

| Risk | Mitigation |
|---|---|
| Typst version bump changes pagination | Exact pin; determinism test |
| Template injection through user/evidence text | Content passed as data; dedicated escape tests |
| Compile latency in the review loop (fit now runs inside `persist`, so also on bullet edit/approve) | ~100 ms typical, ≤ ~21 compiles; if slow in #57, add a `fit=false` fast path then |
| Prefix-by-priority is greedy and may skip a short high-value bullet after a long one | Acceptable for MVP; brute-force reference test bounds the gap; a knapsack variant is a v7 idea |

## Out of scope

More templates, DOCX/HTML export, stored PDFs, custom fonts, cover letters, multi-column layouts.

## Implementation notes — deviations from the plan above

- **Fonts:** the compiler's embedded Libertinus Serif with `ignore_system_fonts=True`; no `resources/fonts/` directory and no font files (owner confirmed serif is fine).
- **Data passing:** one JSON string in `sys_inputs`, decoded by the template with `json(bytes(sys.inputs.data))`; no temp files.
- **Eligibility:** `check == "passed"` only. Approving a flagged bullet already sets `check = "passed"`, and `failed` is never set by code, so it is treated like `needs_review`.
- **Dropping roles (plan step 4) is implicit:** anchors come first in the ordering, so the longest fitting prefix at the floor preset drops the lowest-priority roles whole. `CannotFitError` is raised when the fixed sections (contact, education, skills) overflow, or when not even one bullet fits at the floor preset. When the roomiest preset already fits everything the search stops after one compile.
- **Template validation:** `ResumeDocumentCreate`/`Update.template` is now `Literal["classic", "compact"]` (422 at the edge); the fit still guards with a 400 `InvalidResumeDocumentError` for older rows.
- **Generating never loses content to a failed fit:** `persist` catches `CannotFitError`, stores an empty layout (all candidates `did_not_fit`) and adds a `generation.warnings` entry. The explicit `POST …/fit` and `…/render` re-raise it as 422.
- **`CannotFitError` has no extra body keys** (the explanation is in `detail`), so `test_error_contract.py` needed no change. `ResumeRenderError` (500) wraps compiler failures and never logs compiler text.
- **`short_on_evidence`** is true when pages < target and nothing is left to add: no `did_not_fit`, `needs_review` or `not_written` entries.
- **Order in the document:** included roles keep the document's own order (the profile's reverse-chronological order), not a re-sort.
- **Routes:** `POST …/fit`, `GET …/layout` and `POST …/render` (`Content-Disposition` filename built from an ASCII slug of the name). `render` runs the fit again, persists it, then renders exactly the fitted layout.
- **Not done here:** an amd64 image build (the wheel exists for manylinux x86_64 but was only exercised on aarch64).
- **Verification:** backend gate green against the scratch database (1241 tests, 93.4 % coverage; ruff, format and pyright clean), `pre-commit run --all-files` clean, `pip-audit` clean, frontend lint/format/typecheck/test/build pass after regenerating `lib/api/schema.d.ts`, ER diagram re-rendered.
