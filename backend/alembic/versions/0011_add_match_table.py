"""add match table

Revision ID: 0011
Revises: 0010
Create Date: 2026-09-03

Matching pipeline (issue #10): one `match` row per (profile, job_posting) pair.

Keyed on `profile_id` — profiles are the matching unit (owner decision
2026-09-02), both embeddings are per-profile, and `candidate_id` stays
reachable via `profile.candidate_id`. Deleting a profile or posting cascades:
matches without either side are meaningless.

- `vector_score`: pre-weight cosine similarity, clamp(1 - cosine_distance, 0, 1).
- `role_fit` / `company_fit`: LLM re-rank sub-scores (0-10 scale), null when the
  posting was not re-ranked. Stored so the priority slider (#11) can re-weight
  without re-calling the LLM.
- `final_score`: post-weight score; blended for re-ranked rows, plain
  vector_score otherwise. Indexed (profile_id, final_score DESC) for the
  dashboard query.
- `rationale`: "why this matches", top N only (cost control), null otherwise.

`job_search.matching` records the per-run MatchingOutcome (status, counts,
rerank token usage) so re-rank cost is visible in run results, not just logs.
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "match",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("job_posting_id", sa.Uuid(), nullable=False),
        sa.Column("vector_score", sa.Float(), nullable=False),
        sa.Column("role_fit", sa.Float(), nullable=True),
        sa.Column("company_fit", sa.Float(), nullable=True),
        sa.Column("final_score", sa.Float(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["profile_id"], ["profile.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_posting_id"], ["job_posting.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("profile_id", "job_posting_id", name="uq_match_profile_job_posting"),
    )
    op.create_index(op.f("ix_match_profile_id"), "match", ["profile_id"])
    op.create_index(op.f("ix_match_job_posting_id"), "match", ["job_posting_id"])
    op.create_index(
        "ix_match_profile_final_score",
        "match",
        ["profile_id", sa.literal_column("final_score DESC")],
    )
    op.add_column(
        "job_search",
        sa.Column("matching", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("job_search", "matching")
    op.drop_index("ix_match_profile_final_score", table_name="match")
    op.drop_index(op.f("ix_match_job_posting_id"), table_name="match")
    op.drop_index(op.f("ix_match_profile_id"), table_name="match")
    op.drop_table("match")
