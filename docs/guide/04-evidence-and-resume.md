# 4. Evidence from GitHub (draft)

> **Status: draft, grows with v6.** This page covers what exists after issue #52: connecting
> GitHub, choosing repositories, syncing, notes, links, resume bullets, chunking and achievement
> extraction. Achievements, the resume builder and the interview
> agent arrive in later v6 issues and will be added here.

The v6 **Developer Evidence Engine** turns the work you actually did into an evidence store that
later features build on. Nothing here changes jobs, matches or your profile.

## Connect GitHub

1. Create a **fine-grained, read-only personal access token** on GitHub. Grant *Metadata*,
   *Contents (read)*, *Pull requests (read)* and *Issues (read)*, and select only the repositories
   you want to use.
2. Put it in `backend/.env` as `GITHUB_TOKEN=` and restart the API. The token never goes to the
   database, the frontend or the logs; rotate it by editing `.env`.
3. `POST /api/setup/check` reports `github_token_configured`; `GET /api/evidence/github/status`
   shows the connected login and the latest sync.

Only commit messages, pull request / issue / review text, README text, language statistics and the
*names* of files a pull request touches are read. File contents and diffs are never fetched.

## Choose repositories (scopes)

`GET /api/evidence/github/scopes` lists the repositories your token can see (pushed within
`EVIDENCE_LOOKBACK_YEARS`) and stores any new ones **disabled**. Enable the ones you want with
`PATCH /api/evidence/github/scopes`:

- Forks are listed but, like every new repository, start disabled.
- **Private repositories** need `acknowledged_disclosure: true` the first time: their text is later
  sent to your LLM provider. The acknowledgement is stored, and everything ingested from a private
  repository stays marked private.
- `content_level` and `employer_ref` are stored per repository and edited in the review UI later.

A refresh can never silently widen what is ingested: repositories found later are added disabled.

## Sync and refresh

`POST /api/evidence/github/sync` starts a background run (202) and returns `sync_id`; poll
`GET /api/evidence/syncs/{id}`.

| Mode | What it does |
|---|---|
| `incremental` (default) | Reads only what changed since each repository's last completed pass (with a one-day overlap) |
| `full` | Resets every repository's cursor and re-reads the whole lookback window; rows are updated in place, never duplicated |

- Only one run per source is active at a time (a second start returns **409** with
  `active_sync_id`); a run stuck longer than `MAX_RUN_AGE_MINUTES` is swept so you can start again.
- **Rate limits.** A run stops *before* spending more than `GITHUB_MAX_REQUESTS_PER_RUN` requests or
  when GitHub reports less than `GITHUB_MIN_REMAINING_PCT` of the hourly limit left, and ends
  `paused` with `resume_at`. Starting a sync again continues from the saved per-repository cursors.
- A repository that fails (no access, deleted) becomes a warning on the run; the others continue.
- Noise (merge commits, bots, dependency bumps, lockfile-only or trivial changes) is **stored but
  marked filtered** with the reason, so you can restore it later. Standalone commits that are the
  squash of a pull request are attached to that pull request instead of counted twice.

## Notes, links and resume bullets

GitHub is one source. You can add evidence yourself, and it is chunked exactly like GitHub text:

- **Notes** (`POST/GET/PATCH/DELETE /api/evidence/notes`): free text up to 20,000 characters with an
  optional title. Editing a note creates a new version and hides the old one; deleting hides it
  (nothing is removed, so an identical note can be re-added later). The same text twice is a 409.
- **Links** (`POST /api/evidence/links`): an `http(s)` URL with an optional title and optional pasted
  text. Links are **never fetched**. A link is only chunked, and so only usable later, when you
  paste text for it.
- **Resume bullets** (`POST /api/evidence/resume/ingest` with a `profile_id`): every experience and
  project bullet of that profile becomes a `resume_line`. The same bullet in two profiles is one
  item; re-ingesting after you edit a profile adds new bullets and hides the ones you removed.

## What "filtered" means, and restoring an item

Every item is `kept`, `filtered` or `excluded`. **Filtered** means the noise filter set it aside
(merge commit, bot, dependency bump, lockfile-only or trivial change, or the squash of a pull
request) and it is shown with its reason. **Excluded** means you removed it. Neither is chunked or
sent to an LLM. `GET /api/evidence/items?status=filtered` lists the filtered ones;
`PATCH /api/evidence/items/{id}` with `{"status": "kept"}` restores one (or `"excluded"` removes a
kept one). Nothing here changes your profile.

## Chunks and embeddings

Kept items are grouped into **chunks**, the unit later features extract from and search:
one per pull request (with its squash commit messages and a file-path summary), per burst of
direct commits (a gap of 7 days or more starts a new one, at most 30 commits), per repository
summary, issue, review, note paragraph group and resume entry. Chunks are rebuilt automatically at
the end of every sync and after a note, link, resume or restore change.

- Chunk text is **redacted** (emails, phone numbers, IPs, tokens and keys become placeholders such
  as `<EMAIL_1>`); the original text stays on the item. Turn this off only with
  `EVIDENCE_REDACTION_ENABLED=false`.
- Each chunk is embedded once. Re-running with no change makes no embedding calls; editing an item
  re-embeds only its chunk. If the provider fails, the chunk is kept without a vector and the next
  rebuild retries it.
- `GET /api/evidence/chunks/summary` reports chunk counts, tokens, the private share and how many
  chunks still wait for an embedding.

## Extraction and the cost estimate

An **achievement** is a short STAR story (situation, task, action, result) with the skills it
shows, an impact type, a difficulty from 1 to 5 and links to the evidence it came from. Extraction
turns chunks into **draft** achievements with your cheap model (`LLM_MODEL_EXTRACT`, else
`LLM_MODEL`). Drafts are never used for resumes or the agent until you approve them (review comes
with a later issue).

1. `POST /api/evidence/extract/estimate` shows what a run would do: how many chunks are new, how
   many are already cached (free) or up to date, the token and USD estimate (or "cost unavailable"
   for an unpriced model), and how much of it comes from private repositories. Nothing is sent.
2. `POST /api/evidence/extract` with `confirmed_estimate_id` starts the run. If the evidence,
   prompt version or model changed since the estimate you get a 409 and estimate again.
3. Poll `GET /api/evidence/extract/runs/{id}`; list drafts with `GET /api/achievements?status=draft`.

What keeps drafts honest: the model may only cite evidence from the chunk it was given
(anything else is rejected); a number counts as **evidence-verified** only if the model quotes it
verbatim from that evidence, otherwise the metric is kept as `needs_confirmation`; a **result** is
kept only with a quote that supports it, so no stated outcome means no result; and text containing a
redaction placeholder is flagged. Re-running with no change costs nothing; a changed chunk or a new
prompt version re-extracts only what needs it, and one failing chunk never fails the run.

## Not yet verified against live GitHub

The connector was built from GitHub's documented REST/GraphQL contracts and tested with synthetic
fixtures. The live spike in the issue plan (token permissions, GraphQL cost, organisation
repositories) is still to be run with a real token.
