"""add profile preferences jsonb column

Revision ID: 0012
Revises: 0011
Create Date: 2026-09-03

Priority-weight slider (issue #11): lands the `preferences` jsonb column
deferred from plan §4 (issue #4 locked decision). This is the dashboard *view*
preference — currently `{priority: float 0-1}` weighting role-fit vs
company-fit at match read time — distinct from the resume-derived preferences
inside `structured_profile`. A slider update is deliberately not
revision-audited, does not refresh the embedding, and does not re-score
matches.

No backfill: absent column value means "use the server default"
(match_weight_role_fit / (match_weight_role_fit + match_weight_company_fit)).
Downgrade drops the column along with any stored slider positions.
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "profile",
        sa.Column("preferences", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("profile", "preferences")
