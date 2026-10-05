# Extraction and sync speed

**Status:** Implemented — branch `v6/extraction-speed`
**Follows:** [v6-add-impact-queue.md](v6-add-impact-queue.md)
**Plan of record:** [v6-implementation-plan.md](v6-implementation-plan.md) §5 (evidence pipeline)

## Goal

After issue #56 testing (70 repositories): sync took 20–30 minutes and extraction 2–3 hours. Make both noticeably faster without changing what is extracted from the chunks that matter.

## What the data said

`run_extraction` processed chunks one at a time, so `LLM_MAX_CONCURRENCY` (default 2) never applied to extraction. In the tester's database (773 chunks) a third were under 200 characters; those 254 chunks produced 15% of the achievements, at an average difficulty of about 2.5 against 3.4 for chunks over 400 characters, and 44% of them produced nothing at all.

## Decisions

| Decision | Choice |
|---|---|
| Concurrent extraction | `asyncio.TaskGroup` with a semaphore: `EXTRACTION_CONCURRENCY` (default 4, max 8, bounded by DB pool). Each chunk already owned its session; counters and progress are updated under a lock. Provider cap `LLM_MAX_CONCURRENCY` default raised from 2 to 4; lower it if the provider returns 429s (retry and backoff still apply). |
| Cache-hit accounting | A chunk is "cached" when its LLM call closure never ran, instead of comparing meter counters, which interleave under concurrency. |
| Short-chunk filter | `EXTRACTION_MIN_CHUNK_CHARS` (default 200; 0 disables). Notes and resume lines are never skipped. Skipped chunks are not marked extracted, so lowering the setting brings them back; the estimate dialog reports the count (`chunks_skipped_short`). |
| Concurrent sync | `EVIDENCE_SYNC_CONCURRENCY` (default 3, max 6) repositories at once. The run's shared JSON progress row is re-read and written under a lock so scopes do not overwrite each other. A pause (rate limit, request budget) stops new repositories from starting; running ones finish or pause themselves. |
| Measuring | `evidence.scope done` now logs per-repository duration, items and filtered counts, so the remaining sync time can be attributed. |

## Not done

A shared HTTP client for the GitHub adapter (a new `httpx.AsyncClient` per request pays a TLS handshake each time) and the `achievement_v2` prompt that caps achievements per chunk (it re-extracts everything, so it is a separate, confirmed step). Both wait on the per-repository timings.
