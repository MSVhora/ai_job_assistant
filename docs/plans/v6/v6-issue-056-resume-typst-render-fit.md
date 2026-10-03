# Issue #56 — Typst rendering and the deterministic priority-first page fit (Week 3)

**Status:** Proposed — for owner review (revised 2026-10-02: targets 1–4 pages, priority-first, no fill thresholds, PDF only on explicit request)
**Tracks:** GitHub issue #56 (milestone `v6`, branch `v6/48-resume-typst-render-fit`)
**Plan of record:** [v6-implementation-plan.md](v6-implementation-plan.md) §3.4, §6.3, ADR-3
**Depends on:** #54 (schema), #55 (ranked pool and written bullets)
**Blocks:** #57 (review view needs `layout`; preview/download need `/render`)

---

## Goal

Decide **what is included** for the user's chosen page count (1, 2, 3 or 4) by maximizing the priority of included content, deterministically, and render an ATS-friendly PDF **only on explicit request**. Pages do not need to be full: the objective is the best-priority content for the space, never a blank resume. No LLM anywhere in this issue.

## Spike first (≈ 1 hour, recorded in this file before coding)

1. `pip install typst` inside the backend image (`python:3.12-slim`, arm64 and amd64): no system libs, compiles a sample with bundled fonts.
2. Compile a sample, count pages with `pdfplumber`, extract text, check reading order and headings.
3. Confirm font licences (OFL, e.g. Source Sans 3 / Libertinus); pin the compiler version.
4. Note whether the pinned Typst version emits tagged PDF. If any check fails, switch to the fallback (WeasyPrint behind `PageMeter`) **before** writing the fit and report back.

## Locked decisions

| Decision | Choice | Rationale |
|---|---|---|
| Renderer | `typst` PyPI package, version **pinned exactly** | ADR-3 |
| Fonts | Bundled in `backend/app/resources/fonts/`, passed explicitly; never host fonts | Determinism |
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

- `resources/typst/resume.typ` (+ per-variant parameters), `resources/fonts/*`.
- `services/resume_render/{typst_template.py,page_meter.py,fit.py}`: content → Typst data (passed to the template as **data**, never concatenated into markup), compile, measure, fit search, `RenderResult(pdf_bytes | None, layout)`.
- `services/resume_builder.py` integration point: `fit_document(document)` called after generation, after edits/add/remove, and before render.
- `routers/resume_documents.py`: `POST /api/resume-documents/{id}/fit`, `POST …/render` (`application/pdf`, 422 `CannotFit` with details), `GET …/layout`. Contact info is injected from the profile at compile time; nothing private-marked is rendered into the file.
- `pyproject.toml`: add `typst==<pinned>`; README note about rebuilding the image after a dependency change.
- `core/config.py`: `resume_fit_max_compiles`.

### Tests (no LLM, no network)

- `test_resume_fit.py`: 30+ synthetic documents (varying role/bullet counts, long lines, unicode names, empty sections) × targets {1,2,3,4}: `pages ≤ target` always; included set equals the maximal-priority prefix for the chosen preset (verified against a brute-force reference on small inputs); role anchors included before second bullets; pinned bullets never dropped before unpinned; `needs_review` bullets never included; roles dropped whole only when anchors cannot fit; `CannotFitError` for an impossible 1-page document; a sparse document returns `short_on_evidence=True` without padding.
- `test_resume_determinism.py`: same input twice → identical `layout`, `steps` and extracted text.
- `test_resume_ats.py`: `pdfplumber` extraction — headings in order, bullets are text lines, no empty-glyph boxes, contact exactly once, no table objects, single column (x-position clustering).
- `test_page_meter.py`: fixtures with known page counts; escape-safety (names/bullets containing `#`, `*`, `$`, `@`, backticks, `\`, quotes render literally and never execute Typst code).
- Router tests: `/fit` returns layout and **no PDF bytes**; `/render` returns a valid PDF (`%PDF`, page count ≤ target); 404 on foreign document; 422 shape on `CannotFit`.

### Gates / docs

`ruff` + `pytest`; README (font licences, pinned `typst`, rebuild note); `architecture.md` (fit/render in the resume sequence); guide 04 "Choosing a length", "What gets included", "ATS".

## Risks

| Risk | Mitigation |
|---|---|
| Typst version bump changes pagination | Exact pin; determinism test |
| Template injection through user/evidence text | Content passed as data; dedicated escape tests |
| Compile latency in the review loop | ~100 ms typical; fit runs on explicit actions (generate, add/remove, apply comments), not per keystroke |
| Prefix-by-priority is greedy and may skip a short high-value bullet after a long one | Acceptable for MVP; brute-force reference test bounds the gap; a knapsack variant is a v7 idea |

## Out of scope

More templates, DOCX/HTML export, stored PDFs, custom fonts, cover letters, multi-column layouts.
