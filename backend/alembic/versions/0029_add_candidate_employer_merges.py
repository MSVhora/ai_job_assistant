"""add_candidate_employer_merges

Revision ID: 0029
Revises: 0028

Employers are compared as company groups. Names the user confirmed as one employer (for example
"Samsung" and "Samsung Research Institute") are kept per candidate as
`{"groups": [{"canonical": str, "members": [str, ...]}]}` and applied when companies are compared;
stored employer references are never rewritten. No data migration: null means no merges.

Downgrade drops the column; the confirmed merges are lost (employers fall back to automatic
grouping by normalized name).
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0029"
down_revision: str | None = "0028"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    op.add_column(
        "candidate",
        sa.Column("employer_merges", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("candidate", "employer_merges")
