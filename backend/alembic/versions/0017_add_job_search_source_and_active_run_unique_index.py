"""add job_search.source and the active-run partial unique index

Issue #36: guards duplicate concurrent runs of the same (profile, source)
via a partial unique index over non-terminal runs. `source` was previously
only readable from the `query` JSONB echo (`resolved request dump`);
materializing it as a column makes the enforcement index possible.

Backfill: rows from the one-source era carry `source` in `query`; older rows
carry a `sources` (list) — the backfill reads the stored `source`, else the
first element of `sources`. Rows with neither (a handful of terminal,
pre-source-field tests/current dev rows) are deleted — destructive for
those rows only; terminal history without a source is unusable. The guard
then verifies the table, and downgrade drops the column — losing it only
costs the guard; the `query` echo still names the source.
"""

import sqlalchemy as sa

from alembic import op

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None

WHERE_CLAUSE = "status IN ('pending', 'running')"


def upgrade() -> None:
    op.add_column("job_search", sa.Column("source", sa.String(length=64), nullable=True))
    op.execute(
        "UPDATE job_search SET source = "
        "coalesce(query->>'source', query->'sources'->>0) "
        "WHERE source IS NULL"
    )
    op.execute("DELETE FROM job_search WHERE source IS NULL")
    bind = op.get_bind()
    remaining = bind.execute(
        sa.text("SELECT count(*) FROM job_search WHERE source IS NULL")
    ).scalar_one()
    if remaining:
        raise RuntimeError(f"{remaining} job_search row(s) could not be backfilled")
    op.alter_column("job_search", "source", existing_type=sa.String(length=64), nullable=False)
    op.create_index(op.f("ix_job_search_source"), "job_search", ["source"], unique=False)
    op.create_index(
        "uq_job_search_active_run",
        "job_search",
        ["profile_id", "source"],
        unique=True,
        postgresql_where=sa.text(WHERE_CLAUSE),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_job_search_active_run",
        table_name="job_search",
        postgresql_where=sa.text(WHERE_CLAUSE),
    )
    op.drop_index(op.f("ix_job_search_source"), table_name="job_search")
    op.drop_column("job_search", "source")
