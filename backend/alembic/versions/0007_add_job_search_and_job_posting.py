"""add job_search and job_posting tables

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-01

Job discovery (issue #7): `job_search` tracks a background ingestion run
(status + per-source outcomes); `job_posting` stores normalized postings with
(source, external_id) dedupe, raw_payload retained for debugging/re-mapping.
Embedding vector column is intentionally deferred to the embeddings issue (#9),
where the dimension gets pinned to the chosen embedding model.
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | None = None
depends_on: str | None = None

JOB_SEARCH_STATUS = sa.Enum(
    "pending",
    "running",
    "succeeded",
    "partial",
    "failed",
    name="job_search_status",
)
JOB_TYPE = sa.Enum(
    "full_time",
    "part_time",
    "contract",
    "internship",
    "temporary",
    name="job_type",
)
REMOTE_TYPE = sa.Enum("remote", "hybrid", "on_site", name="remote_type")


def upgrade() -> None:
    op.create_table(
        "job_search",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("status", JOB_SEARCH_STATUS, nullable=False),
        sa.Column("query", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("results", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
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
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "job_posting",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("company", sa.String(length=255), nullable=True),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("job_type", JOB_TYPE, nullable=True),
        sa.Column("remote_type", REMOTE_TYPE, nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("salary_min", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("salary_max", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("job_search_id", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["job_search_id"], ["job_search.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source", "external_id", name="uq_job_posting_source_external_id"),
    )
    op.create_index(op.f("ix_job_posting_job_search_id"), "job_posting", ["job_search_id"])
    op.create_index(op.f("ix_job_posting_posted_at"), "job_posting", ["posted_at"])


def downgrade() -> None:
    op.drop_index(op.f("ix_job_posting_posted_at"), table_name="job_posting")
    op.drop_index(op.f("ix_job_posting_job_search_id"), table_name="job_posting")
    op.drop_table("job_posting")
    op.drop_table("job_search")
    REMOTE_TYPE.drop(op.get_bind(), checkfirst=True)
    JOB_TYPE.drop(op.get_bind(), checkfirst=True)
    JOB_SEARCH_STATUS.drop(op.get_bind(), checkfirst=True)
