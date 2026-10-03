"""add_resume_document

Revision ID: 0026
Revises: 0025

v6 #54: `resume_document` (structured resume content with per-bullet provenance, layout,
conflicts and comments as JSONB; CHECKs bound `page_target` to 1-4 and `jd_weight` to
0-0.5; `profile_id` CASCADE, `match_id` SET NULL, `candidate_id` RESTRICT) and
`resume_document_revision` (content snapshots, FK CASCADE). No existing table is changed.

Downgrade drops the two tables and the `resume_document_status` enum; saved resume
documents and their revisions are lost.
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from app.core.migration_helpers import create_updated_at_trigger, drop_updated_at_trigger

revision: str = "0026"
down_revision: str | None = "0025"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None

STATUSES = ("draft", "final")


def _uuid_pk() -> sa.Column[sa.Uuid]:
    return sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False)


def _jsonb(name: str, default: str) -> sa.Column[postgresql.JSONB]:
    return sa.Column(
        name,
        postgresql.JSONB(astext_type=sa.Text()),
        server_default=sa.text(default),
        nullable=False,
    )


def _created() -> sa.Column[sa.DateTime]:
    return sa.Column(
        "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
    )


def upgrade() -> None:
    op.create_table(
        "resume_document",
        _uuid_pk(),
        sa.Column("candidate_id", sa.Uuid(), nullable=False),
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("match_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("page_target", sa.SmallInteger(), server_default="1", nullable=False),
        sa.Column("jd_weight", sa.Float(), server_default="0", nullable=False),
        sa.Column("template", sa.String(length=50), server_default="classic", nullable=False),
        sa.Column("job_description", sa.Text(), nullable=True),
        sa.Column("jd_hash", sa.String(length=64), nullable=True),
        _jsonb("content", "'{}'::jsonb"),
        _jsonb("layout", "'{}'::jsonb"),
        _jsonb("conflicts", "'[]'::jsonb"),
        _jsonb("comments", "'[]'::jsonb"),
        sa.Column(
            "status",
            sa.Enum(*STATUSES, name="resume_document_status"),
            server_default="draft",
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        _created(),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "page_target BETWEEN 1 AND 4", name=op.f("resume_document_page_target_range_check")
        ),
        sa.CheckConstraint(
            "jd_weight BETWEEN 0 AND 0.5", name=op.f("resume_document_jd_weight_range_check")
        ),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["candidate.id"],
            name=op.f("resume_document_candidate_id_fkey"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["profile_id"],
            ["profile.id"],
            name=op.f("resume_document_profile_id_fkey"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["match_id"],
            ["match.id"],
            name=op.f("resume_document_match_id_fkey"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("resume_document_pkey")),
    )
    op.create_index(op.f("ix_resume_document_candidate_id"), "resume_document", ["candidate_id"])
    op.create_index(op.f("ix_resume_document_profile_id"), "resume_document", ["profile_id"])
    op.create_index(op.f("ix_resume_document_match_id"), "resume_document", ["match_id"])

    op.create_table(
        "resume_document_revision",
        _uuid_pk(),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        _jsonb("content", "'{}'::jsonb"),
        sa.Column("source", sa.String(length=30), nullable=False),
        _created(),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["resume_document.id"],
            name=op.f("resume_document_revision_document_id_fkey"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("resume_document_revision_pkey")),
    )
    op.create_index(
        op.f("ix_resume_document_revision_document_id"),
        "resume_document_revision",
        ["document_id"],
    )

    create_updated_at_trigger("resume_document")


def downgrade() -> None:
    drop_updated_at_trigger("resume_document")
    op.drop_table("resume_document_revision")
    op.drop_table("resume_document")
    op.execute(sa.text("DROP TYPE IF EXISTS resume_document_status"))
