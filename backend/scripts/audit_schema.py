"""Read-only schema audit against a migrated database (issue #43).

    python scripts/audit_schema.py

Prints one section per check and exits non-zero when any finding remains. Run it
against a migrated scratch database, never to change anything: it only reads
`pg_catalog`.
"""

import asyncio
import re
import sys

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.core.db import engine

ALLOWED_NAME = re.compile(r"^(ix_|uq_|fk_|ck_|pk_|trg_)|(_pkey|_fkey|_key|_check|_idx)$")
IGNORED_TABLES = ("alembic_version",)

UNINDEXED_FKS = """
SELECT c.conrelid::regclass::text || '.' || a.attname AS finding
FROM pg_constraint c
JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = c.conkey[1]
WHERE c.contype = 'f' AND c.connamespace = 'public'::regnamespace
  AND NOT EXISTS (
    SELECT 1 FROM pg_index i
    WHERE i.indrelid = c.conrelid AND i.indkey[0] = c.conkey[1]
  )
ORDER BY 1
"""

FKS_WITHOUT_ON_DELETE = """
SELECT c.conrelid::regclass::text || '.' || c.conname AS finding
FROM pg_constraint c
WHERE c.contype = 'f' AND c.connamespace = 'public'::regnamespace AND c.confdeltype = 'a'
ORDER BY 1
"""

NULLABLE_TIMESTAMPS = """
SELECT table_name || '.' || column_name AS finding
FROM information_schema.columns
WHERE table_schema = 'public' AND table_name <> 'alembic_version'
  AND column_name IN ('created_at', 'updated_at') AND is_nullable = 'YES'
ORDER BY 1
"""

CONSTRAINT_AND_INDEX_NAMES = """
SELECT conrelid::regclass::text || '.' || conname AS finding, conname AS name
FROM pg_constraint WHERE connamespace = 'public'::regnamespace
UNION ALL
SELECT tablename || '.' || indexname, indexname FROM pg_indexes WHERE schemaname = 'public'
ORDER BY 1
"""


async def audit(conn: AsyncConnection) -> dict[str, list[str]]:
    async def column(query: str) -> list[str]:
        return [row[0] for row in await conn.execute(text(query))]

    names = (await conn.execute(text(CONSTRAINT_AND_INDEX_NAMES))).all()
    return {
        "fk columns without an index": await column(UNINDEXED_FKS),
        "foreign keys without an explicit ON DELETE": await column(FKS_WITHOUT_ON_DELETE),
        "nullable created_at/updated_at": await column(NULLABLE_TIMESTAMPS),
        "constraints/indexes with non-conventional names": [
            finding
            for finding, name in names
            if not finding.startswith(IGNORED_TABLES) and not ALLOWED_NAME.search(name)
        ],
    }


async def main() -> int:
    async with engine.connect() as conn:
        findings = await audit(conn)
    await engine.dispose()
    for title, items in findings.items():
        print(f"{title}: {len(items)}")
        for item in items:
            print(f"  {item}")
    return 1 if any(findings.values()) else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
