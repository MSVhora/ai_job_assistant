"""add_match_rebuild_run_table

Revision ID: 0014
Revises: 0013
Create Date: 2026-09-14

Run bookkeeping for the explicit per-profile match rebuild (issue #25, v3 plan
§2 D7): `POST /api/profiles/{id}/rescore` runs in the background, the run
banner polls the latest `match_rebuild` row, which carries `corpus_count` =
postings found by the profile's own searches and `scored_count` = those with
embeddings. Nothing pre-existing is deleted here — cleanup of out-of-corpus
matches happens only when the user explicitly rebuilds (⚠ owner sign-off:
upgrade keeps all currently stored matches; per D7 no auto-deletion).

Downgrade drops the run rows and table (history of rebuild runs is lost;
stored matches are untouched).
"""

import sqlalchemy as sa

from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    op.create_table(
        "match_rebuild",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "running",
                "succeeded",
                "failed",
                name="match_rebuild_status",
            ),
            nullable=False,
        ),
        sa.Column("corpus_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("scored_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("warning", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["profile_id"],
            ["profile.id"],
            ondelete="CASCADE",
            name="fk_match_rebuild_profile_id_profile",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_match_rebuild_profile_id"), "match_rebuild", ["profile_id"])
    op.create_index(
        "ix_match_rebuild_profile_created", "match_rebuild", ["profile_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_match_rebuild_profile_created", table_name="match_rebuild")
    op.drop_index(op.f("ix_match_rebuild_profile_id"), table_name="match_rebuild")
    op.drop_table("match_rebuild")
    op.execute(sa.text("DROP TYPE IF EXISTS match_rebuild_status"))
