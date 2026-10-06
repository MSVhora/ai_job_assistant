"""add profile.queries_input_hash

Content-hash cache for stored search-query specs (issue #31): generation fires
only when the SHA-256 of the prompt-consumed inputs differs from the stored
value. Nullable — profiles without a stored hash are treated as "stale" and
regenerate on the next save/chat completion; no data migration needed.

Downgrade drops the column (nothing else stores the hash; losing it only means
the next save regenerates queries once).
"""

import sqlalchemy as sa

from alembic import op

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    op.add_column("profile", sa.Column("queries_input_hash", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("profile", "queries_input_hash")
