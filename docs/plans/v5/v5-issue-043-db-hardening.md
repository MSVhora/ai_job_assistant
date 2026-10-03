# Issue #43 — Database hardening: `updated_at` trigger and standards audit

**Status:** Implemented — see notes below
**Tracks:** GitHub issue #43 (milestone `v5`, branch `v5/43-db-hardening`)
**Plan of record:** [v5 plan](v5-hardening-plan.md) · standards: [database-postgres.md](../../instructions/database-postgres.md) (*v5 #43* rules)
**Depends on:** #42 (tests live in the mirrored layout) · **Blocks:** v6 (migration numbering), #41

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
- Grep-style test (or ruff rule in #41) that fails on f-string SQL.

## Gates

`ruff` + `pytest` on a scratch DB; `alembic upgrade head` / `downgrade -1` / `upgrade head`.

## Doc impact

`docs/architecture.md`: ER notes mention the `updated_at` trigger and migration conventions; `docs/instructions/database-postgres.md`: remove the *(v5 #43)* markers; **v6 plan migration numbers start after this issue** (see "Hand-off to v6" in the [v5 plan](v5-hardening-plan.md)).

## Risks

| Risk | Mitigation |
|---|---|
| Trigger changes "heartbeat" semantics the sweeper relies on | Sweeper compares `updated_at` to a cutoff; any real column change refreshes it, which is the intended heartbeat; covered by a test |
| Naming convention causes autogenerate to rename constraints | Use PG-default patterns; `alembic check` proves no drift |
| Extra migration if the audit finds gaps | Planned as `0022`; v6 migrations are numbered from `0023` either way |

## Out of scope

ANN (HNSW) indexes, table partitioning, backup tooling, changing existing constraint names.

## Implementation notes

- **`0022` was needed:** the audit found one gap, `job_posting.canonical_id` (implicit NO ACTION). It is now `ON DELETE SET NULL` (provenance pointer), in the model and in `0022_set_null_on_canonical_posting_delete`. v6 migrations start at `0023`.
- **Trigger deviation:** `set_updated_at()` keeps a value the statement sets explicitly (`IF NEW.updated_at IS NOT DISTINCT FROM OLD.updated_at THEN now()`). A plain `NEW.updated_at = now()` overrode explicit values and broke `test_sweeper_reclaims_stuck_run`, which backdates a run to test the sweeper cutoff.
- **Helper location:** `app/core/migration_helpers.py`, not `alembic/helpers.py`. The `alembic/` folder shadows nothing importable (the installed package wins), so a helper there could not be imported from migrations. The helper builds DDL with `sa.DDL` context substitution and a validated table identifier, not f-strings, so the new no-f-string-SQL test passes.
- Naming convention: PG-default patterns; `alembic check` is clean (tested). Models only gained the convention and the `SET NULL`; the trigger docstring note lives on `Base`.
- `audit_schema.py` ignores `alembic_version`. The "nullable NOT NULL candidates" check is narrowed to nullable `created_at`/`updated_at`, since a data-based check is meaningless on an empty scratch database.
- Tests: `tests/db/test_updated_at_trigger.py`, `tests/db/test_schema_standards.py` (alembic check, 0021/0022 round trip, empty audit, no f-string SQL). Sweeper and `update(Match)` already set `updated_at` explicitly, so they are not separately re-tested.
