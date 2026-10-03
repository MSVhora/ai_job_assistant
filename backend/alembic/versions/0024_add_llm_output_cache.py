"""add_llm_output_cache

Revision ID: 0024
Revises: 0023

v6 #49: `llm_output_cache`, a content-addressed cache of structured LLM outputs
(key = SHA-256 of task, model, prompt version and redacted inputs). It is not
candidate-owned and has no `updated_at` (rows are write-once; a bad row is
overwritten). The `created_at` index supports a future prune.

Downgrade drops the table; cached outputs are simply regenerated on demand.
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0024"
down_revision: str | None = "0023"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    op.create_table(
        "llm_output_cache",
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("task", sa.String(length=20), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("prompt_version", sa.Text(), nullable=False),
        sa.Column("output", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False),
        sa.Column("completion_tokens", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("key", name=op.f("llm_output_cache_pkey")),
    )
    op.create_index(
        "ix_llm_output_cache_created_at", "llm_output_cache", ["created_at"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_llm_output_cache_created_at", table_name="llm_output_cache")
    op.drop_table("llm_output_cache")
