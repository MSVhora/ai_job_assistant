# Postgres & Migration Standards

Applies to all schema and data-access work. Alembic + SQLAlchemy 2.0 async.

## The migration rule (non-negotiable)

1. **Every change to tables, columns, indexes, enums, triggers, or extensions goes through a new Alembic migration.** No manual `ALTER`/`CREATE` against any database, ever — including "just to test".
2. **Models are the source of truth.** Edit `app/models/` first, then autogenerate, then review the generated migration before applying.
3. **Never edit a migration that has been committed or applied anywhere.** Fix forward with a new migration.
4. The migration file ships in the same PR/commit as its model change.

## Workflow

```bash
# in backend/
alembic revision --autogenerate -m "descriptive_snake_case_message"
# READ the generated file — autogenerate reliably misses:
#   - server_default changes
#   - enum value changes (it may drop/recreate)
#   - column renames (emits drop + add instead)
#   - triggers, functions, partial-index predicates, CHECK details
#   - any data transformation
alembic upgrade head
```

- Migration messages: `add_profile_revision_table`, `add_match_final_score_column`, `create_vector_extension`.
- Every migration has a working `downgrade()`; if downgrade is intentionally destructive (e.g., column drop loses data), say so in a docstring. `test_migrations.py` runs up/down against a scratch database.
- **Data migrations are separate from schema migrations** and use bulk SQL/`exec_driver_sql`, not row-by-row ORM updates.
- Recommended gate: lint migrations for unsafe operations (for example with `squawk`) before merging.

## Schema conventions

- **PKs**: UUID (`uuid4`), generated client-side or via `server_default=text("gen_random_uuid()")`.
- **Timestamps**: `timestamptz` only; `created_at` with server default `now()`.
- **`updated_at`**: maintained by a **database trigger** (`set_updated_at()` as `BEFORE UPDATE ... WHEN (OLD IS DISTINCT FROM NEW)`; it keeps a value the statement sets explicitly), created in the migration of every table that has the column with `create_updated_at_trigger(table)` / `drop_updated_at_trigger(table)` from `app.core.migration_helpers`. ORM-side `onupdate` does not fire for bulk `UPDATE` statements, so it is never the only mechanism.
- **JSONB** for flexible payloads (`structured_profile`, `preferences`, `raw_payload`). Don't bury queryable relationships in JSONB — if we filter/group by it, it becomes a column or table.
- **Indexes**: every FK column indexed; unique constraint on `(source, external_id)` for `job_posting` dedupe; index `match(profile_id, final_score DESC)` for the dashboard query (profiles are the matching unit — owner decision 2026-09-02). Partial indexes are fine and preferred for status-scoped guards (`uq_job_search_active_run`).
- **Naming**: `Base.metadata` carries a naming convention that mirrors PostgreSQL's default names, so unnamed constraints are predictable; name every constraint and index explicitly with a prefix — `uq_`, `ix_`, `fk_`, `ck_` — so migrations and autogenerate stay stable.
- **ON DELETE policy**: `CASCADE` for rows owned by their parent (matches, search results, rebuild runs); `RESTRICT` for identity and audit rows (`profile_revision`, candidate links); `SET NULL` for provenance pointers (`profile.source_resume_id`). State the choice in the model when it is not the default.
- **CHECK constraints** for bounded or enumerated scalars that are not native enums (for example a 1–5 score). Application validation is not a substitute.
- **pgvector**: extension created in the initial migration (`CREATE EXTENSION IF NOT EXISTS vector`); `Vector(dim)` dimension pinned to the embedding model (Gemini `gemini-embedding-001` with `EMBEDDING_DIMENSIONS=768`; native output is 3072, truncated via the API's `dimensions` param) and documented in the migration message; changing embedding models = new column + backfill migration, never silent dimension change. No ANN index exists at current single-user scale (sequential scan is fast enough); when one is added it is HNSW with `vector_cosine_ops`, created in its own migration, and `CREATE INDEX CONCURRENTLY` inside an `autocommit_block()` if the table is large.
- **Enums**: named native PG enums via `sa.Enum(..., name="job_type")`. Adding a value is `ALTER TYPE ... ADD VALUE` and must run inside `op.get_context().autocommit_block()`; the new value is not usable in the same transaction. Removing or renaming a value means recreating the type (and says so in the migration docstring).
- **Extensions** (`vector`, `pg_trgm`) are created by migrations, never by hand.
- **Files/uploads**: DB stores path/metadata only; blobs on disk/object storage with UUID filenames.

## Data access rules

- SQLAlchemy 2.0 style only: `select()`, `Mapped[]`, `mapped_column()`. No legacy `Query` API.
- **Parameterized queries only** — never f-string/`%`-format SQL, ever.
- Sessions come from the app dependency; commit/rollback handled per request; background tasks open fresh sessions from `session_factory` and never hold one across awaits that outlive their work.
- Bulk updates are explicit `update()` statements and rely on the `updated_at` trigger, not on ORM hooks.
- Connection pool sizing sensible for single-user self-host (default is fine; don't multiply engines).
- No secrets, API keys, or real resume content hardcoded in migrations or seed scripts.

## Operations

- The Compose `pgdata` volume is the only copy of user data: document and test a `pg_dump` backup/restore path before any destructive migration.
- Run migrations and tests only against disposable databases; the test suite migrates up at session start and downgrades at the end, so it must never point at a dev database.
