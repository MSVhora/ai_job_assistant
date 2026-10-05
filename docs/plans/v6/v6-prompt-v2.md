# Extraction prompt v2 and replacing older extractions

**Status:** Implemented — branch `v6/prompt-v2`
**Follows:** [v6-extraction-speed.md](v6-extraction-speed.md)
**Plan of record:** [v6-issue-052-achievement-extraction-star.md](v6-issue-052-achievement-extraction-star.md)

## Goal

About 1,000 achievements came out of 70 repositories, most of them routine feature work that a senior resume leaves out, and impact types were dominated by generic `quality` and `ux`. Extract fewer, better ones, and let the user replace the earlier set.

## Decisions

| Decision | Choice |
|---|---|
| Prompt | `achievement_v2`: output 0 to 2 achievements (the schema ceiling stays 3 so a stray third does not force a repair call); group related changes into one; output none for routine work (pages, endpoints, glue, config, bumps, renames, tests or docs only) unless the evidence shows an outcome, scale, a hard problem or ownership; a one-line definition for each impact type (the ranking weights depend on it); difficulty 4 and 5 used sparingly. Grounding and injection rules unchanged. |
| Re-extract | The version bump changes every chunk's extraction hash, so the normal estimate-and-confirm flow applies. Approved achievements are not touched by it (as before). |
| Replacing v1 | **Owner decision:** re-extract and replace. `GET /api/achievements/older-version` previews and `POST …/older-version/archive` archives approved `ai_extracted` achievements from an older prompt version, **only** when their source chunk was re-extracted under the current version (a failed or skipped chunk keeps its old result) and **not** when `edited_by_user`. Archiving is terminal and writes a `replaced_by_new_prompt` revision. |
| Order for the user | Re-extract, approve the new drafts you want, then archive the older ones, so the knowledge base is never empty. |
| UI | A *Replace older extractions* panel on the review page's Approved tab. |

## Not covered

Achievements you approved one at a time are not distinguished from bulk-approved ones; only edited ones are protected. No live-model comparison of v1 against v2 was run here (it spends the user's provider credits); judge the result on the first re-extract.
