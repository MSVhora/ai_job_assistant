# Issue #47 — LLM cost estimation before batch operations

**Status:** Proposed — for owner review
**Tracks:** GitHub issue #47 (milestone `v5`, branch `v5/47-llm-cost-estimation`)
**Plan of record:** [v5 plan](v5-hardening-plan.md) · standards: [llm-ai.md](../../instructions/llm-ai.md), [backend-fastapi.md](../../instructions/backend-fastapi.md) (*v5 #47* rules)
**Depends on:** #41 · **Blocks:** v6 #49 (extends this instead of building an estimator)

## Goal

The standard says batch or user-triggered LLM actions show an estimated cost before running. Today the adapter returns and logs token counts only; the tune-my-queries confirm panel (`SearchQueriesCard.tsx`) warns in prose ("roughly a few thousand tokens — your API key pays") without a number. Add `estimate_cost` to `adapters/llm.py`, log cost with every call, and show real estimates in the confirm-gated actions.

## Evidence

- `adapters/llm.py`: `generate` returns `GenerationResult(text, prompt_tokens, completion_tokens)`, `embed` returns `EmbeddingResult`, `parse_structured` returns `StructuredResult`; all log tokens and duration; nothing computes cost.
- Confirm-gated user actions: **Tune my queries** (`POST /api/profiles/{id}/tune-queries`, one `parse_structured` call). Background batch work: re-rank during search runs (reports token usage in the run's `matching` outcome), profile/posting embeddings, and `backend/scripts/backfill_embeddings.py`.

## Locked decisions

| Decision | Choice | Rationale |
|---|---|---|
| Price source | `litellm.cost_per_token` (LiteLLM's built-in price map) by default; optional overrides `LLM_PRICE_IN_PER_MTOK` / `LLM_PRICE_OUT_PER_MTOK` / `EMBEDDING_PRICE_PER_MTOK` in `Settings` for models the map does not know | No hand-maintained prices in code; the user can correct them |
| Unknown price | Report `cost: null` and the message "cost unavailable for this model" — never guess a number | Honest estimates |
| API | `CostEstimate(prompt_tokens, completion_tokens, usd | None, basis)` and `estimate_cost(model, prompt_tokens, completion_tokens)`; `estimate_tokens(text/messages)` via `litellm.token_counter` (fallback chars/4 flagged as approximate) | One place for the math |
| Logging | Every `llm.*` log line gains `cost_usd=` (or `cost_usd=unknown`) | Standard: log tokens and cost |
| Tune-my-queries | New `POST /api/profiles/{id}/tune-queries/estimate` builds the same prompt without calling the model and returns a `CostEstimate`; the existing confirm dialog shows "≈ N tokens, ≈ $X" before the user confirms | Confirm-gated with a real number |
| Re-rank and embeddings in runs | The run's `matching` outcome and run banner show the **actual** tokens and cost after the run (already tracks tokens) | Visibility without adding a gate to automatic work |
| Backfill script | Prints an estimate and requires `--yes` (or an interactive confirm) before calling the provider | Batch operation |
| Scope limit | No spending caps/budgets in this plan | Out of scope; see v5 for usage meter |

## Scope

- `core/config.py`: price override settings (`float | None`), validated; `.env.example` entries.
- `adapters/llm.py`: `CostEstimate`, `estimate_tokens`, `estimate_cost`; cost in log lines; unit tests for unknown models.
- `services/query_tuner.py`: split prompt building from the call so the estimate endpoint reuses it; `routers/profile.py` + `schemas` for the estimate response.
- `services/matching.py` / run outcome schema: add `cost_usd` next to token usage; frontend run banner shows it when known.
- `backend/scripts/backfill_embeddings.py`: estimate + confirmation.
- Frontend: `SearchQueriesCard` confirm dialog calls the estimate endpoint and renders the number; regenerate `lib/api/schema.d.ts`.

## Tests

- `estimate_cost` for a model in LiteLLM's map (stable fixture values) and for an unknown model (`None` + message); override settings take precedence.
- Estimate endpoint returns without any provider call (fake asserts zero calls); estimate within ±25 % of the actual tokens on the fixture profile.
- Log lines include cost fields (caplog); run outcome carries `cost_usd`.
- Frontend: dialog renders the estimate, shows the unavailable message when `usd` is null (component test).
- Backfill script requires confirmation (test with `--yes` and without).

## Gates

Backend and frontend gates from #41/#44; `npm run generate:api` leaves no diff after regeneration.

## Doc impact

`docs/guide/02-upload-and-profile.md` / `03-job-discovery-and-matching.md` (Tune my queries shows the estimate; run banner shows actual cost); `docs/architecture.md` LLM-adapter paragraph; `.env.example` (price overrides); `docs/instructions/{llm-ai,backend-fastapi}.md` (remove *(v5 #47)* markers).

## Risks

| Risk | Mitigation |
|---|---|
| Provider price map is stale or missing | Overrides + honest "unavailable"; estimate is labelled approximate |
| Estimate drifts from reality (hidden thinking tokens, repair calls) | Tolerance test; show "up to" wording for structured calls that may repair once |

## Out of scope

Usage meters across runs, budgets/caps, cost dashboards (v6 #49 extends this plan's primitives).
