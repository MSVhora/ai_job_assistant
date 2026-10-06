# Issue #41 — Backend strict tooling: ruff ALL, pyright strict, coverage, audit, pre-commit

**Status:** Implemented — see notes below
**Tracks:** GitHub issue #41 (milestone `v5`, branch `v5/41-backend-strict-tooling`)
**Plan of record:** [v5 plan](v5-hardening-plan.md) · standards: [backend-fastapi.md](../../instructions/backend-fastapi.md) (*v5 #41* rules), [security-privacy.md](../../instructions/security-privacy.md)
**Depends on:** #42, #43 · **Blocks:** #46, #47 (written to the strict standard)

## Goal

Give the backend the same kind of automated, strict standard the frontend gets from Prettier + typed ESLint — **strict, not basic** — and then clear the errors it reveals. Errors are expected and accepted; the plan sequences how they are cleared.

## Current state

`pyproject.toml`: ruff `line-length = 100`, `select = ["E","F","I","UP","B"]`; dev deps `pytest`, `pytest-asyncio`, `httpx`, `ruff`; no type checker, no coverage, no lock file, no pre-commit.

## Locked decisions

| Decision | Choice | Fallback |
|---|---|---|
| Lint rules | `select = ["ALL"]` with a short, documented `ignore` list (docstring rules `D*`, `COM812`/`ISC001` formatter conflicts, `CPY`) | Start with a curated family list and widen |
| Test relaxations | `per-file-ignores` for `tests/**`: `S101`, `ANN`, `PLR2004`, `SLF001`, `ARG` | — |
| Import bans | `flake8-tidy-imports banned-api`: `os.getenv`/`os.environ` outside `core/config.py`; provider SDK imports (`openai`, `anthropic`, `google.generativeai`) outside `adapters/llm.py` | Enforces two non-negotiables mechanically |
| Types | **pyright**, `typeCheckingMode = "strict"`, `include = ["app"]` (tests later) | `basedpyright` with a baseline file to clear errors in stages if the count is unmanageable |
| `Any` | ANN401 + pyright `reportAny`-style strictness; third-party gaps wrapped in typed adapters or narrowly ignored with a reason | — |
| Coverage | `pytest-cov`, `--cov=app`, `fail_under` set to the **measured** baseline and raised only | — |
| Dependency lock | `uv` (`uv.lock`, `uv sync --frozen`), Dockerfile updated | `pip-tools` `requirements.lock` |
| Supply chain | `pip-audit` clean or each waiver documented in `pyproject.toml` comments | — |
| Hooks | Root `.pre-commit-config.yaml`: ruff (lint+format), pyright, gitleaks, `check-added-large-files`, trailing-whitespace/EOF; #44 adds the frontend hooks | — |

## Method (measure first)

1. `ruff check --select ALL --statistics` and `pyright` → write the counts per rule/family into this file's notes.
2. Add the config with the full rule set, then clear errors **one rule family per commit**: (a) safe auto-fixes (`--fix`), (b) annotations (`ANN`), (c) exceptions (`TRY`, `BLE`, `EM`), (d) async/security (`ASYNC`, `S`), (e) complexity/style (`C90`, `PLR`, `SIM`, `PERF`), (f) type-checking imports (`TC`), (g) everything else.
3. Pyright strict in the same way: fix by module, `app/core` → `adapters` → `models/schemas` → `services` → `routers`.
4. Temporary `# noqa`/`# pyright: ignore[rule]` are allowed only with a reason comment and are listed in a tracking checklist that must be empty at close.
5. Measure coverage, set `fail_under`, add the gate.
6. Add lock file, `pip-audit`, pre-commit; run `pre-commit run --all-files` once.

## Tests

No behaviour change is intended; the whole suite must stay green after every commit (scratch Postgres). New tests only where a fix reveals a real bug (each bug found is called out in the commit message).

## Gates (become the definition of done)

`ruff check . && ruff format --check . && pyright && pytest --cov=app` in `backend/`; `pre-commit run --all-files` clean.

## Doc impact

`README.md` Development table (new commands, `pre-commit install`); `AGENTS.md` definition of done (target gate becomes enforced, remove the "once #41 lands" note); `docs/instructions/backend-fastapi.md` (final ignore list, remove *(v5 #41)* markers); `docs/instructions/security-privacy.md` (secret scanning is now real).

## Risks

| Risk | Mitigation |
|---|---|
| Error count is huge and stalls | Batch by rule family; allow a short-lived `basedpyright` baseline, ratcheted to zero before close |
| Untyped third-party libs (`pgvector`, `litellm`, `pdfplumber`) | Typed wrapper functions in adapters; targeted ignores with reasons |
| "Fixes" change behaviour | Suite green per commit; no logic edits in a style commit |

## Out of scope

Rewriting modules for taste, adding features, CI (see [future-tasks](../future-tasks.md)).

## Implementation notes

- **Baseline measured:** `ruff --select ALL` = 3,693 errors on the whole backend (1,333 `S101`, 667 `D103`, 453 `COM812`, 257 `PLR2004`, … mostly docstring/test-assert rules); with the documented ignore list 397; pyright strict on `app/` = 236 errors (118 in `adapters/llm.py` + `ingestion.py` combined, mostly untyped litellm/SQLAlchemy results). Both are now zero.
- **Rule families cleared** in three commits: config + mechanical fixes (`EM`, `RSE`, `PT018`, `FURB`, `RET`, `TC`), the remainder of ruff, then pyright by module. Suite stayed at 471 passing after each.
- **Ignore list (in `pyproject.toml`, each with a reason):** `D`, `COM812`, `ISC001`, `CPY`, `FAST001` (the API standard requires an explicit `response_model`; the rule's autofix removed them), `RUF001-003`. Pylint/mccabe thresholds are set to the current maxima (args 6, branches 13, returns 8, complexity 14). Per-file: tests (`S101`, `ANN`, `PLR2004`, `SLF001`, `ARG`, `INP001`, `PLC0415`, `PLR09xx`, `FBT`, `S311`, `A001`, `DTZ011`), `tests/conftest.py` (`TID251`, it sets env before the app imports), `alembic/**`, `scripts/**`, `app/adapters/retry.py` (`S311` jitter), `app/services/profile_service.py` (`PLC0415`, a real `gap_fill` ↔ `profile_service` import cycle).
- **Import bans:** `os.getenv`/`os.environ` and the provider SDKs (`openai`, `anthropic`, `google.generativeai`) via `flake8-tidy-imports`.
- **Remaining suppressions:** no `noqa`. Two `# pyright: ignore[reportUnknownMemberType]` on the litellm `acompletion`/`aembedding` calls (partially unknown third-party signatures), each with its reason. The tracking checklist is therefore not empty by design; these two are the plan's "narrowly ignored with a reason" fallback.
- **Behaviour-adjacent changes** (all covered by the existing suite): `TransientError` rename (N818); `enable_source` takes `acknowledged_disclosure` keyword-only; `date.today()` replaced by `datetime.now().astimezone().date()` (same local date); `JobPostingDetail.from_posting` passes the enums instead of `.value` (same JSON); cross-module private helpers made public (`next_timestamp`, `GeneratedQueries`, `options_block`, `strip_undeclared_options`); `ingestion` upsert builds `on_conflict_do_update` before `.returning()` (same SQL).
- **Coverage:** 90.6% measured with the DB tests; `fail_under = 90`. The floor only holds with `TEST_DATABASE_URL` set (the DB tests skip otherwise and coverage drops below it).
- **Supply chain:** `uv.lock` was already committed; dev tools added to the `dev` extra and the lock regenerated. `pip-audit` flagged three `urllib3` 2.7.0 advisories; `uv lock --upgrade-package urllib3` moved it to 2.8.0 and the lock now audits clean. The Dockerfile installs with `uv sync --frozen --no-dev` (uv image pinned to 0.9.17).
- **Hooks:** root `.pre-commit-config.yaml` (whitespace/EOF/large-file, gitleaks, local ruff check/format and pyright run from `backend/`; `.svg` excluded so generated diagrams are not rewritten). The ruff hooks are local rather than `ruff-pre-commit` because the upstream hook runs from the repo root and `tests/**` per-file ignores did not apply. `pre-commit run --all-files` is clean.
