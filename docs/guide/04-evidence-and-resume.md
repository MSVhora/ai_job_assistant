# 4. Evidence, achievements and review (draft)

> **Status: draft, grows with v6.** This page covers what exists after issue #53 (the evidence and review pages): connecting
> GitHub, choosing repositories, syncing, notes, links, resume bullets, chunking and achievement
> extraction. Achievements, the resume builder and the interview
> agent arrive in later v6 issues and will be added here.

The v6 **Developer Evidence Engine** turns the work you actually did into an evidence store that
later features build on. Nothing here changes jobs, matches or your profile.

## Connect GitHub

1. Create a read-only personal access token on GitHub. Which kind depends on where your work is:
   - **Fine-grained token** — best for your own repositories. Grant *Metadata*, *Contents (read)*,
     *Pull requests (read)* and *Issues (read)*, and select only the repositories you want to use.
     A fine-grained token has a single **resource owner** (your account *or* one organization) and
     only sees that owner's repositories, so it cannot cover both your own and an organization's.
     An organization may need to allow fine-grained tokens and approve yours.
   - **Classic token** — use this when most of your work is in repositories you collaborate on
     inside one or more organizations. Tick the `repo` scope (and `read:org` if an organization
     hides its membership). It lists everything you can access in one go, but it is broader than
     the app needs (GitHub offers no read-only repository scope for classic tokens; the app only
     ever reads). If the organization enforces SAML single sign-on, open the token on GitHub and
     choose *Configure SSO → Authorize* for that organization, or its repositories stay hidden.
2. Put it in the **root `.env`** (next to `docker-compose.yml`) as `GITHUB_TOKEN=`; use
   `backend/.env` only if you run the API without Docker. Then recreate the API container with
   `docker compose up -d --force-recreate api` — a plain restart does not re-read `.env`. The token
   never goes to the database, the frontend or the logs; rotate it by editing `.env`.
3. `POST /api/setup/check` reports `github_token_configured`; `GET /api/evidence/github/status`
   shows the connected login and the latest sync.

Only commit messages, pull request / issue / review text, README text, language statistics and the
*names* of files a pull request touches are read. File contents and diffs are never fetched.

## Choose repositories (scopes)

Enabling a repository means **evidence is collected from it**: only the repositories you select
are synced and used to build achievements and resumes, and nothing is read from the rest. On the
Evidence page, tick the repositories you want (the filter box narrows the list, and **Select all**
and **Clear selection** act on the repositories currently shown), then press **Save changes** —
nothing is saved until you do, and **Discard** throws your edits away. If the selection switches on
private repositories, Save shows the disclosure once for all of them. Content level and employer
mapping are part of the same draft.

`GET /api/evidence/github/scopes` lists the repositories your token can see (pushed within
`EVIDENCE_LOOKBACK_YEARS`) and stores any new ones **disabled**. The page saves your selection with
one `PATCH /api/evidence/github/scopes` (up to 200 repositories per request; larger selections are
sent in batches):

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

## Reviewing achievements

Nothing reaches a resume or the interview agent until **you approve it**. Every change below is
recorded as a revision (`GET /api/achievements/{id}/revisions`) with a field-level diff, so you can
always see what was edited, merged or confirmed and when.

- **States.** `draft → approved | rejected`; `approved → draft` (unapprove) or `archived`;
  `rejected → draft` (restore). Anything else is a 409. Archived rows are kept for the audit trail.
- **Approval gate.** `POST /api/achievements/{id}/approve` needs at least one evidence link and no
  metric still marked `needs_confirmation`; otherwise you get a 409 that says why. Confirm a metric
  with `POST …/confirm-metric` ("as written" or with an edited value); it is then marked
  user-verified.
- **Editing** (`PATCH /api/achievements/{id}`) works on drafts and approved rows alike. Editing an
  approved row re-embeds it and rechecks whether it is derived from private data; it stays approved.
  Evidence can be linked or unlinked (an approved achievement always keeps at least one link).
- **Bulk approval** is a preview and a commit: `GET /api/achievements/bulk-approve/eligible` lists
  the clean drafts (evidence present, no pending metric, no redaction placeholder, evidence
  unchanged, and **not derived from private data**, which always needs an individual look);
  `POST /api/achievements/bulk-approve` approves the ids you choose and reports what it skipped and
  why. Unapprove undoes it.
- **Merge and split.** `POST /api/achievements/merge` combines two or more achievements into a new
  draft (evidence, skills and metrics are unioned) and archives the sources.
  `GET /api/achievements/merge-proposals` only *suggests* likely duplicates (same repository,
  overlapping dates, cosine similarity of 0.90 or more); nothing is merged automatically.
  `POST …/split` moves chosen evidence to a new draft; both rows become drafts.
- **Changed evidence.** After a sync, an approved achievement whose linked evidence changed is
  flagged (`evidence_stale_at`, "evidence updated"). It is never altered silently; `POST
  …/acknowledge` clears the flag once you have looked again.
- **Employer mapping.** Each repository can be mapped once to one of your profile's experience
  entries or to **Personal / open source** (`GET /api/evidence/employers`, then `PATCH
  /api/evidence/github/scopes` with `employer_ref`). The scope list suggests a match when the repo
  was active during exactly one job, and the choice applies to all of that repo's achievements.
  Unmapped repos are not blocking; their achievements are treated as projects, never as employer
  experience.

## The two pages

Everything above is available from the app, no API calls needed. Use the **Evidence** link in the
header (or open `/evidence`).

**`/evidence`** — connect and collect:

1. **GitHub connection** shows whether the token is configured and, once repositories are loaded,
   who you are connected as. Without a token the notes and resume sections still work.
2. **Repositories** lists everything your token can see. Tick a repository to include it; new
   ones start unticked and carry a *New* badge, and a refresh never ticks anything for you.
   Ticking a **private** repository opens a disclosure the first time (what can reach your LLM
   provider, what never does, that anything derived is marked private); later private repositories
   ask for a one-line confirmation. Pick a content level per repository, and once a repository has
   synced, map it to an employer (the page suggests one when the repository was active during
   exactly one job) or to *Personal / open source*.
3. **Sync** has **Refresh** (what changed since last time) and **Full re-sync** (re-reads the whole
   look-back window; a confirmation explains that approved achievements are never changed). The
   banner shows progress per repository, GitHub requests used, warnings, and — when a run stops
   early — *Paused, resumes at HH:MM*; start a refresh to continue from where it stopped.
4. **Notes, links and resume** adds your own evidence (see above).
5. **Achievements** shows the chunk summary and **Estimate extraction**, a dialog with chunk counts,
   the token and cost estimate (or "cost unavailable") and, again, how many chunks come from
   private repositories — the second checkpoint before anything is sent. Confirm to start; the page
   follows the run and links to the review page when it finishes.

**`/evidence/review`** — decide:

- Tabs **Draft**, **Approved**, **Rejected** and **Needs attention** (approved achievements whose
  evidence changed). A *Private-derived only* filter narrows any tab. Cards are ranked by
  difficulty and amount of evidence and carry badges: *Private repo*, *Evidence updated —
  re-review*, metrics to confirm, impact, difficulty, employer or project.
- **Approve** is disabled with the reason shown until the achievement has evidence and no
  unconfirmed metric. **Approve all fully-evidenced…** previews the clean, non-private drafts with
  checkboxes before approving.
- Opening a card shows a panel with the story (STAR) editor, metrics (confirm as written, or edit
  the value), tags, the evidence with source links and quotes, split controls and the full revision
  history. Tick two or more cards to **Merge**, or use the *possible duplicates* list, which only
  suggests and never merges by itself.

## Reconciliation

Before a resume is written, the builder compares your profile with your **approved** achievements
and lists where they disagree. It only reports: nothing is changed on its own, and the profile stays
exactly as you saved it. Each conflict has a stable key, so a decision survives re-runs.

| Conflict | Meaning |
|---|---|
| Date outside employment | An achievement is dated outside the time you were at its mapped employer (compared by month; a year-only end date covers the whole year). |
| Employer not in profile | An achievement is mapped to a company your profile no longer lists. Unconfirmed *Suggested* mappings are ignored. |
| Identity mismatch | Your GitHub name, location or public email differs from your profile contact. This reads GitHub on demand and stores nothing; without a token, or if GitHub cannot be reached, the check is skipped and the page says so. |
| Skill missing in profile | Your evidence shows a skill your profile does not list. |
| Skill without evidence | A profile skill has no approved evidence yet (informational; it stays on the resume). Hidden until you have approved achievements. |
| Metric contradiction | A profile bullet states a different figure than a confirmed metric on the same project or employer (same unit, shared topic words; only confirmed metrics count). |
| Overlapping roles | Two roles overlap by at least `RESUME_OVERLAP_MIN_DAYS` (default 60; informational). Unparsable dates never raise a conflict. |

To resolve one, either edit your profile (the normal profile edit, which writes a revision) or mark
it **keep as is** on the document; the profile is not touched. A kept conflict can be reopened.

Resume documents keep a snapshot of the content on every save (the newest 20) and can be exported
as plain text, Markdown or JSON Resume. Exports are clean: no private-repo marks, badges or
provenance, and the contact details come from the document's basics, copied from the profile.

## Writing the resume content

Creating a resume document now also **writes its content** from your approved achievements. It
returns data only — nothing is rendered to a PDF until you ask (see *Choosing a length* below). You choose a page target (1 to 4, at most
`RESUME_MAX_PAGES`), optionally a job description (pasted, or taken from one of your matches
together with its rationale), a tailoring strength and whether to leave out achievements derived
from private repositories.

For each employer and project block the builder ranks your approved achievements by one priority
score, writes a short bullet for the best ones (action verb, scope and — only when you confirmed
one — the measured impact), checks every bullet against its evidence, and keeps the rest of your
achievements ranked and *available* so you can add them later. Bullets are written for about 30 %
more achievements than the page target needs (`RESUME_CANDIDATE_OVERSAMPLE`), so the page fit has
spare material. A role with no approved achievements keeps its own bullets from your profile, so no
role and no document is ever blank. Contact details are never sent to the model.

### Tailoring to a job

A job description is analysed once (cached by its text) into must-haves, nice-to-haves, keywords,
seniority and domain. It changes **which true achievements are chosen and how they are ordered and
phrased — never what is claimed.**

- Every achievement has a base priority that does not depend on the job: impact (its type, and
  whether a metric is confirmed), difficulty and recency (`RESUME_WEIGHT_IMPACT`,
  `RESUME_WEIGHT_DIFFICULTY`, `RESUME_WEIGHT_RECENCY`, summing to 1).
- With a job description, priority = (1 − w) × base + w × alignment, where alignment blends how close
  the achievement is to the job description with how many of its terms the achievement shows. The
  tailoring strength sets w: **Light** half of `RESUME_JD_WEIGHT`, **Balanced** `RESUME_JD_WEIGHT`
  (default 0.30), **Strong** 0.50. Without a job description w is 0.
- The job description is a **boost, not a filter**: aligned work rises, strong work that does not
  align keeps its own priority and still appears. Near-duplicates are demoted so the pool is varied.
- The writer may use the job description's wording only for terms your evidence supports (the
  achievement's tags or terms in its linked evidence, including synonyms such as *K8s* for
  *Kubernetes*). Anything else from the job description is off limits and is checked afterwards.
- The skills list keeps your skills, adds evidence-backed ones, and puts the job-relevant ones
  first. Job keywords with no support are never added.
- **Gaps:** each must-have with no supporting evidence is listed with the nearest achievement, if
  any, and an *Add a note* action. A note becomes evidence, then an achievement you review, and is
  eligible next time. A tailored resume may match fewer keywords than a stuffed one; the gaps list
  shows what is missing and how to close it honestly.

### Why a bullet is flagged

Every bullet passes two checks. First, code: each number, version, year and recognised tool must
appear in the bullet's evidence or confirmed metrics (`40%`, `40 percent` and `40 percent` agree;
`10k` equals `10,000`), and the bullet must start with an action verb in the right tense, stay
within 28 words, avoid filler such as *successfully* or *robust*, and not claim more ownership
(*led*, *owned*, *architected*) than the evidence shows. Second, a model checks that every claim is
supported by the evidence. A bullet that fails is rewritten once with the problems listed; if it
still fails it is marked **needs review**, keeps its reasons, and stays out of the layout until you
fix it or choose **Approve anyway** (the override is recorded with the original reasons). If the
checking model is unavailable, bullets are flagged for review rather than trusted.

Your own edits are pinned: an edited bullet is re-checked by code only (a figure or tool the
evidence lacks flags it, but it is your wording), and regenerating never overwrites a pinned or
edited bullet.

### Comments

Attach a comment to a role, a project or one bullet ("emphasize the migration, drop the tooling
detail"). **Apply comments** rewrites only the commented blocks, passing each comment to the writer
as a request that is followed only where the evidence supports it; the result is verified like any
other bullet. A comment that asks for something the evidence does not support (for example "add
Kubernetes" when nothing mentions it) is **not applied**: it is marked rejected with the reason and
an *Add a note* action. A comment on a pinned or edited bullet is also rejected — edit it directly.
Applied and rejected comments stay on the document as history.

### Overlapping roles

If two employment roles overlap by at least `RESUME_OVERLAP_MIN_DAYS` (default 60; the current role
ends today; unparsable dates are never compared), only the higher-priority role is written, ties go
to the more recent one, and the other is listed as omitted with the reason. Role priority is the
weighted sum of its top three achievement priorities plus a small recency term. Projects and open
source are exempt. **Include anyway** restores an omitted role for this document without removing
the other one.

## Choosing a length

The page target (1, 2, 3 or 4) is the most pages the resume may take, not a number it has to fill.
After content is written, edited, added to or removed, a fit step decides **what is included** by
maximizing the priority of the bullets that fit; a half-empty page is fine when the remaining
material is weaker or does not exist. Nothing is ever padded, and no model is involved.

### What gets included

Only bullets that passed verification (or that you approved anyway) are candidates. They are taken
in this order: pinned bullets, then each role's best bullet (so every included role appears before
any role's second bullet), then the rest by priority. The fit tries three typography presets —
comfortable (10.5 pt, 0.7 in margins), 10 pt with 0.6 in margins, and a floor of 9.5 pt with 0.5 in
margins — and finds the longest run of that order that fits the page target at each. It keeps the
preset that includes the most priority; on a tie the roomier one wins. If a role's best bullet
does not fit, the lowest-priority roles are left out whole.

The result is the document's **layout**: pages used, preset, what is included and what is not
(`did_not_fit`, `needs_review`, `not_written` or `overlap_omitted`, each with its priority). It says
**short on evidence** when everything available is already included and the pages are not full.
If even one bullet cannot fit at the smallest size — for example a one-page target with a very
long skills list — fit and render answer 422 asking you to choose more pages or shorten the fixed
sections; generating content never fails for this reason, it stores an empty layout and a warning.

`POST /api/resume-documents/{id}/fit` re-runs the fit and returns the layout as data; `POST
…/render` is the explicit **Generate PDF** step: it re-runs the fit on the current content and
returns `application/pdf`. PDFs are never stored.

### ATS-friendly output

The PDF is a single column of real text: standard headings (Summary, Experience, Education, Skills,
Projects, Certifications, Awards), a plain bullet glyph, contact details in the body rather than a
header, links as visible text, and no images, tables or text boxes, so applicant tracking systems
read it in order. Two variants exist, `classic` (centered header) and `compact` (left-aligned,
tighter).

## Not yet verified against live GitHub

The connector was built from GitHub's documented REST/GraphQL contracts and tested with synthetic
fixtures. The live spike in the issue plan (token permissions, GraphQL cost, organisation
repositories) is still to be run with a real token.
