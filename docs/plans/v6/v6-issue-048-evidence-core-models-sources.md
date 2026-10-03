# Issue #48 — Evidence core: models, `EvidenceSource` interface, noise filter (Week 1)

**Status:** Proposed — for owner review
**Tracks:** GitHub issue #48 (milestone `v6`, branch `v6/40-evidence-core-models-sources`)
**Plan of record:** [v6-implementation-plan.md](v6-implementation-plan.md) §3.1, §4.2–4.3, §9 (migration `0023`)
**Depends on:** v4 merged (Alembic head `0020`)
**Blocks:** #49 (settings), #50 (connector + sync), #51 (chunking), everything downstream

---

## Goal

Land the storage and contracts every later v6 issue builds on, with no user-visible feature yet: the evidence tables, the sibling `EvidenceSource` protocol and registry, the normalized `EvidenceItemData` schema, and the pure, fully tested noise filter. Nothing here calls GitHub or an LLM.

### Plan-of-record drift (flagged, not silently changed)

| Plan says | This issue does | Why |
|---|---|---|
| ORM class `EvidenceSource` (§9) | ORM class is **`EvidenceSourceAccount`** (table stays `evidence_source`) | The protocol in `adapters/evidence_sources/base.py` is also called `EvidenceSource`; two same-named symbols in `models/` and `adapters/` invite wrong imports. §9 should be updated when this merges. |
| Sweeper age setting for sync runs (new setting implied) | Reuse the existing `max_run_age_minutes` | One knob for "a stuck background run", same semantics as v4 #36. |

## Locked decisions

| Decision | Choice | Rationale |
|---|---|---|
| Interface location | `adapters/evidence_sources/{base,registry}.py`, sibling of `adapters/job_sources/` | ADR-1; `JobSource` contract stays untouched |
| Ownership | Every new table carries `candidate_id` (directly, or via `source_id → evidence_source.candidate_id` for scope/run) | Candidate-scoped knowledge base (owner decision 2026-10-02) |
| Run guard | Partial unique index `uq_evidence_sync_active_run ON evidence_sync_run (source_id) WHERE status IN ('pending','running')` | Same mechanism as `uq_job_search_active_run` (v4 #36); survives multi-worker and crashes |
| Item identity | `UniqueConstraint(candidate_id, kind, external_id)` | Idempotent upserts for incremental/full sync |
| Noise filter shape | Pure functions `classify(item) -> NoiseVerdict(kept: bool, reason: str | None)`; rules are data (compiled regexes and name sets in one module), bot list configurable via `EVIDENCE_BOT_LOGINS` | Auditable, testable without DB/network |
| Filtered items | Stored with `status='filtered'` + `filter_reason`, never deleted | User can restore in review (#53); audit |
| `is_private` | Column on `evidence_item` and `evidence_scope`; `contains_private` on `evidence_chunk` | Provenance marking requirement (owner decision 2026-10-02) |
| `httpx` | Moved from `dev` extras to runtime `dependencies` | Declaration fix; already imported at runtime |

## Scope

### Migration (`backend/alembic/versions/0023_add_evidence_core.py`, models first)

1. Native enums: `evidence_kind`, `evidence_item_status`, `sync_status` (created with the tables; downgrade drops tables then enums, following the repo's existing migration convention — confirm against `0011`/`0014` in review).
2. Tables: `evidence_source`, `evidence_scope`, `evidence_sync_run`, `evidence_item`, `evidence_chunk`, `evidence_chunk_item` with columns exactly as plan §9 (+ `is_private`, `contains_private`).
3. Indexes: FK columns indexed; `evidence_item(candidate_id, project_key)`, `evidence_item(occurred_at)`, `evidence_chunk(content_hash)`; unique constraints listed above; the partial unique index.
4. `evidence_chunk.embedding` is `Vector(768)` nullable with the same pinned-dimension comment as `Profile.embedding`; no ANN index in v6.

Review checklist: no changes to existing tables or enums; no data migration.

### Backend (`backend/app/`)

- `models/evidence.py`: `EvidenceSourceAccount`, `EvidenceScope`, `EvidenceSyncRun`, `EvidenceItem`, `EvidenceChunk`, `EvidenceChunkItem` + the three `StrEnum`s; export from `models/__init__.py` (Alembic autogenerate sees them).
- `schemas/evidence.py`: `EvidenceKind`, `EvidenceItemData` (plan §4.2), `ScopeCandidate`, `ScopeState`, `SyncPage`, `SourceIdentity`, `NoiseVerdict`.
- `adapters/evidence_sources/base.py`: `EvidenceSource` protocol (plan §3.1) and `EvidenceSourceError`/`EvidenceSourceConfigError`; `registry.py` with `get_source(name)`/`registered_sources()` (empty registry until #50, with a fake registered only in tests).
- `services/evidence_pipeline/noise.py`: rules from plan §4.3 — merge commits (`parents > 1` or `^Merge (branch|pull request|remote)`), bots (`[bot]` suffix or configured list), dependency bumps (message regex + ≤ 5 changed lines), lockfile/manifest-only PRs (path set), trivia messages (regex, or ≤ 2 words with ≤ 3 changed lines), generated/vendored-only paths. Order is fixed and the **first** matching rule supplies `reason`.
- `core/config.py`: `github_token: str | None`, `github_api_url: str = "https://api.github.com"`, `github_max_requests_per_run: int = 1500`, `github_min_remaining_pct: int = 10`, `evidence_lookback_years: int = 6`, `evidence_bot_logins: list[str]` (defaults), all validated (`ge`/`le`), `github_token` added to the existing blank-to-None validator.
- `pyproject.toml`: `httpx>=0.27` to runtime dependencies (removed from `dev` duplicates if any).

### OpenAPI / frontend

None (no endpoints yet).

### Tests (`backend/tests/`, scratch Postgres via `migrated_database`)

- `test_migrations.py`: `0023` up/down round trip, enum and index existence.
- `test_evidence_models.py`: `(candidate_id, kind, external_id)` uniqueness; second active `evidence_sync_run` for the same source raises `IntegrityError`, a terminal one does not; cascade from `evidence_source` → scope/run; chunk↔item link integrity.
- `test_evidence_noise.py` driven by `tests/fixtures/evidence_noise_cases.yaml` (≈ 40 labelled synthetic items: merge, bot, `chore(deps)`, lockfile-only PR, `fix typo`, `wip`, and **kept** look-alikes such as "Fix race in token refresh", "Bump retry budget to handle 429s" with a real diff size). Asserts verdict and reason per row; asserts rule order determinism.
- `test_evidence_registry.py`: unknown source → typed error; fake source satisfies the protocol (structural check).
- `test_config.py` (or existing settings tests): new settings parse/validate; blank `GITHUB_TOKEN` → `None`.

### Gates / docs

- `ruff check . && ruff format --check . && pytest` in `backend/`.
- `.env.example`: `GITHUB_TOKEN=` (with the fine-grained-PAT permission note), `GITHUB_API_URL`, `GITHUB_MAX_REQUESTS_PER_RUN`, `GITHUB_MIN_REMAINING_PCT`, `EVIDENCE_LOOKBACK_YEARS`, `EVIDENCE_BOT_LOGINS`.
- `docs/architecture.md`: ER diagram gains the six tables (header link refresh waits for #61); re-run `node scripts/render-diagrams.mjs`.

## Risks

| Risk | Mitigation |
|---|---|
| Noise rules drop a real contribution ("Bump X to fix CVE" is meaningful) | Rules are conservative (size gates), everything filtered stays visible and restorable; golden look-alike cases lock the boundary |
| Schema churn after later issues discover missing columns | Plan fixes the columns up front; later additive migrations (`0025`+) are cheap, and no existing table is touched |
| Enum drop order in downgrade | Round-trip test in CI |

## Out of scope

Any HTTP to GitHub, chunking, embeddings, LLM, endpoints, UI, the `achievement*` tables (#52).
