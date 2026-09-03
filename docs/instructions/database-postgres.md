# Postgres & Migration Standards

Applies to all schema and data-access work. Alembic + SQLAlchemy 2.0 async.

## The migration rule (non-negotiable)

1. **Every change to tables, columns, indexes, enums, or extensions goes through a new Alembic migration.** No manual `ALTER`/`CREATE` against any database, ever — including "just to test".
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
#   - any data transformation
alembic upgrade head
```

- Migration messages: `add_profile_revision_table`, `add_match_final_score_column`, `create_vector_extension`.
- Every migration has a working `downgrade()`; if downgrade is intentionally destructive (e.g., column drop loses data), say so in a docstring.
- **Data migrations are separate from schema migrations** and use bulk SQL/`exec_driver_sql`, not row-by-row ORM updates.

## Schema conventions

- **PKs**: UUID (`uuid4`), generated client-side or via `server_default=text("gen_random_uuid()")`.
- **Timestamps**: `timestamptz` only; `created_at` with server default `now()`; `updated_at` via `onupdate` + trigger or ORM hook.
- **JSONB** for flexible payloads (`structured_profile`, `preferences`, `raw_payload`). Don't bury queryable relationships in JSONB — if we filter/group by it, it becomes a column or table.
- **Indexes**: every FK column indexed; unique constraint on `(source, external_id)` for `job_posting` dedupe; index `match(profile_id, final_score DESC)` for the dashboard query (profiles are the matching unit — owner decision 2026-09-02).
- **pgvector**: extension created in the initial migration (`CREATE EXTENSION IF NOT EXISTS vector`); `Vector(dim)` dimension pinned to the embedding model (Gemini `gemini-embedding-001` with `EMBEDDING_DIMENSIONS=768`; native output is 3072, truncated via the API's `dimensions` param) and documented in the migration message; changing embedding models = new column + backfill migration, never silent dimension change.
- **Enums**: named native PG enums via `sa.Enum(..., name="job_type")` so values can be `ALTER TYPE ... ADD VALUE` in later migrations.
- **Files/uploads**: DB stores path/metadata only; blobs on disk/object storage with UUID filenames.

## Data access rules

- SQLAlchemy 2.0 style only: `select()`, `Mapped[]`, `mapped_column()`. No legacy `Query` API.
- **Parameterized queries only** — never f-string/`%`-format SQL, ever.
- Sessions come from the app dependency; commit/rollback handled per request; no long-lived sessions in background tasks (open fresh ones).
- Connection pool sizing sensible for single-user self-host (default is fine; don't multiply engines).
- No secrets, API keys, or real resume content hardcoded in migrations or seed scripts.
