# v2 plan — JobGen product site & experience milestones

**Status:** Done (2026-09-12). Six milestone commits on `main` (see commit map below).
**Supersedes/covers:** the parts of v1 that shipped earlier — this plan records the second
major work stream: the public-facing product site, JobGen branding/SEO, guided setup, and
the jobs-experience pass (detail panel, pagination, run-banner polish).
**Depends on:** v1 issues #1–#12 (all done).

---

## Scope summary

| Area | What changed |
|---|---|
| Backend API | New `GET /api/jobs/postings/{id}`; `X-Total-Count` pagination headers on `GET /api/matches` |
| Jobs UI | JobDetailPanel, X-Total-Count pagination, polished filter bar / priority slider / run banner / source multi-select |
| Profile & upload flows | Purple-theme polish across upload page, resume list, profile review/merge/gap-fill forms |
| Marketing site | New landing page (gradient canvas, AI particles, radar showcase, features, companies, how-it-works), get-started chooser |
| Navigation | `AppNav` replaced by `SiteHeader`: transparent when unscrolled, Back button on inner pages, logo → home |
| Setup | Guided step checklist with direct provider signup links + live re-check |
| Brand/SEO | Renamed to **JobGen**, per-page titles via template, OpenGraph/Twitter metadata, keyword-rich description |

## Milestone 1 — job posting detail API and match count headers

- `GET /api/jobs/postings/{posting_id}` → `JobPostingDetail` (description, `job_type`,
  `remote_type`, `fetched_at` on top of summary fields); 404 via new
  `JobPostingNotFoundError` domain error.
- `GET /api/matches` now sets `X-Total-Count` (and
  `Access-Control-Expose-Headers`) via a `count_matches` service function so the
  dashboard can paginate without loading all matches.
- `uv.lock` committed — backend dependency resolution is reproducible via `uv`.

**Verification:** `ruff check .` + `ruff format --check` + `pytest` (118 passed; DB-bound
tests skip without scratch Postgres).
**Doc impact:** none ( OpenAPI regenerated frontend types — see M2).

## Milestone 2 — jobs experience: detail panel, pagination, run banner polish

- `lib/api/schema.d.ts` regenerated from FastAPI OpenAPI (no hand-written response types).
- `JobDetailPanel` feature component: source badges (Official API / Third-party scraper
  always visible), salary/location detail, keep-or-hide per standard.
- `MatchList` wires `X-Total-Count` into its pagination state.
- Filter bar, `PrioritySlider`, `RunBanner`, `SourceMultiSelect`, `SearchQueriesCard`,
  `SearchResults`, `SearchForm` restyled on the theme; jobs page shell updated.

**Verification:** `npm run lint` + `npm run build` pass.
**Doc impact:** none beyond type regeneration.

## Milestone 3 — profile review & upload flow polish

- Upload page shell + `ResumeUploadForm`, `ResumeList`, `ProfilesSection` re-themed
  (gradient CTA pills, violet-tinted cards, error/empty states kept).
- Profile review editor, merge mode, gap-fill chat restyled — no logic changes to the
  revision audit trail or review-save flow.

**Verification:** `npm run lint` + `npm run build` pass.

## Milestone 4 — JobGen marketing site, unified nav and SEO metadata

- `AppNav` deleted; new `SiteHeader` (site-wide): logo always returns home,
  transparent until 8 px scroll (then white/blur pill), "Get Started" only on `/`,
  and a Back button (`router.back()`) on all inner pages.
- Landing page (`/`): light violet→fuchsia gradient canvas + dot-grid, fixed AI
  particle layer (15 drifting dots + twinkles, CSS-only, `prefers-reduced-motion` safe),
  hero with AI-search radar showcase (`AiSearchShowcase`), features grid, companies
  marquee, 4-step how-it-works with animated flow arrows.
- `Get-started` chooser reordered: Create profile → Manage profiles → Job openings
  (most popular) → ATS Score → Resume builder → API keys; every card previews its own
  flow.
- Rebrand to **JobGen** (header, footer, copyright) and SEO metadata in `layout.tsx`:
  default title + `%s | JobGen` template, OG/Twitter, keywords, applicationName.
  Per-page titles normalized.

**Verification:** `npm run lint` + `npm run build` pass.

## Milestone 5 — guided setup with provider key links and theme parity

- `SetupChecklist` replaces `KeyStatusCards`: numbered steps (Gemini, Adzuna, Apify)
  with live Configured/Missing badges from `/api/setup/check`, a Re-check status button,
  and for every missing key a direct provider signup link plus the exact env vars to
  paste into `backend/.env`.
- SourceList keeps the LinkedIn scraper disclosure acknowledgement and gains theme parity.
- Profile page shell restyled on the same theme.

**Verification:** `npm run lint` + `npm run build` pass.

## Commit map

| Commit | Milestone |
|---|---|
| `15223b9` | M1 — job posting detail API and match count headers |
| `b172695` | M2 — jobs experience: detail panel, pagination, run banner polish |
| `93840cc` | M3 — profile review & upload flow polish |
| `0cd1b4c` + `846ddd7` | M4 — JobGen marketing site, unified nav and SEO metadata |
| `71f8541` | M5 — guided setup with provider key links and theme parity |

## Known follow-ups (v2 backlog candidates)

1. Profile page runtime error reported on `/profile?profile=<id>` (Next dev overlay,
   `ProfileEditor`) — reproducible only with live data; needs the full overlay message to
   diagnose.
2. GitHub milestones for this plan to be created/linked in the repo (open-source).
3. Backend service-to-service docs for the new endpoints (`docs/guide/`).
