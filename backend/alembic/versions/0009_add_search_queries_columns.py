"""add search_queries jsonb columns

Revision ID: 0009
Revises: 0008
Create Date: 2026-09-01

LLM-generated per-source search queries (owner decision 2026-09-01): a
draft-stage artifact on `resume` (generated during extraction) that is copied
into `profile.search_queries` when a profile is created, and overwritten by
POST /api/profiles/{id}/search-queries. Payload shape is stamped inside the
jsonb: {queries, generated_at, generated_by, prompt_version}.
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "resume",
        sa.Column("search_queries", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "profile",
        sa.Column("search_queries", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("profile", "search_queries")
    op.drop_column("resume", "search_queries")
