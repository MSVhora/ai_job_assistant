"""add_posting_expiry_columns

Expiry data model for the v3 freshness policy (issue #26, plan §2 D4):
`job_posting.expires_at` (source-reported, LinkedIn `expireAt`) and
`job_posting.is_closed` (future seam — no producing source today).

A D4 read-side filter built on these columns excludes closed/expired
postings from matches and search results; postings with no expiry go stale
after the `STALE_POSTING_DAYS` grace window (default 45) since posting.

No backfill: existing rows keep `expires_at = NULL` until refetched; the
grace window handles their staleness.

Destructive downgrade: dropping the columns loses any recorded expiry
information (raw payloads are retained).
"""

import sqlalchemy as sa

from alembic import op

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    op.add_column(
        "job_posting",
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "job_posting",
        sa.Column("is_closed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )


def downgrade() -> None:
    op.drop_column("job_posting", "is_closed")
    op.drop_column("job_posting", "expires_at")
