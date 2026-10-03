# Issue #41 — Backend strict tooling: ruff ALL, pyright strict, coverage, audit, pre-commit

**Status:** Proposed — for owner review
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
