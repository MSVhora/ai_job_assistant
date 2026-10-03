# Next.js Frontend Standards

Applies to everything under `frontend/`.

> **Target state.** Rules marked *(v5 #45)* are brought into the code by the
> [v5 plans](../plans/v5/v5-hardening-plan.md). This repo runs Next.js 16: before writing
> framework code, read the relevant guide in `node_modules/next/dist/docs/` (see `frontend/AGENTS.md`).

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
```

Shared app types live next to the code that owns them; prefer generated API types over hand-written ones. Create a `types/` folder only when a type genuinely has no owner.

## Rules

- **TypeScript strict.** No `any`; use `unknown` + narrowing. No non-null `!` assertions on API data. `tsconfig` also enables `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`, `noImplicitOverride`, `noUnusedLocals`, `noUnusedParameters`, `noFallthroughCasesInSwitch`. Queries that need a nullable id use TanStack Query's `skipToken` instead of `!`; optional props that receive `undefined` are declared `?: T | undefined`; payloads omit empty keys instead of setting them `undefined`.
- **Server Components by default.** Add `"use client"` only where interactivity/state/effects are needed, and push it to the smallest leaf component possible.
- **API access**: all backend calls go through `lib/api` client functions with generated types. No raw `fetch`/`axios` inside components. Regenerate types with `npm run generate:api` after any backend schema change — never hand-write API response types.
- **Secrets and env**: never reference backend keys in frontend code. `NEXT_PUBLIC_*` only for genuinely public values (`NEXT_PUBLIC_API_BASE_URL`); prefer proxying through Next route handlers instead.
- **Forms**: react-hook-form + zod. Validate on submit (and blur for long forms). Backend validation is the source of truth — a passing client never skips server checks. Every field gets a label and an error message slot.
- **Async UI**: every loading state (skeleton/spinner), error state (with retry), and empty state is implemented. No silent failures, no unhandled promise rejections. Route segments provide `loading.tsx`, `error.tsx` and `not-found.tsx` where a segment fetches data.
- **Server state**: TanStack Query for fetch caching/invalidation. Global client state only when genuinely cross-cutting; no Redux unless the app demands it.
- **Styling**: Tailwind utility classes only — no inline style objects, no CSS-in-JS. Shared patterns become `components/ui/` primitives, not copy-pasted class strings.
- **Background work UX**: ingestion/scoring runs are async — poll status, show progress, allow navigation away without breaking the run.
- **Scraping sources**: source badges ("Official API" / "Third-party scraper") always visible on cards and settings; the disclosure modal must be acknowledged before a scraping source can be enabled.
- **Accessibility**: semantic HTML, labeled inputs, keyboard-navigable modals (focus trap + escape), visible focus rings, `aria-live` for async status changes.
- **Components**: under ~200 lines (ESLint `max-lines` warns above 200 lines in `app/` and `components/`; #45 splits the existing exceptions and flips it to an error); extract subcomponents/hooks when larger. No comments except non-obvious decisions.
- Prefer App Router idioms: `app/` conventions, route handlers for proxying, `next/image` for images, metadata exports for titles.

## Tooling (target gates)

- **Formatting**: Prettier (`printWidth` 100) with `prettier-plugin-tailwindcss`; `npm run format` writes, `npm run format:check` is a gate. Prettier covers the frontend only — Python is formatted by `ruff format`.
- **ESLint**: `next/core-web-vitals` + `typescript-eslint` `strictTypeChecked` and `stylisticTypeChecked`, `jsx-a11y` strict rules, `testing-library`/`vitest` rules for tests and `eslint-config-prettier`. Deliberate tunings live in `eslint.config.mjs` with their reasons (numbers allowed in template literals; `||` on strings stays; unchecked response casts in `lib/api/client.ts`). `lib/api/schema.d.ts` is generated and ignored.
- **Dependencies**: `npm audit` clean (or each waiver documented); lockfile committed.
- **Hooks**: the root `.pre-commit-config.yaml` runs Prettier and ESLint on `frontend/`.
- Gate command (in `frontend/`): `npm run lint && npm run format:check && npm run typecheck && npm test && npm run build`.

## Testing

- Vitest + Testing Library; test files are co-located (`Component.test.tsx`, `thing.test.ts`).
- Components are tested through user-visible behaviour (roles, labels, text), not implementation details; network access goes through `lib/api`, which tests mock.
- Zod schemas and pure helpers (`lib/*.ts`, `search-form-schema.ts`) get plain unit tests.
- Every bug fix lands with a test that fails without it. See [testing.md](testing.md).
