# Add-impact queue

**Status:** Implemented — branch `v6/impact-queue`
**Follows:** [v6-review-impact-ranking.md](v6-review-impact-ranking.md)

## Goal

Senior resume bullets lead with measurable outcomes, but commits and PRs rarely contain them. The numbers come from the user, so make supplying them quick and focus it on the achievements that matter most.

## Decisions

| Decision | Choice |
|---|---|
| Queue | Drafts and approved achievements with no confirmed metric (`verified` of `evidence` or `user`) and no `impact_skipped` flag, ordered by the shared `base_priority`; the top 40 are served, the total goes in `X-Total-Count`. |
| Adding a number | `POST /api/achievements/{id}/impact` appends a metric with `verified: "user"` and an empty `source_quote`; audited as a `metric_confirmation` revision. The resume writer, figure check and ranking already treat `user` metrics as confirmed. No embedding refresh: the embedding text excludes metrics. |
| "No number" | `POST …/skip-impact` adds the `impact_skipped` review flag (no schema change). Adding an impact later removes it. The flag is hidden from card badges. |
| "Not now" | Client-side only; the item returns next visit. |
| UI | `/evidence/impact`, one card at a time, linked from the review page. |

## Out of scope

Pulling numbers from analytics, suggesting figures, and LLM-drafted outcome wording.
