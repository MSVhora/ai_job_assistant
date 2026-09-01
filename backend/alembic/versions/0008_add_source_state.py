"""add source_state table

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-01

Issue #8: persists the per-source disclosure acknowledgment so a scraping
source stays enabled across restarts. `acknowledged_at` is null until the
disclosure modal is confirmed via POST /api/sources/{name}/enable.
"""

import sqlalchemy as sa

from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "source_state",
        sa.Column("source_name", sa.String(length=50), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("source_name"),
    )


def downgrade() -> None:
    op.drop_table("source_state")
