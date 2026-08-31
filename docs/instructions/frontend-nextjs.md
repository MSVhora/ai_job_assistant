# Next.js Frontend Standards

Applies to everything under `frontend/`.

## Structure

```
frontend/
  app/                 # App Router: layouts, pages, route handlers
  components/
    ui/                # generic presentational (button, card, input, badge)
    features/          # domain components (ProfileForm, MatchCard, SourceDisclosureModal)
  lib/
    api/               # single typed API client — the ONLY place that fetches the backend
    api/schema.d.ts    # generated from FastAPI OpenAPI (openapi-typescript)
  hooks/               # reusable client hooks
  types/               # shared app types (prefer generated over hand-written)
```

## Rules

- **TypeScript strict.** No `any`; use `unknown` + narrowing. No non-null `!` assertions on API data.
- **Server Components by default.** Add `"use client"` only where interactivity/state/effects are needed, and push it to the smallest leaf component possible.
- **API access**: all backend calls go through `lib/api` client functions with generated types. No raw `fetch`/`axios` inside components. Regenerate types from the backend's `openapi.json` after any backend schema change — never hand-write API response types.
- **Secrets**: never reference backend keys in frontend code. `NEXT_PUBLIC_*` only for genuinely public values; prefer proxying through Next route handlers instead.
- **Forms**: react-hook-form + zod. Validate on submit (and blur for long forms). Backend validation is the source of truth — a passing client never skips server checks. Every field gets a label and an error message slot.
- **Async UI**: every loading state (skeleton/spinner), error state (with retry), and empty state is implemented. No silent failures, no unhandled promise rejections.
- **Server state**: TanStack Query (or SWR) for fetch caching/invalidation. Global client state only when genuinely cross-cutting; no Redux unless the app demands it.
- **Styling**: Tailwind utility classes only — no inline style objects, no CSS-in-JS. Shared patterns become `components/ui/` primitives, not copy-pasted class strings.
- **Background work UX**: ingestion/scoring runs are async — poll status, show progress, allow navigation away without breaking the run.
- **Scraping sources**: source badges ("Official API" / "Third-party scraper") always visible on cards and settings; the disclosure modal must be acknowledged before a scraping source can be enabled.
- **Accessibility**: semantic HTML, labeled inputs, keyboard-navigable modals (focus trap + escape), visible focus rings, `aria-live` for async status changes.
- **Components**: under ~200 lines; extract subcomponents/features when larger. No comments except non-obvious decisions.

## Commands & gates

- `npm run lint` and `npm run build` must pass before any task is "done".
- ESLint: `next/core-web-vitals` + strict TS rules; Prettier for formatting.
- Prefer App Router idioms: `app/` conventions, route handlers for proxying, `next/image` for images, metadata exports for titles.
