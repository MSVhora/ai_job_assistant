"""add posting canonical dedupe columns + pg_trgm

Issue #38: cross-source posting dedupe (canonical grouping). `job_posting`
gains a self-FK `canonical_id` (NULL = own canonical; a duplicate points at
its canonical), a `source_urls` JSONB merge record, and a `country` column
(the dedupe grouping key's "location bucket" — the run's resolved 2-letter
country, refreshed on re-fetch). pg_trgm + a GIN trgm index on `title` serve
the similarity candidate lookup.

No data migration / backfill: existing duplicate pairs collapse
opportunistically the next time a source re-finds one of them. Downgrade is
destructive for the merge record (`source_urls` is dropped) and re-splits
dashboard entries — re-derivable by re-running searches.
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "0019"
down_revision: str | None = "0018"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.add_column("job_posting", sa.Column("country", sa.String(length=2), nullable=True))
    op.add_column(
        "job_posting",
        sa.Column(
            "canonical_id",
            sa.UUID(),
            sa.ForeignKey("job_posting.id", use_alter=True, name="fk_job_posting_canonical_id"),
            nullable=True,
        ),
    )
    op.create_index("ix_job_posting_canonical_id", "job_posting", ["canonical_id"])
    op.add_column("job_posting", sa.Column("source_urls", JSONB(), nullable=True))
    op.execute(
        "CREATE INDEX ix_job_posting_title_trgm ON job_posting USING gin (title gin_trgm_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_job_posting_title_trgm")
    op.drop_column("job_posting", "source_urls")
    op.drop_index("ix_job_posting_canonical_id", table_name="job_posting")
    op.drop_column("job_posting", "canonical_id")
    op.drop_column("job_posting", "country")
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
