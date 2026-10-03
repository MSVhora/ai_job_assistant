# Issue #50 — GitHub connector, guarded resumable sync, refresh modes (Week 1)

**Status:** In progress — branch `v6/50-github-connector-sync`
**Tracks:** GitHub issue #50 (milestone `v6`, branch `v6/50-github-connector-sync`)
**Plan of record:** [v6-implementation-plan.md](v6-implementation-plan.md) §3.2, §3.5, §4.1, §4.6, §12
**Depends on:** #48 (tables, protocol, settings), #49 (redaction is not needed here; retry reuse only)
**Blocks:** #51 (needs ingested items), #53 (UI), #60 (golden fixtures)

---

## Goal

Pull the user's own GitHub work into `evidence_item` incrementally, within rate limits, and resumably after a crash or pause — with an explicit **refresh** action (incremental or full). Backend only; the UI arrives in #53, so this issue is exercised through the API and tests.

## Spike (deferred to owner — not run; implementation follows GitHub's documented contracts with synthetic fixtures)

The checklist below stays open: run it with your PAT and report any mismatch with plan §3.2/§12; each one becomes a follow-up fix.

1. With the real PAT: `gh api` for `/user`, `/user/repos`, `/repos/{o}/{r}/commits?author=&since=`, one GraphQL PR query (reviews, comments, files, commits); record `X-RateLimit-*` headers and GraphQL `rateLimit { cost remaining }`.
2. Confirm which **fine-grained PAT permissions** are required (expected: Metadata, Contents read, Pull requests read, Issues read) and what an org-owned repo returns without approval.
3. Confirm `Commit.additions/deletions/changedFilesIfAvailable` availability on `history`.
Any mismatch with plan §3.2/§12 is reported back before implementation continues.

## Locked decisions

| Decision | Choice | Rationale |
|---|---|---|
| Transport | `httpx.AsyncClient`, REST for repos/commits, GraphQL for PRs/issues/reviews | Plan §3.2 |
| Own-work scope | Single login (owner decision); commits via `author=<login>`, PRs/issues authored by login, review comments by login | No multi-email in v6 |
| Token | `GITHUB_TOKEN` from settings only; never persisted, logged, or returned; `Authorization` stripped from any logged request/exception | ADR-4 |
| Budget | `GITHUB_MAX_REQUESTS_PER_RUN` (REST requests + GraphQL calls); stop **before** exceeding; floor `GITHUB_MIN_REMAINING_PCT` of the hourly limit | Respect rate limits (hard req. 4) |
| Pause semantics | Budget exhausted / low remaining / secondary-limit `Retry-After` beyond the retry policy → run `paused` with `resume_at`; cursors already committed | Resumable by construction |
| Retry | `retry.with_retry` with `Transient` for 429 and secondary-limit 403 (honouring `Retry-After`) | Reuse, no new policy |
| Cursors | `evidence_scope.cursor` JSONB, committed **per page** in a fresh session from `session_factory` | Survives process death |
| Refresh | `POST …/sync` `mode: "incremental" (default) \| "full"`; full resets scope cursors, re-reads within `EVIDENCE_LOOKBACK_YEARS`, upserts by identity | Owner requirement: refreshable history |
| Forks | Listed with a `fork` flag, **default disabled**; a fork scope whose sync yields zero authored items is marked `empty` | Avoids an expensive "authored commit count" probe per fork up front |
| New repos | Repos found by a later Refresh/Full re-sync are stored as scopes with `enabled=false` and a `new` flag; sync only reads enabled scopes | Refresh can never silently widen what is ingested |
| Private repos | `enabled=false` by default; enabling requires `acknowledged_disclosure: true` (409 otherwise) and stamps `evidence_source.acknowledged_at`; `is_private` copied onto every item | Opt-in + provenance marking |
| Squash/merge dedupe | A commit whose SHA is a PR's merge/head commit is attached to the PR item (`meta.pr_number`) and not kept as a standalone commit | No double counting |

## Scope

### Backend (`backend/app/`)

- `adapters/evidence_sources/github.py`: `GitHubSource` implementing the protocol — `identify()` (`GET /user` → login, granted-permission hints), `list_scopes()` (owned/collab/org repos pushed within the lookback; `is_private`, `fork`, `languages`, `pushed_at`), `sync_scope()` yielding `SyncPage(items, next_cursor, requests_used, rate_limit)`. Item kinds produced: `repo_summary` (+README text, topics, language shares, stars/forks, contribution span), `commit`, `pull_request`, `review_comment`, `issue`. **Never** fetches file contents or patches; PR file *paths* only (GraphQL `files{path}`) for lockfile detection.
- `services/evidence_sync.py`: `start_sync(session, mode)` — sweep stale runs (`max_run_age_minutes`) → advisory select of an active run → insert with IntegrityError translation to `DuplicateSyncError(active_sync_id)` (exact v4 #36 shape); `run_sync(run_id)` background task (fresh sessions via `session_factory`, explicit commits) iterating enabled scopes in a stable order; per page: normalize → `noise.classify` → upsert items (`on_conflict_do_update` by identity) → commit cursor; progress/rate-limit/usage written to `evidence_sync_run`. Failures in one scope mark that scope `failed` with a warning and continue (like a failing job source = warning, not a run error).
- `routers/evidence.py` (HTTP only): `GET /api/evidence/github/status`, `GET /api/evidence/github/scopes` (live list merged with stored opt-ins), `PATCH /api/evidence/github/scopes` (the CORS policy from v5 #46 allows no `PUT`) (enable/disable, `content_level`, `employer_ref` — stored, edited in #53), `POST /api/evidence/github/sync`, `GET /api/evidence/syncs/{id}`, `GET /api/evidence/syncs?limit=`. Ownership checked against the single candidate (`get_or_create_candidate`), 404 on mismatch.
- `core/errors.py`: `DuplicateSyncError(DomainError)` → 409 with `{"detail", "active_sync_id"}` (extend `domain_error_handler` the same way as `DuplicateRunError`); `EvidenceSourceNotConfiguredError` → 400 when `GITHUB_TOKEN` is absent.
- `services/setup.py` + `POST /api/setup/check`: report `github_token_configured` (bool only).
- `adapters/evidence_sources/registry.py`: register `github`.

### OpenAPI / frontend

Regenerate `openapi.json` and `frontend/lib/api/schema.d.ts`. No UI in this issue.

### Tests (`backend/tests/`, `httpx.MockTransport`, golden JSON under `tests/eval/golden/github/`)

- `tests/adapters/test_github_adapter.py`: identity; scope listing (private/fork flags); commit paging with `since`; ETag `If-None-Match` → 304 yields no items and costs no budget; GraphQL PR page mapping incl. review comments and file paths; own-work filtering (other authors ignored); no request is ever made to a contents/patch endpoint (asserted on the mock transport log).
- `tests/services/test_evidence_sync.py` (Postgres): happy path writes items + advances cursors; **kill mid-run** (cancel the task after page 2) then `incremental` start continues from the stored cursor with no duplicates; budget exhausted → `paused` with `resume_at`; low `X-RateLimit-Remaining` → paused; `full` mode resets cursors and re-upserts without duplicating or losing rows; noise-filtered items stored with reasons; one failing scope does not fail the run.
- `tests/services/test_duplicate_sync_concurrency.py`: mirrors `tests/services/test_duplicate_run_concurrency.py` (two concurrent starts → one 202, one 409 with `active_sync_id`; index-only path with the pre-flight select patched out).
- `tests/routers/test_evidence_endpoints.py`: disclosure required for private scopes (409), token-missing 400, 404 on foreign ids, response bodies never contain the token (grep the serialized responses and captured logs for the test token string).
- Sweeper test: stale `running` row is marked failed and releases the lock.

### Standards from v5 (must hold from the first commit)

- **Lint/types:** ruff `ALL` and pyright strict pass with no new `noqa`; untyped third-party values are narrowed through small typed helpers (the pattern in `adapters/llm.py`); a `# pyright: ignore` needs a reason comment. Functions stay within the configured limits (args 6, branches 13, returns 8, complexity 14).
- **Coverage and layout:** the 90 % floor holds with `TEST_DATABASE_URL` set; new code ships with its tests in the mirrored folders (`tests/adapters/`, `tests/services/`, `tests/routers/`, `tests/db/`, `tests/core/`; recorded/golden suites in `tests/eval/`).
- **Config:** every new `Settings` field appears in `.env.example` (the settings↔env guard test fails otherwise); no `os.getenv`/`os.environ` and no provider SDK imports outside their one module.
- **API:** new routes keep `response_model` (binary downloads declare their media type instead), use only the CORS-allowed methods (`GET`, `POST`, `PATCH`, `DELETE`, `OPTIONS` — **never PUT**) and headers (`Content-Type`, `Accept`), raise `DomainError` subclasses (checked by `tests/core/test_error_contract.py`), and bound every list with the shared `pagination()` dependency and `X-Total-Count`.
- **Privacy:** no resume/evidence text, prompts, tokens or keys in logs (extend `tests/routers/test_logging_privacy.py` for the new flows); LLM calls log `cost_usd=`; outbound HTTP has an explicit timeout.

### Gates / docs

the backend gate (`ruff check . && ruff format --check . && pyright && pytest --cov=app` with a scratch `TEST_DATABASE_URL`) and `pre-commit run --all-files` green; `.env.example` PAT instructions (fine-grained, read-only, selected repos); `docs/guide/04-evidence-and-resume.md` created as a draft (connect, scopes, refresh vs full, rate-limit pausing); `/setup` guide section.

## Risks

| Risk | Mitigation |
|---|---|
| Org repos need approval or a classic PAT | Spike documents it; status endpoint explains inaccessible repos; classic-PAT path documented |
| GraphQL node/cost limits on busy repos | Small page sizes (≤ 50 PRs), cost read from `rateLimit`, cursor per page |
| `BackgroundTasks` dies on restart mid-run | Cursor-per-page + sweeper; start endpoint is safe to call again |
| Rate-limit headers differ between REST and GraphQL | Separate trackers, both feed `evidence_sync_run.rate_limit` |

## Out of scope

UI, chunking/embedding (#51), LLM calls, GitLab/Bitbucket, multiple emails/accounts, fetching code or diffs, webhooks, scheduled auto-sync (refresh is user-triggered).

## Implementation notes (deviations from the plan above)

- **Spike not run:** built from GitHub's documented contracts with synthetic fixtures (`tests/eval/golden/github/`); the spike checklist above is still open for the owner. Fine-grained PAT permissions in `.env.example`/guide 04 are the documented expectation, not a verified result.
- **Commits via GraphQL, not REST:** commits come from `defaultBranchRef.history(author: {id})`, which carries `additions`/`deletions`/`changedFilesIfAvailable`/`parents`. REST commit lists have no sizes, so the noise filter's size gates (dependency bumps, tiny trivia) could never fire. Only the default branch is read. REST is used for `/user`, `/user/repos`, repo summary, languages and README.
- **Search-backed stages:** PRs, reviews and issues use GraphQL `search(repo: author: updated:>=)` so the author filter is server-side. Review items are one `review_comment` per PR (review text plus inline comments), external id `owner/repo#N:review`.
- **ETag** is used on the repo-summary request (`summary_etag` in the scope cursor); a 304 yields no summary item and is not counted against the request budget. It is not used for commits (a moving `since` makes it useless).
- **Per-run source instance:** the registry now stores factories (`_FACTORIES`), because a run owns the request budget and rate trackers. The #48 registry test was updated accordingly.
- **Cursor:** `evidence_scope.cursor` holds `{stage, since, started_at, watermark, summary_etag, *_after}`; each pass starts at `watermark - 1 day` (or the lookback floor), and `full` mode resets it to `{}`.
- **Upsert** only rewrites a row whose `content_hash` changed, so a status the user restored later (#53) is not reset by an unchanged re-sync. Squash commits are attached to their PR (`filtered`, reason `squash_of_pull_request`, `meta.pr_number`) once per commit.
- **`is_new`** on a scope means "stored by this listing call"; there is no persisted flag. `is_fork` and `description` come only from the live listing.
- **Disclosure:** `acknowledged_disclosure` is required the first time a private scope is enabled; once `acknowledged_at` is set it is not required again.
- **Not implemented:** the repo summary's "contribution span" (needs commit dates across the pass) and the "empty fork" marker; forks simply start disabled.
- **Status endpoint** reports stored login/counts and never calls GitHub; the login is stored when scopes are listed.
