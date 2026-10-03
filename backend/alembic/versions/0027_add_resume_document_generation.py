"""add_resume_document_generation

Revision ID: 0027
Revises: 0026

v6 #55: `resume_document.generation` (JSONB, default `{}`) holds what a content run produced
besides the content itself: the ranked candidate pool, omitted overlapping roles, the gaps
report, the JD analysis, warnings and usage. No data migration: existing rows keep `{}`.

Downgrade drops the column; the stored generation metadata is lost (content is untouched).
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0027"
down_revision: str | None = "0026"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    op.add_column(
        "resume_document",
        sa.Column(
            "generation",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("resume_document", "generation")
