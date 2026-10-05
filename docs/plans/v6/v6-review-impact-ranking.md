# Review ranking: impact first, shared with the resume builder

**Status:** Implemented — branch `v6/impact-ranking`
**Follows:** [v6-review-grouping-bulk.md](v6-review-grouping-bulk.md)
**Plan of record:** [v6-implementation-plan.md](v6-implementation-plan.md) §6.2 step 4, risk 8 ("rank drafts by impact")

## Goal

The review list was ordered by `difficulty × (1 + evidence_count)`: a hard feature with no outcome outranked a confirmed revenue result. A senior resume is led by outcomes, so the review order should be too.

## Decisions

| Decision | Choice |
|---|---|
| Formula | One source of truth: the review list calls `resume_priority.base_priority` (impact type weight blended with a confirmed metric, difficulty, recency; `RESUME_WEIGHT_*`). Evidence count, then newest, break ties. No second formula to drift. |
| Where it runs | In Python over the filtered set (columns loaded with `load_only`, no embeddings), then paged. Hundreds to a few thousand drafts is cheap; avoids duplicating the formula in SQL. |
| Metrics | Commits rarely carry business numbers, so ranking cannot depend on extracted metrics. "Confirmed" means `verified` is `evidence` or `user`; the user supplies most real numbers (next: the add-impact queue). |
| Filters | `impact_type` and `has_metric` on `GET /api/achievements`, with **Impact** and **Metric** selects on the review page. |
| Schema | No change; the score is computed at read time. |

## Out of scope (next)

The add-impact queue (asking the user for numbers on top achievements), extraction speed and the `achievement_v2` prompt.
