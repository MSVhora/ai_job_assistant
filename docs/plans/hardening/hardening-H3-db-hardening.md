# H3 — Database hardening: `updated_at` trigger and standards audit

**Status:** Proposed — for owner review
**Tracks:** `hardening/H3-db-hardening`
**Plan of record:** [README](README.md) · standards: [database-postgres.md](../../instructions/database-postgres.md) (*H3* rules)
**Depends on:** H2 (tests live in the mirrored layout) · **Blocks:** v5 (migration numbering), H1

## Goal

Make the database standards true: `updated_at` is maintained by the database (ORM `onupdate` does not fire for bulk `UPDATE`, which already bit us in v4 #36), every FK column is indexed, constraints/indexes are named predictably, ON DELETE/CHECK rules are written down per table, and no SQL is built by string formatting.

## Evidence

- `Candidate`, `Profile`, `Match`, `MatchRebuild`, `JobSearch` define `updated_at` with `onupdate=func.now()` only (ORM side). Bulk statements exist: `services/ingestion.py` (stale-run sweeper `update(JobSearch)`) and `services/matching.py` (`update(Match).values(...)`).
- `core/db.py` `Base` has no `MetaData(naming_convention=...)`.
- Quick scan: no f-string/`%` SQL in `app/`, `alembic/`, `scripts/` (grep for `text(f`, `execute(f`, `exec_driver_sql(f` is empty) — the audit makes this a repeatable check.
- FK-column index coverage and ON DELETE/CHECK consistency have not been audited.

## Locked decisions

| Decision | Choice | Rationale |
|---|---|---|
| `updated_at` mechanism | plpgsql `set_updated_at()` + `BEFORE UPDATE ON <table> FOR EACH ROW WHEN (OLD.* IS DISTINCT FROM NEW.*) EXECUTE FUNCTION set_updated_at()` on every table that has the column | Fires for ORM and bulk updates; no touch on no-op updates |
| Migration | `0021_add_updated_at_trigger`; downgrade drops triggers and function | One reviewed migration; models unchanged apart from a comment |
| ORM `onupdate` | Left in place | Harmless, keeps in-memory objects fresh; the trigger is authoritative |
| Naming convention | Add `MetaData(naming_convention=...)` to `Base` using the **PostgreSQL default patterns** (`%(table_name)s_pkey`, `%(table_name)s_%(column_0_name)s_fkey`, `..._key`, `..._check`, `ix_%(column_0_label)s`) | New unnamed constraints get predictable names without renaming any existing one |
| Drift gate | `alembic check` (autogenerate yields no diff) runs in the migration test | Proves the naming convention and trigger migration cause no schema drift |
| Audit outputs | A script `backend/scripts/audit_schema.py` (read-only, runs against a migrated scratch DB) that lists: FK columns without an index, FKs without an explicit ON DELETE, nullable columns that should be NOT NULL candidates, unnamed constraints | Repeatable evidence; fixes land in one extra migration `0022_...` **only if** it finds gaps |
| ON DELETE policy | CASCADE owned children; RESTRICT identity/audit; SET NULL provenance (as in the standard) | Matches existing models; the audit checks it table by table |

## Scope

- Models: add the naming convention to `Base`; add a short docstring note on the trigger convention to models with `updated_at`.
- `alembic/versions/0021_add_updated_at_trigger.py` (+ `0022_...` if the audit finds index/constraint gaps).
- `scripts/audit_schema.py` and a test that runs it against the migrated test DB and asserts an empty finding list (after fixes).
- A reusable Alembic helper (`alembic/helpers.py`) with `create_updated_at_trigger(table)` / `drop_...` so future migrations add the trigger in one line; documented in the standard.

## Tests (`tests/db/`, scratch Postgres)

- Raw bulk `UPDATE ... SET status = ...` bumps `updated_at`; an update that changes nothing does not.
- Sweeper and `update(Match)` paths bump `updated_at` without setting it explicitly.
- Migration `0021` up/down round trip; `alembic check` clean.
- `audit_schema` test: no unindexed FK columns, no unnamed constraints created after the convention, expected ON DELETE per table.
- Grep-style test (or ruff rule in H1) that fails on f-string SQL.

## Gates

`ruff` + `pytest` on a scratch DB; `alembic upgrade head` / `downgrade -1` / `upgrade head`.

## Doc impact

`docs/architecture.md`: ER notes mention the `updated_at` trigger and migration conventions; `docs/instructions/database-postgres.md`: remove the *(H3)* markers; **v5 plan migration numbers shift** (tracked in the README "v5 re-plan" step).

## Risks

| Risk | Mitigation |
|---|---|
| Trigger changes "heartbeat" semantics the sweeper relies on | Sweeper compares `updated_at` to a cutoff; any real column change refreshes it, which is the intended heartbeat; covered by a test |
| Naming convention causes autogenerate to rename constraints | Use PG-default patterns; `alembic check` proves no drift |
| Extra migration if the audit finds gaps | Planned as `0022`; v5 numbering shifts by one more |

## Out of scope

ANN (HNSW) indexes, table partitioning, backup tooling, changing existing constraint names.
