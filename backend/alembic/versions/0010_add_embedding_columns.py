"""add embedding columns

Revision ID: 0010
Revises: 0009
Create Date: 2026-09-02

Vector columns for issue #9 (embeddings + hard filters):

- `job_posting.embedding`: computed on ingest (batch per source run).
- `profile.embedding`: refreshed whenever structured_profile changes
  (create, manual save, re-upload merge, gap-fill apply).

The dimension is pinned to 768, matching the configured embedding model
Gemini `text-embedding-004`. Changing embedding models must NEVER alter the
dimension silently: add a new nullable vector column with the new dim, run a
backfill migration, then drop the old column. Both columns are nullable:
postings persist even when the embedding call fails, and are matched by hard
filters alone until re-embedded.

No ANN index (HNSW/ivfflat) in v1: single-user scale (a few thousand postings
at most) makes sequential scans fast enough; revisit when data grows.
"""

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column("job_posting", sa.Column("embedding", Vector(768), nullable=True))
    op.add_column("profile", sa.Column("embedding", Vector(768), nullable=True))


def downgrade() -> None:
    op.drop_column("profile", "embedding")
    op.drop_column("job_posting", "embedding")
