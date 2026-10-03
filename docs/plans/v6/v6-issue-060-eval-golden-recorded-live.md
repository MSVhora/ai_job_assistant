# Issue #60 — Evaluation: golden dataset, recorded-LLM CI suite, opt-in live suite (Week 4)

**Status:** Proposed — for owner review
**Tracks:** GitHub issue #60 (milestone `v6`, branch `v6/52-eval-golden-recorded-live`)
**Plan of record:** [v6-implementation-plan.md](v6-implementation-plan.md) §11
**Depends on:** #52, #55, #56, #58 (everything it measures); the `RecordedLLM` scaffolding is started earlier and used by #52/#55 tests
**Blocks:** #61

---

## Goal

Make quality measurable and regression-proof: a small golden dataset for a synthetic persona, recorded LLM fixtures so CI is deterministic and offline, and an opt-in live suite that scores faithfulness, bullet quality, retrieval and the agent against the user's real provider. Also produces the data for the `LLM_MODEL_WRITE` decision (plan §14.3 #3).

## Locked decisions

| Decision | Choice | Rationale |
|---|---|---|
| Location | `backend/tests/eval/` — `golden/`, `recordings/`, `test_*_eval.py`, `conftest.py` | Plan §11 |
| Persona | Synthetic "Ada": 4 repos (public, private, fork, bot-heavy), notes, resume profile with deliberate conflicts; no real person's data | Safe to commit |
| Recording mechanism | `RecordedLLM` in `tests/fakes.py` monkeypatches `app.adapters.llm.generate`/`embed`; key = SHA-256 of `(task, resolved model name, system, prompt, schema)`; missing key → test fails with "re-record" | Deterministic, no VCR dependency |
| Record mode | `EVAL_RECORD=1 pytest tests/eval` uses the configured real key and rewrites recordings; recordings are scrubbed (no keys, no real data) and committed | Reviewable diffs |
| Live suite | `pytest -m live_llm`, additionally gated by `EVAL_LIVE=1`; prints a metric table; exits non-zero below thresholds; never part of default CI | Cost and flakiness control |
| Judge | `LLMTask.judge` for entailment/rubric scoring in live mode only; CI uses deterministic checks | CI stays offline |
| Thresholds | As plan §11.2 (fabricated-number rate = 0 in CI; recall@5 ≥ 0.80; page-fit 100 %; live: faithfulness ≥ 95 %, router fallback ≥ 90 %, bullet rubric ≥ 4/5) | Gates tied to hard requirements |

## Scope

### Golden dataset (`backend/tests/eval/golden/`)

`github/*.json` (scrubbed REST/GraphQL responses incl. merge commits, bots, lockfile PRs, `fix typo`), `evidence_expected.yaml` (items that must be filtered and why; chunk boundaries), `achievements_expected.yaml` (must-have claims and **must-not-have traps**: no-metric chunk ⇒ no numbers and `result is None`; evidence ids outside the chunk), `profile.json` (conflicts: employer dates mismatch, missing skill, contradicting metric), `jds/*.md` (3 close, 3 distant), `matches.json`, `questions.yaml` (≈ 40: type label, expected achievement ids, unanswerable flag), `notes/*.md`.

### Harness

- `tests/eval/conftest.py`: loads persona into a scratch DB via the real services (sync with `MockTransport` → chunks → extraction with recordings → auto-approve fixture achievements), exposes fixtures for resume and agent tests.
- `RecordedLLM` + recorded embeddings so retrieval metrics are reproducible without a provider.
- Metric helpers: `faithfulness_numbers`, `claims_supported`, `retrieval_recall_at_k`/`mrr`, `bullet_rubric`, `page_fit`; shared with the production verifier code where appropriate (single implementation of "is this number in the evidence").

### CI tests (offline, default `pytest`)

- Noise filter precision/recall vs `evidence_expected.yaml`; chunk boundary goldens.
- Extraction traps: zero fabricated numbers, evidence-id subset always holds, `result` null where unsupported.
- Resume: zero fabricated numbers across all golden achievements and all JDs; every bullet has evidence; `needs_review` set on injected unsupported claims; page fit `pages ≤ target` and maximal-priority inclusion for targets 1–4 across all JD × template combos plus the synthetic documents from #56; determinism check; **JD boost is bounded** (`w = 0` equals untailored order; a high-impact non-aligned achievement still outranks a low-impact weakly aligned one); overlapping roles resolved by priority; comment-apply touches only commented blocks; copy/export contains no private marks.
- Agent: router accuracy on the labelled set; retrieval recall@5 ≥ 0.80 and MRR reported; unanswerable questions refuse; injected claims caught by the validator; citations always resolve.
- Reconciliation: all seven conflict kinds on `profile.json`.
- Private provenance: private repo evidence ⇒ flags set on item, chunk, achievement, bullet and citation; `exclude_private` removes exactly those bullets.
- Recording hygiene test: no recording contains a key-shaped string or an email.

### Live suite (`-m live_llm`, opt-in)

Runs the same pipelines with the real provider: LLM-judge faithfulness on extraction/bullets/answers, bullet rubric scores, retrieval recall with live embeddings, router fallback accuracy; supports `--write-model` comparison (runs the writing task with the default and the candidate model and prints both columns — the evidence for the model decision). Writes a Markdown report to `tests/eval/reports/` (gitignored).

### Gates / docs

`ruff` + `pytest` green offline; `pyproject.toml` registers markers `live_llm`; `docs/instructions/` gains an evaluation note (how to record, how to run live, thresholds); guide 04/05 link to the quality guarantees.

## Risks

| Risk | Mitigation |
|---|---|
| Recordings go stale when prompts change | Prompt-version constants are part of the key; CI fails loudly with a re-record instruction; record command documented |
| Golden set too small to catch regressions | Traps target the hard requirements specifically; set grows with bug reports |
| Live suite costs money | Opt-in, small dataset, cost printed before running, cache reused where keys match |

## Out of scope

Large-scale benchmarking, human-labelled quality studies, automatic prompt optimisation, CI secrets for live runs.
