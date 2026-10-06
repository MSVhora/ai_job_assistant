import re

import sqlalchemy as sa

from alembic import op

_IDENTIFIER = re.compile(r"^[a-z_][a-z0-9_]*$")


def _ddl(statement: str, table: str | None = None) -> None:
    if table is not None and not _IDENTIFIER.fullmatch(table):
        msg = f"not a plain table identifier: {table!r}"
        raise ValueError(msg)
    op.execute(sa.DDL(statement, context={"table": table}))


def create_updated_at_function() -> None:
    _ddl(
        """
        CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger AS $$
        BEGIN
            IF NEW.updated_at IS NOT DISTINCT FROM OLD.updated_at THEN
                NEW.updated_at = now();
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )


def drop_updated_at_function() -> None:
    _ddl("DROP FUNCTION IF EXISTS set_updated_at()")


def create_updated_at_trigger(table: str) -> None:
    _ddl(
        """
        CREATE TRIGGER trg_%(table)s_set_updated_at
        BEFORE UPDATE ON "%(table)s"
        FOR EACH ROW
        WHEN (OLD.* IS DISTINCT FROM NEW.*)
        EXECUTE FUNCTION set_updated_at()
        """,
        table,
    )


def drop_updated_at_trigger(table: str) -> None:
    _ddl('DROP TRIGGER IF EXISTS trg_%(table)s_set_updated_at ON "%(table)s"', table)
