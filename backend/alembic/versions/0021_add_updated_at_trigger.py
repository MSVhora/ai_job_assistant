"""add updated_at trigger

Issue #43: `updated_at` was maintained only by the ORM `onupdate`, which does
not fire for bulk `UPDATE` statements. A `set_updated_at()` function and a
`BEFORE UPDATE ... WHEN (OLD.* IS DISTINCT FROM NEW.*)` row trigger now keep it
current on every table that has the column, for ORM and raw updates alike;
no-op updates do not touch it, and an update that sets `updated_at`
explicitly (tests backdating a run, the sweeper's `func.now()`) keeps its value.

No data change. Downgrade drops the triggers and the function (non-destructive).
"""

from app.core.migration_helpers import (
    create_updated_at_function,
    create_updated_at_trigger,
    drop_updated_at_function,
    drop_updated_at_trigger,
)

revision: str = "0021"
down_revision: str | None = "0020"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None

TABLES = ("candidate", "profile", "job_search", "match", "match_rebuild")


def upgrade() -> None:
    create_updated_at_function()
    for table in TABLES:
        create_updated_at_trigger(table)


def downgrade() -> None:
    for table in reversed(TABLES):
        drop_updated_at_trigger(table)
    drop_updated_at_function()
