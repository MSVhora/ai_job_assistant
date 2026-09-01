"""add candidate source resume provenance

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-01

source_resume_id records which uploaded resume the saved profile was last
derived from (provenance). Nullable — unset until the first profile save from
a draft; SET NULL if the source resume row ever disappears.
"""

import sqlalchemy as sa

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column("candidate", sa.Column("source_resume_id", sa.Uuid(), nullable=True))
    op.create_index(op.f("ix_candidate_source_resume_id"), "candidate", ["source_resume_id"])
    op.create_foreign_key(
        "fk_candidate_source_resume_id_resume",
        "candidate",
        "resume",
        ["source_resume_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_candidate_source_resume_id_resume", "candidate", type_="foreignkey")
    op.drop_index(op.f("ix_candidate_source_resume_id"), table_name="candidate")
    op.drop_column("candidate", "source_resume_id")
