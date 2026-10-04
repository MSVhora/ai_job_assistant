"""add_evidence_source_owner_employers

Revision ID: 0030
Revises: 0029

A GitHub organization (the owner part of `owner/repo`) can be mapped to an employer once; every
repository of that owner without a mapping of its own gets it, including repositories that are not
selected and ones found by later refreshes. The mapping is kept per source as
`{"owners": {"<owner>": <employer reference>}}`. No data migration: null means no organization
mappings.

Downgrade drops the column; the organization mappings are lost (the employers already written
onto repositories and achievements stay).
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0030"
down_revision: str | None = "0029"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    op.add_column(
        "evidence_source",
        sa.Column("owner_employers", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("evidence_source", "owner_employers")
