"""add resume draft profile

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-31

Draft profile is a parse artifact (reproducible by re-running extraction);
downgrade discards it.
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column("resume", sa.Column("draft_profile", JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("resume", "draft_profile")
