# Issue #12 — Buffer: seed data, error states, rate-limit backoff

**Status:** Code landed (2026-09-03). §9 acceptance walkthrough pending — needs a human
at the browser with real keys (checklist below; each item gets checked in the issue when
done).
**Tracks:** GitHub issue #12 (Buffer, Week 2) — closes v1
**Plan of record:** [v1-implementation-plan.md](v1-implementation-plan.md) §8 (Buffer day), §9 (acceptance criteria), §10 (risks & mitigations)
**Depends on:** Issues #1–#11 (done). This is the last v1 issue; the §9 walkthrough is its exit gate.

---

## Carry-over review: what of this issue already exists

Re-verified against the code on 2026-09-03:

| Checkbox | State | Resolution |
|---|---|---|
| Seed script with synthetic jobs/profile | Nothing exists — no seed script anywhere; `backend/scripts/backfill_embeddings.py` is the only script and the pattern to follow (service-layer only, run via `docker exec` in the API container). Synthetic building blocks exist in tests: `tests/fakes.py` `VALID_PROFILE` (17–59), `fake_posting` (91–97), `fake_vector` (139–144); `uploads/` is gitignored so clean clones start empty | Lands here |
| Rate-limit backoff + retry on LLM and source calls | Single retry (2 attempts, fixed 1.0 s) already on `llm.generate()` (`adapters/llm.py:66–98`), Adzuna (`adzuna.py:159–179`), Apify (`apify.py:167–194`), each with retry tests. Gaps: **`embed()` has zero retry** (`llm.py:134–148`) — the exact free-tier risk §10 names; fixed delay, no exponential backoff; delays/attempt counts hardcoded module constants, not Settings; litellm `num_retries` unused | Upgrade existing retry to shared exponential policy; close the `embed()` gap. Most of the graceful-degradation work already landed in #7 |
| Error states audited across all sources failing / partial results | Backend largely done: `JobSearchStatus` includes `partial`/`failed`; per-source `SourceOutcome` warnings persisted in `job_search.results`; matching/embedding failures degrade to warnings, never abort the run. Frontend has retry buttons and empty states everywhere. Audit found two thin spots: failed source badge renders amber `warn` not red (`RunBanner.tsx:85` — `Badge` has no red variant at all), and after a hard-failed run `SearchResults` says "sources returned nothing", which reads wrong when the run itself failed | Audit passes over everything; the two thin spots get small fixes |
| §9 acceptance walkthrough on a clean clone | docker-compose + README Quickstart + 4 guide chapters cover the full flow; **no §9 checklist exists** and the walkthrough has never been executed end-to-end | Executes here; results recorded in the issue, gaps fixed |

## Cross-issue sweep: gaps the original draft missed

| # | Gap | Where it lands |
|---|---|---|
| 1 | §10 mitigation "Setup check warns before first search" (embedding provider gap) — no such pre-search check exists; a user with no Gemini key discovers it at search time | Decision row "missing-key pre-search warning" |
| 2 | Seeded demo data must be cleanable and unambiguous vs. real scraped data (a demo posting indistinguishable from a live one is a data-hygiene trap) | Decision row "seed data tagging" |
| 3 | Seed script needs stored matches with sub-scores for the #11 priority slider to have something to reorder | Seed scope |
| 4 | Retry knobs going into `Settings` require `.env.example` lines (definition-of-done) | Doc impact |
| 5 | `docs/guide/README.md` per-issue feature status never flips to "v1 complete" | Doc impact |
| 6 | §9 criterion "no resume content ever leaves the deployment" is a trust claim — walkthrough should verify BYOK plumbing (only user-configured providers are called), not just take it on faith | Walkthrough scope |

## Goal

Close out v1: a one-command synthetic demo dataset for clean clones, uniform exponential
backoff on every outbound call (LLM generate, embed, Adzuna, Apify), an audited error-state
surface with the two found thin spots fixed, and a documented §9 walkthrough passing from a
clean clone with only `.env` filled.

**Acceptance (issue):** all §9 criteria pass from a clean clone with only `.env` filled.

## Locked decisions (proposed — owner sign-off before build)

| Decision | Choice | Rationale |
|---|---|---|
| Seed script shape | `backend/scripts/seed_demo.py`, mirroring `backfill_embeddings.py`: service-layer only, `asyncio.run` entrypoint, run via `docker exec` in the API container (it holds DB access + keys); documented in README dev table | Established pattern; no Makefile exists to invent one for |
| Seed contents | Creates one synthetic profile (`fakes.VALID_PROFILE`, "Jane Doe" — no real resume data) with real embedding, plus N≈30 synthetic postings across all configured sources with deterministic 768-d embeddings, deduped by `(source, external_id)`; computes vector matches in SQL and stores `match` rows so the dashboard, filter bar, and #11 slider are fully populated. LLM re-rank skipped by default — seeded matches are vector-scored, rationale empty (matches what an unranked row looks like) | A demo dashboard in minutes with **zero LLM/Apify spend** — the point of a seed script on free tiers. `--rerank` opt-in flag can exercise the real LLM path |
| Seed data tagging | Every seeded posting gets `external_id` prefixed `demo-`; `--reset` flag deletes all `demo-*` postings, their matches, and the seeded profile (matched by a fixed synthetic email) before/after seeding | Clean clone → demo → reset loop must be safe; synthetic data must never be mistaken for live results |
| Retry policy | One shared helper in `adapters/` (e.g. `_retry.py` or inline in `llm.py` + connectors): exponential backoff with jitter, `delay = base * 2^attempt + jitter`, honouring `Retry-After` header when a 429 provides it. Applied to `generate()` (upgrades the existing single retry), **`embed()` (new)**, Adzuna `_get_json`, Apify `_request_json` | §10 names "Gemini free-tier rate limits → backoff + retry" explicitly; embeddings are the batch-heavy call most likely to hit it. One policy, four call sites, tested once |
| Retry configuration | New Settings: `llm_retry_attempts` (default 3), `llm_retry_base_delay_s` (default 1.0); connectors reuse the same values (single-user self-host doesn't need per-source knobs). `.env.example` documents both with a free-tier note | Hardcoded constants can't be tuned without a redeploy; one knob set matches the single-user posture. No new dependency (no tenacity — stdlib `asyncio.sleep` + `random`) |
| litellm `num_retries` | Not used; the shared helper stays the single retry path | Two overlapping retry layers (litellm's + ours) would multiply worst-case waits unobservably; the custom loop is what the existing tests exercise |
| Backoff ceiling | Cap total added latency: max 3 attempts per call by default; Apify's 600 s run-poll deadline unchanged (polling is not retried — a timed-out actor run fails its source and the run degrades, which is already the correct behaviour) | Free-tier backoff must not turn a search into a multi-minute hang; degradation is the designed fallback |
| Failed-state visuals | `Badge` gains a `danger` variant (red, matching the existing palette); `RunBanner` renders failed run status and failed source outcomes with it; run-status label for `failed` gets a distinct line pointing at the per-source warnings | All-failed vs partial must not both read as amber "warnings" — the audit item |
| Failed-run empty state | `SearchResults` distinguishes "run failed" (status from the run + per-source warnings, no "sources returned nothing" wording) from "run succeeded but zero postings" | Post-failure copy must match the failure, not imply an empty result set |
| Missing-key pre-search warning | The jobs page already blocks on "no sources enabled"; extended: sources whose keys are absent from Settings render as disabled with a "key not configured" hint (Adzuna/Apify chips), and Gemini-key absence shows a warning card on setup/upload before the first extraction | §10's "warns before first search, not at failure time"; frontend-only, reads the same `/api/sources` config data |
| §9 walkthrough | Executed manually on a clean clone (fresh `git clone` + empty volume, `.env` filled): each of the 7 criteria exercised with real keys; results + any gaps recorded as a checklist in this plan's Done note; small gaps fixed in this issue, anything structural goes to a new issue | The exit gate for v1; "no resume content leaves the deployment" verified by inspecting outbound-call paths (BYOK plumbing), not just claimed |
| New dependencies | None | |

## Scope

### Backend

**Shared retry**
- `adapters/`: extract the retry loop into a shared helper (exponential + jitter + `Retry-After`); wire into `llm.py` `generate()` and `embed()` (embed gains its first retry), `adzuna.py`, `apify.py`
- `core/config.py`: `llm_retry_attempts`, `llm_retry_base_delay_s`

**Seed script**
- `backend/scripts/seed_demo.py` per the locked decisions (service-layer only, `--reset`, `--rerank`)

### Frontend

- `Badge`: `danger` variant; `RunBanner`: failed run/outcome rendering
- `SearchResults`: failed-run vs empty-result states
- `JobsPageClient`/setup: missing-key hints + Gemini-key warning card
- No API schema change expected (statuses/warnings already exist) — verify with `npm run generate:api`, no diff

### Docs

- `.env.example`: retry settings + free-tier note
- README: seed script in the dev table (`docker exec … seed_demo.py`)
- `docs/guide/README.md`: feature status flips to v1-complete after the walkthrough passes
- `docs/guide/01`: §9-walkthrough footnote (clean-clone expectations, free-tier behaviour)
- Plan-of-record §8 Buffer row: note landed (no structural drift)
- No DB schema change → no migration, no diagram changes

### Tests

- Retry helper: unit tests (backoff math, jitter bounds, `Retry-After` honoured, non-retryable fails fast, cap respected); `embed()` retry test added next to `test_llm_generate_retry.py`
- Adzuna/Apify: existing retry tests updated for the new attempt count
- Seed script: smoke test against the scratch DB (seeds, matches readable via `GET /api/matches`, `--reset` leaves no `demo-*` rows)
- Frontend: lint + build; error-state audit recorded as a checklist in the plan (manual verification, as in #11)

### Doc impact

Listed under Docs; the issue's Done comment records the §9 checklist results.

## Definition of done

- `ruff check . && ruff format --check . && pytest` green in `backend/`
- `npm run lint && npm run build` green in `frontend/`
- Seed script verified on a clean DB: seed → dashboard populated → slider reorders → `--reset` clean
- Live check: a 429 from Gemini is retried with visible backoff in logs (op + duration logged, no resume content), and the run still degrades gracefully if it exhausts retries
- All §9 criteria walked through on a clean clone; checklist recorded in the issue
- Docs updated as above; guide status flipped to v1-complete

## Out of scope (this issue)

Redis queue / worker process, per-source RPS throttling, ATS scorer (v1.1), saved searches,
new job sources, any change to matching logic or the `JobSource` interface. Fast-follows
stay in §11 of the plan of record.

## Open questions (owner)

1. **Sign-off on the seed approach** — resolved by proceeding with the recommendation:
   vector-scored matches with empty rationale by default (zero spend), `--rerank` opt-in.
2. **Demo data retention** — resolved by proceeding with the recommendation: `--reset` is
   documented as "do not run while a background search is active" (script docstring).

## §9 acceptance walkthrough checklist (owner, clean clone + real keys)

- [ ] Clean clone: fresh `git clone` + empty volume → `cp .env.example .env`, fill keys,
      `docker compose up -d`, `alembic upgrade head` (README Quickstart)
- [ ] Upload a single-column resume → editable profile in <30 s on the free Gemini tier
- [ ] Correct every AI-extracted field → corrections appear in `profile_revision`
- [ ] Gap-fill asks only about genuinely missing fields
- [ ] Both sources return normalized postings; dedupe across sources works
- [ ] New Apify actor added via `connectors.yaml` + mapper only (config-only check)
- [ ] Ranked matches with rationale for the top 10
- [ ] Scraping source cannot be enabled without the ToS disclosure; badges on every card
- [ ] No resume content leaves the deployment except to the user's own configured
      providers (spot-check outbound-call paths: only LiteLLM/Apify/Adzuna adapters make
      HTTP calls; keys never leave `.env`)
- [ ] Error paths: kill a key → sources warn individually; kill all keys → red failed
      banner; extraction failure → 409 re-extract affordance
- [ ] Seed script on the clean clone: seed → dashboard populated → `--reset` clean
