# LLM & AI Usage Standards

Applies to every feature that calls a language or embedding model.

> **Target state.** Cost estimation *(H7)* is brought into the code by the
> [hardening plans](../plans/hardening/README.md).

## One door

- All model calls go through `app/adapters/llm.py` (LiteLLM). Never import a provider SDK in routers or services. Provider and model are configuration (`LLM_MODEL`, `EMBEDDING_MODEL`), so swapping a provider is a settings change.
- The adapter owns resilience: the shared retry policy (`adapters/retry.py`, `LLM_RETRY_*`) with exponential backoff, jitter and `Retry-After`; services translate failures into plain messages ("rate limited by the provider — retry shortly").

## Structured output

- Use `parse_structured` with a pydantic schema. The schema is embedded in the prompt (prompt-instructed JSON, not provider response schemas — large schemas made Gemini loop), the response is validated, and **one repair round-trip** is allowed before the call fails.
- Keep schemas small and focused; batch work in bounded chunks rather than asking for a very large object.
- Never trust model output: validate, then clamp or reject; derived facts that can be computed deterministically (for example years of experience) are computed in code, not by the model.

## Prompts

- Prompts live next to the service that owns them, are versioned with a constant (`search_query_v3`, `parse_version`), and the version is stamped on persisted outputs so changes are traceable and re-runs are intentional.
- Third-party text (job postings, resume text) is data, never instructions: delimit it and say so in the prompt.
- Send the minimum necessary context; digests (profile digest, bounded posting digest) are built by shared helpers so embeddings and prompts stay consistent.

## Determinism, caching and cost

- Persisted defaults are generated at temperature 0; only explicit "regenerate/alternatives" actions use a hot temperature.
- Cache LLM output by a content hash of its inputs (for example `profile.queries_input_hash`) and skip the call when the hash is unchanged. Changing the prompt version changes the hash.
- Every call returns and logs token usage and duration. **Batch or user-triggered LLM actions are confirm-gated and show an estimated cost before running** *(H7: `estimate_cost`, price settings)*. Automatic background generation must be hash-gated so unchanged inputs never pay twice.
- LLM work never runs in the request path of a read endpoint; it runs in explicit actions or background tasks with queryable status.

## Graceful degradation

- A failing model call degrades the feature, not the app: re-rank failure leaves hybrid-scored matches with a warning; an embedding failure stores the posting without a vector and reports it; extraction failures leave existing data untouched.
- Postings or profiles without embeddings are scored on the remaining signals, never silently dropped.

## Embeddings

- Dimension is pinned to the model (`EMBEDDING_DIMENSIONS=768`, matching the `vector(768)` columns). Changing model or dimension means a new column and a backfill migration, never a silent change.

## Testing

- Default tests use fakes and fixtures; no live provider calls (see [testing.md](testing.md)).
- Cover: schema validation failure + repair, retry classification, cache hit/miss, degradation paths.
