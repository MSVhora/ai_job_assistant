"""add_achievements

Revision ID: 0025
Revises: 0024

v6 #52: `achievement` (STAR text, metrics/skills JSONB, a `vector(768)` embedding with the
dimension pinned to gemini-embedding-001 and no ANN index, `review_flags`,
`evidence_stale_at`), `achievement_evidence` (evidence links; the item FK is RESTRICT so
evidence under an achievement is never silently deleted), `achievement_revision` (audit
trail, FK RESTRICT) and `achievement_extraction_run` (progress, estimate, usage; the partial
unique index `uq_achievement_extraction_active_run` admits one pending/running run per
candidate). The run table reuses the existing `sync_status` enum. No existing table or enum
is changed.

Downgrade drops the new tables and their three enums; extracted achievements are lost.
"""

import pgvector.sqlalchemy
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from app.core.migration_helpers import create_updated_at_trigger, drop_updated_at_trigger

revision: str = "0025"
down_revision: str | None = "0024"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None

TRIGGER_TABLES = ("achievement", "achievement_extraction_run")
ACTIVE_RUN_WHERE = "status IN ('pending','running')"
STATUSES = ("draft", "approved", "rejected", "archived")
ORIGINS = ("ai_extracted", "user_created", "merged")
REVISION_SOURCES = (
    "ai_extraction",
    "manual_edit",
    "merge",
    "split",
    "metric_confirmation",
    "status_change",
)
SYNC_STATUSES = ("pending", "running", "paused", "succeeded", "failed")


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


def _updated() -> sa.Column[sa.DateTime]:
    return sa.Column(
        "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
    )


def upgrade() -> None:
    op.create_table(
        "achievement",
        _uuid_pk(),
        sa.Column("candidate_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(*STATUSES, name="achievement_status"),
            server_default="draft",
            nullable=False,
        ),
        sa.Column(
            "origin",
            sa.Enum(*ORIGINS, name="achievement_origin"),
            server_default="ai_extracted",
            nullable=False,
        ),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("situation", sa.Text(), nullable=True),
        sa.Column("task", sa.Text(), nullable=True),
        sa.Column("action", sa.Text(), nullable=True),
        sa.Column("result", sa.Text(), nullable=True),
        _jsonb("metrics", "'[]'::jsonb"),
        _jsonb("skills", "'[]'::jsonb"),
        sa.Column("impact_type", sa.String(length=30), nullable=False),
        sa.Column("difficulty", sa.SmallInteger(), nullable=False),
        sa.Column("project_key", sa.String(), nullable=True),
        sa.Column("employer_ref", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("time_start", sa.Date(), nullable=True),
        sa.Column("time_end", sa.Date(), nullable=True),
        sa.Column("embedding", pgvector.sqlalchemy.Vector(dim=768), nullable=True),
        sa.Column("prompt_version", sa.String(), nullable=True),
        sa.Column("source_chunk_hash", sa.String(length=64), nullable=True),
        sa.Column("edited_by_user", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "derived_from_private", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        _jsonb("review_flags", "'[]'::jsonb"),
        sa.Column("evidence_stale_at", sa.DateTime(timezone=True), nullable=True),
        _created(),
        _updated(),
        sa.CheckConstraint(
            "difficulty BETWEEN 1 AND 5", name=op.f("achievement_difficulty_range_check")
        ),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["candidate.id"],
            name=op.f("achievement_candidate_id_fkey"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("achievement_pkey")),
    )
    op.create_index(op.f("ix_achievement_candidate_id"), "achievement", ["candidate_id"])
    op.create_index("ix_achievement_candidate_status", "achievement", ["candidate_id", "status"])

    op.create_table(
        "achievement_extraction_run",
        _uuid_pk(),
        sa.Column("candidate_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(*SYNC_STATUSES, name="sync_status", create_type=False),
            server_default="pending",
            nullable=False,
        ),
        _jsonb("estimate", "'{}'::jsonb"),
        _jsonb("progress", "'{}'::jsonb"),
        _jsonb("usage", "'{}'::jsonb"),
        sa.Column("error", sa.Text(), nullable=True),
        _created(),
        _updated(),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["candidate.id"],
            name=op.f("achievement_extraction_run_candidate_id_fkey"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("achievement_extraction_run_pkey")),
    )
    op.create_index(
        op.f("ix_achievement_extraction_run_candidate_id"),
        "achievement_extraction_run",
        ["candidate_id"],
    )
    op.create_index(
        "uq_achievement_extraction_active_run",
        "achievement_extraction_run",
        ["candidate_id"],
        unique=True,
        postgresql_where=sa.text(ACTIVE_RUN_WHERE),
    )

    op.create_table(
        "achievement_revision",
        _uuid_pk(),
        sa.Column("achievement_id", sa.Uuid(), nullable=False),
        sa.Column(
            "source", sa.Enum(*REVISION_SOURCES, name="achievement_revision_source"), nullable=False
        ),
        _jsonb("diff", "'{}'::jsonb"),
        _created(),
        sa.ForeignKeyConstraint(
            ["achievement_id"],
            ["achievement.id"],
            name=op.f("achievement_revision_achievement_id_fkey"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("achievement_revision_pkey")),
    )
    op.create_index(
        op.f("ix_achievement_revision_achievement_id"), "achievement_revision", ["achievement_id"]
    )

    op.create_table(
        "achievement_evidence",
        _uuid_pk(),
        sa.Column("achievement_id", sa.Uuid(), nullable=False),
        sa.Column("item_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("quote", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "role IN ('primary', 'supporting')", name=op.f("achievement_evidence_role_values_check")
        ),
        sa.ForeignKeyConstraint(
            ["achievement_id"],
            ["achievement.id"],
            name=op.f("achievement_evidence_achievement_id_fkey"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["item_id"],
            ["evidence_item.id"],
            name=op.f("achievement_evidence_item_id_fkey"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("achievement_evidence_pkey")),
        sa.UniqueConstraint("achievement_id", "item_id", name="uq_achievement_evidence_pair"),
    )
    op.create_index(
        op.f("ix_achievement_evidence_achievement_id"), "achievement_evidence", ["achievement_id"]
    )
    op.create_index(op.f("ix_achievement_evidence_item_id"), "achievement_evidence", ["item_id"])

    for table in TRIGGER_TABLES:
        create_updated_at_trigger(table)


def downgrade() -> None:
    for table in reversed(TRIGGER_TABLES):
        drop_updated_at_trigger(table)

    op.drop_table("achievement_evidence")
    op.drop_table("achievement_revision")
    op.drop_table("achievement_extraction_run")
    op.drop_table("achievement")

    op.execute(sa.text("DROP TYPE IF EXISTS achievement_revision_source"))
    op.execute(sa.text("DROP TYPE IF EXISTS achievement_origin"))
    op.execute(sa.text("DROP TYPE IF EXISTS achievement_status"))
