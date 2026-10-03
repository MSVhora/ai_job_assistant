# Issue #49 — LLM task routing, usage meter, output cache, redaction (Week 1)

**Status:** Proposed — for owner review
**Tracks:** GitHub issue #49 (milestone `v6`, branch `v6/41-llm-task-routing-cache-redaction`)
**Plan of record:** [v6-implementation-plan.md](v6-implementation-plan.md) §8, §12 (redaction), migration `0024`
**Depends on:** #48 (settings conventions); otherwise independent of GitHub work
**Blocks:** #51 (redaction), #52 (cache, usage, routing), #55, #58

---

## Goal

Extend `app/adapters/llm.py` — not a second abstraction — so v6 can pick a model per task, cap provider concurrency, meter tokens per run (building on v5 #47's `estimate_cost`), cache structured outputs by content hash, and redact PII/secrets before any text reaches the provider. Existing callers must behave byte-for-byte as before when the new settings are blank.

## Locked decisions

| Decision | Choice | Rationale |
|---|---|---|
| Task routing | `LLMTask` StrEnum (`classify`, `extract`, `write`, `judge`); `generate()`/`parse_structured()` gain `task: LLMTask \| None = None`; model = `settings.llm_model_<task>` or `settings.llm_model` | Additive; no existing signature breaks |
| Usage metering | `ContextVar`-based `UsageMeter` (`with usage_meter() as meter:`); the wrapper records tokens per task into the active meter | No signature churn through services; background runs open their own meter |
| Concurrency | Provider-call semaphore (`LLM_MAX_CONCURRENCY`, default 2) created **lazily per running event loop** | pytest-asyncio uses one loop per test; a module-level `Semaphore` would bind to the wrong loop |
| Cache location | `services/llm_cache.py` (service layer), table `llm_output_cache` keyed by SHA-256 | Adapter stays provider-only; deviation from v4 #31's hash-column-on-row is deliberate (five task types) — recorded in plan §8 |
| Cache key | `sha256(task, resolved_model, prompt_version, canonical-JSON(inputs))`; inputs are the **redacted** text | Secrets never reach the cache table |
| Redaction | Deterministic, ordered regex rules; per-call placeholder map (`<EMAIL_1>`); `restore()` available but extraction/chunk paths use irreversible redaction | Plan §12 |
| Prices | Reuse v5 #47's `estimate_cost` (LiteLLM price map + `LLM_PRICE_*` overrides); per-task price overrides only if a task model is missing from the map; unknown ⇒ "cost unavailable", never a guess | One estimator, not two |

## Scope

### Migration (`0024_add_llm_output_cache.py`)

`llm_output_cache(key varchar(64) PK, task varchar(20), model text, prompt_version text, output JSONB, prompt_tokens int, completion_tokens int, created_at timestamptz default now())`; index on `created_at` for a future prune. Not candidate-owned (content-addressed, holds only redacted inputs' outputs) — documented in the model docstring so it does not read as a violation of the ownership rule.

### Backend (`backend/app/`)

- `adapters/llm.py`: `LLMTask`; model resolution helper `_model_for(task)`; `task` plumbed through `_completion_with_retry`; semaphore wrapper; `UsageMeter` + `usage_meter()` context manager that accumulates per-task tokens and calls v5 #47's `estimate_cost` for the total; log lines gain `task=`.
- `services/llm_cache.py`: `cached_parse_structured(task, prompt_version, key_parts, schema, call)` — get → hit returns validated model (re-validated with pydantic, invalid cached row treated as miss) → miss calls through, stores. Hit/miss counters feed the meter.
- `services/redaction.py`: `redact(text) -> RedactionResult(text, placeholders, counts)`; rules in order: credentials-in-URL, private-key blocks, known token shapes (`ghp_`, `github_pat_`, `gho_`, `AKIA[0-9A-Z]{16}`, `sk-…`, `AIza…`, JWT, Slack `xox[abp]-`), emails, phone numbers, IPv4/IPv6, long high-entropy strings in `key=value`/`: value` context. `restore(text, placeholders)`.
- `core/config.py`: `llm_model_classify|extract|write|judge: str | None`, `llm_max_concurrency: int = 2`, price settings (`float | None`), `evidence_redaction_enabled: bool = True`.
- `setup` service: `POST /api/setup/check` reports the resolved model per task (names only).

### OpenAPI / frontend

`/setup` page lists the per-task models (read-only). Regenerate `schema.d.ts` for the setup response.

### Tests

- Existing `test_llm_*` files must pass **unmodified**.
- `test_llm_task_routing.py`: unset task models → `llm_model`; each task setting honoured; unknown model string passed through.
- `test_llm_concurrency.py`: N parallel calls never exceed the cap (instrumented fake provider); works across two sequential event loops.
- `test_usage_meter.py`: tokens accumulate per task, nested meters isolate, cost "unknown" when prices blank, correct arithmetic otherwise.
- `test_llm_cache.py`: miss → provider called once; hit → zero provider calls; changed `prompt_version`/model/input → miss; corrupt cached JSON → miss and overwrite.
- `test_redaction.py`: table-driven for every rule incl. false-positive guards (commit SHAs and UUIDs are **not** redacted; version strings like `1.2.3.4` in prose vs. real IPs documented); idempotent (`redact(redact(x)) == redact(x)`); `restore` round-trips.
- `test_migrations.py`: `0024` round trip.

### Gates / docs

`ruff` + `pytest` green; `.env.example` gains the model, concurrency, price and redaction settings with comments; `docs/architecture.md` LLM paragraph describes task routing, cache and redaction.

## Risks

| Risk | Mitigation |
|---|---|
| Over-redaction mangles meaningful text (SHAs, IDs) | Conservative rules + explicit negative tests; redaction counts logged so surprises are visible |
| Cache poisoning by a bad earlier output | Cached rows are re-validated on read; `prompt_version` bump invalidates; manual prune is a one-line SQL (documented) |
| Semaphore starves interactive chat during a long extraction | Cap is global but small and calls are short; the chat path is revisited in #58 if latency shows |

## Out of scope

Streaming, provider switching UI, per-user budgets, automatic cost enforcement (estimate and confirm only), embedding caching.
