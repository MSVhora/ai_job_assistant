# Review at scale: employer filter and bulk actions

**Status:** Implemented — branch `v6/review-grouping-bulk`
**Follows:** issue #56 testing (206 repos, 70 synced, about 1000 draft achievements, reviewing one by one was not workable)
**Plan of record:** [v6-issue-053-evidence-review-ui-audit.md](v6-issue-053-evidence-review-ui-audit.md)

## Goal

Make the draft review tractable without removing the human gate: nothing is approved or rejected unless the user clicks, and every bulk move is confirmed with its count.

## Decisions

| Decision | Choice |
|---|---|
| Grouping | An **Employer** filter above the **Repository** filter on the Draft tab, with draft counts, *Personal* and *No employer*. Choosing an employer narrows the repository list; a repository outside it is cleared. |
| Bulk actions | With an employer or repository chosen, **Approve N clean** and **Reject all N** act on the whole view, each behind a confirmation. `POST /api/achievements/bulk-reject` and `…/bulk-archive` (up to 1000 ids) join `bulk-approve`. |
| Clean drafts | **Deviation from #53:** private-derived drafts are no longer excluded from bulk approval. Most work is in private repositories, so the exclusion left almost nothing eligible. The private badge and the private-only filter remain. |
| Performance | Bulk eligibility and bulk approve load evidence counts and rows in a fixed number of queries instead of one per achievement. |

## API

`GET /api/achievements/groups` (drafts by employer then repository, with ids and clean counts); `GET /api/achievements` takes `employer` and `employer_kind` (`personal` / `unassigned`); `bulk-approve/eligible` takes `project_key`.

## Out of scope (next)

Impact-first ranking, the add-impact queue, extraction speed and the `achievement_v2` prompt (items 2–5 of the follow-up plan).
