"""create profile table and reparent revisions

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-01

Multi-profile support: `profile` is now the home of structured_profile (name,
provenance, one revision trail per profile); candidate is slimmed back to a
bare root entity.

DESTRUCTIVE (owner-approved 2026-09-01, test data): existing profile_revision
rows are deleted during upgrade — profile_id is NOT NULL and there is no
meaningful mapping from old candidate-level revisions to named profiles. The
downgrade reconstructs the previous schema but cannot restore lost rows.
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "profile",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("candidate_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("structured_profile", JSONB(), nullable=False),
        sa.Column("source_resume_id", sa.Uuid(), nullable=True),
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
        sa.ForeignKeyConstraint(["candidate_id"], ["candidate.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_resume_id"], ["resume.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_profile_candidate_id"), "profile", ["candidate_id"])
    op.create_index(op.f("ix_profile_source_resume_id"), "profile", ["source_resume_id"])

    op.execute("DELETE FROM profile_revision")
    op.drop_index(op.f("ix_profile_revision_candidate_id"), table_name="profile_revision")
    op.drop_constraint("profile_revision_candidate_id_fkey", "profile_revision", type_="foreignkey")
    op.drop_column("profile_revision", "candidate_id")
    op.add_column("profile_revision", sa.Column("profile_id", sa.Uuid(), nullable=False))
    op.create_foreign_key(
        "fk_profile_revision_profile_id_profile",
        "profile_revision",
        "profile",
        ["profile_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(op.f("ix_profile_revision_profile_id"), "profile_revision", ["profile_id"])

    op.drop_index(op.f("ix_candidate_source_resume_id"), table_name="candidate")
    op.drop_constraint("fk_candidate_source_resume_id_resume", "candidate", type_="foreignkey")
    op.drop_column("candidate", "structured_profile")
    op.drop_column("candidate", "source_resume_id")


def downgrade() -> None:
    op.execute("DELETE FROM profile_revision")
    op.drop_index(op.f("ix_profile_revision_profile_id"), table_name="profile_revision")
    op.drop_constraint(
        "fk_profile_revision_profile_id_profile", "profile_revision", type_="foreignkey"
    )
    op.drop_column("profile_revision", "profile_id")
    op.add_column(
        "profile_revision",
        sa.Column("candidate_id", sa.Uuid(), nullable=False),
    )
    op.create_foreign_key(
        "profile_revision_candidate_id_fkey",
        "profile_revision",
        "candidate",
        ["candidate_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(op.f("ix_profile_revision_candidate_id"), "profile_revision", ["candidate_id"])

    op.add_column("candidate", sa.Column("structured_profile", JSONB(), nullable=True))
    op.add_column("candidate", sa.Column("source_resume_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_candidate_source_resume_id_resume",
        "candidate",
        "resume",
        ["source_resume_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(op.f("ix_candidate_source_resume_id"), "candidate", ["source_resume_id"])

    op.drop_index(op.f("ix_profile_source_resume_id"), table_name="profile")
    op.drop_index(op.f("ix_profile_candidate_id"), table_name="profile")
    op.drop_table("profile")
