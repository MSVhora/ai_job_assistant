# 4. Evidence from GitHub (draft)

> **Status: draft, grows with v6.** This page covers what exists after issue #50: connecting
> GitHub, choosing repositories and syncing. Achievements, the resume builder and the interview
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

## Not yet verified against live GitHub

The connector was built from GitHub's documented REST/GraphQL contracts and tested with synthetic
fixtures. The live spike in the issue plan (token permissions, GraphQL cost, organisation
repositories) is still to be run with a real token.
