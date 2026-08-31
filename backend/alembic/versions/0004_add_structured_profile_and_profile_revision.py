"""add structured profile and profile revision

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-31

structured_profile holds the reviewed, human-approved profile (including the
embedded preferences block). profile_revision is the audit trail of AI vs human
field changes; its downgrade is destructive — recorded corrections are not
recoverable, and dropping the saved profile discards reviewed data.
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "profile_revision",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("candidate_id", sa.Uuid(), nullable=False),
        sa.Column(
            "source",
            sa.Enum(
                "ai_extraction",
                "manual_edit",
                "gap_fill",
                "reupload_merge",
                name="profile_revision_source",
            ),
            nullable=False,
        ),
        sa.Column("diff", JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidate.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_profile_revision_candidate_id"), "profile_revision", ["candidate_id"])
    op.add_column("candidate", sa.Column("structured_profile", JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("candidate", "structured_profile")
    op.drop_index(op.f("ix_profile_revision_candidate_id"), table_name="profile_revision")
    op.drop_table("profile_revision")
    op.execute("DROP TYPE profile_revision_source")
