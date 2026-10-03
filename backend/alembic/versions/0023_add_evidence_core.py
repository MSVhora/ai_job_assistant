"""add_evidence_core

Revision ID: 0023
Revises: 0022

v6 #48: the evidence store behind the Developer Evidence Engine —
`evidence_source` (per-candidate connector config), `evidence_scope` (opted-in
repos), `evidence_sync_run` (run guard: one pending/running run per source via
the partial unique index), `evidence_item` (normalized evidence; filtered items
are kept with a reason), `evidence_chunk` (+ `vector(768)` embedding, dimension
pinned to gemini-embedding-001, no ANN index at this scale) and
`evidence_chunk_item`. No existing table is touched and no data is migrated.

Downgrade drops the new tables and their enums; any stored evidence is lost.
"""

import pgvector.sqlalchemy
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from app.core.migration_helpers import create_updated_at_trigger, drop_updated_at_trigger

revision: str = "0023"
down_revision: str | None = "0022"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None

TRIGGER_TABLES = ("evidence_scope", "evidence_sync_run", "evidence_item", "evidence_chunk")
ACTIVE_RUN_WHERE = "status IN ('pending','running')"
SYNC_STATUSES = ("pending", "running", "paused", "succeeded", "failed")
EVIDENCE_KINDS = (
    "commit",
    "pull_request",
    "review_comment",
    "issue",
    "readme",
    "repo_summary",
    "note",
    "link",
    "resume_line",
)


def _sync_status() -> postgresql.ENUM:
    return postgresql.ENUM(*SYNC_STATUSES, name="sync_status", create_type=False)


def _now() -> sa.TextClause:
    return sa.text("now()")


def _uuid_pk() -> sa.Column[sa.Uuid]:
    return sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False)


def _jsonb(name: str, default: str) -> sa.Column[postgresql.JSONB]:
    return sa.Column(
        name,
        postgresql.JSONB(astext_type=sa.Text()),
        server_default=sa.text(default),
        nullable=False,
    )


def _timestamps(*, updated: bool = True) -> list[sa.Column[sa.DateTime]]:
    columns = [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_now(), nullable=False)
    ]
    if updated:
        columns.append(
            sa.Column(
                "updated_at", sa.DateTime(timezone=True), server_default=_now(), nullable=False
            )
        )
    return columns


def upgrade() -> None:
    bind = op.get_bind()
    postgresql.ENUM(*SYNC_STATUSES, name="sync_status").create(bind, checkfirst=False)

    _create_source_tables()
    _create_item_tables()
    _create_chunk_tables()

    for table in TRIGGER_TABLES:
        create_updated_at_trigger(table)


def _create_source_tables() -> None:
    op.create_table(
        "evidence_source",
        _uuid_pk(),
        sa.Column("candidate_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=50), nullable=False),
        sa.Column("account_login", sa.String(), nullable=True),
        _jsonb("extra_identities", "'[]'::jsonb"),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(updated=False),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["candidate.id"],
            name=op.f("evidence_source_candidate_id_fkey"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("evidence_source_pkey")),
        sa.UniqueConstraint("candidate_id", "kind", name="uq_evidence_source_candidate_kind"),
    )
    op.create_index(
        op.f("ix_evidence_source_candidate_id"), "evidence_source", ["candidate_id"], unique=False
    )

    op.create_table(
        "evidence_scope",
        _uuid_pk(),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("ref", sa.String(length=255), nullable=False),
        sa.Column("is_private", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "content_level",
            sa.Enum("messages_and_prs", "metadata_only", name="evidence_content_level"),
            server_default="messages_and_prs",
            nullable=False,
        ),
        sa.Column("employer_ref", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        _jsonb("cursor", "'{}'::jsonb"),
        sa.Column("sync_state", _sync_status(), server_default="pending", nullable=False),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["evidence_source.id"],
            name=op.f("evidence_scope_source_id_fkey"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("evidence_scope_pkey")),
        sa.UniqueConstraint("source_id", "ref", name="uq_evidence_scope_source_ref"),
    )
    op.create_index(
        op.f("ix_evidence_scope_source_id"), "evidence_scope", ["source_id"], unique=False
    )

    op.create_table(
        "evidence_sync_run",
        _uuid_pk(),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("status", _sync_status(), server_default="pending", nullable=False),
        _jsonb("progress", "'{}'::jsonb"),
        _jsonb("rate_limit", "'{}'::jsonb"),
        sa.Column("resume_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        _jsonb("usage", "'{}'::jsonb"),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["evidence_source.id"],
            name=op.f("evidence_sync_run_source_id_fkey"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("evidence_sync_run_pkey")),
    )
    op.create_index(
        op.f("ix_evidence_sync_run_source_id"), "evidence_sync_run", ["source_id"], unique=False
    )
    op.create_index(
        "uq_evidence_sync_active_run",
        "evidence_sync_run",
        ["source_id"],
        unique=True,
        postgresql_where=sa.text(ACTIVE_RUN_WHERE),
    )


def _create_item_tables() -> None:
    op.create_table(
        "evidence_item",
        _uuid_pk(),
        sa.Column("candidate_id", sa.Uuid(), nullable=False),
        sa.Column("scope_id", sa.Uuid(), nullable=True),
        sa.Column("kind", sa.Enum(*EVIDENCE_KINDS, name="evidence_kind"), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column("project_key", sa.String(), nullable=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("authored_by_user", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "status",
            sa.Enum("kept", "filtered", "excluded", name="evidence_item_status"),
            server_default="kept",
            nullable=False,
        ),
        sa.Column("filter_reason", sa.String(), nullable=True),
        sa.Column("is_private", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        _jsonb("meta", "'{}'::jsonb"),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["candidate.id"],
            name=op.f("evidence_item_candidate_id_fkey"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["scope_id"],
            ["evidence_scope.id"],
            name=op.f("evidence_item_scope_id_fkey"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("evidence_item_pkey")),
        sa.UniqueConstraint(
            "candidate_id", "kind", "external_id", name="uq_evidence_item_candidate_kind_external"
        ),
    )
    op.create_index(
        op.f("ix_evidence_item_candidate_id"), "evidence_item", ["candidate_id"], unique=False
    )
    op.create_index(
        "ix_evidence_item_candidate_project",
        "evidence_item",
        ["candidate_id", "project_key"],
        unique=False,
    )
    op.create_index(
        op.f("ix_evidence_item_occurred_at"), "evidence_item", ["occurred_at"], unique=False
    )
    op.create_index(op.f("ix_evidence_item_scope_id"), "evidence_item", ["scope_id"], unique=False)


def _create_chunk_tables() -> None:
    op.create_table(
        "evidence_chunk",
        _uuid_pk(),
        sa.Column("candidate_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=50), nullable=False),
        sa.Column("project_key", sa.String(), nullable=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("chunker_version", sa.String(length=50), nullable=False),
        sa.Column("extracted_hash", sa.String(length=64), nullable=True),
        sa.Column(
            "contains_private", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("embedding", pgvector.sqlalchemy.Vector(dim=768), nullable=True),
        sa.Column("time_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("time_end", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.CheckConstraint(
            "token_count >= 0", name=op.f("evidence_chunk_token_count_nonneg_check")
        ),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["candidate.id"],
            name=op.f("evidence_chunk_candidate_id_fkey"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("evidence_chunk_pkey")),
    )
    op.create_index(
        op.f("ix_evidence_chunk_candidate_id"), "evidence_chunk", ["candidate_id"], unique=False
    )
    op.create_index(
        op.f("ix_evidence_chunk_content_hash"), "evidence_chunk", ["content_hash"], unique=False
    )

    op.create_table(
        "evidence_chunk_item",
        sa.Column("chunk_id", sa.Uuid(), nullable=False),
        sa.Column("item_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["chunk_id"],
            ["evidence_chunk.id"],
            name=op.f("evidence_chunk_item_chunk_id_fkey"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["item_id"],
            ["evidence_item.id"],
            name=op.f("evidence_chunk_item_item_id_fkey"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("chunk_id", "item_id", name=op.f("evidence_chunk_item_pkey")),
    )
    op.create_index(
        op.f("ix_evidence_chunk_item_item_id"), "evidence_chunk_item", ["item_id"], unique=False
    )


def downgrade() -> None:
    for table in reversed(TRIGGER_TABLES):
        drop_updated_at_trigger(table)

    op.drop_table("evidence_chunk_item")
    op.drop_table("evidence_chunk")
    op.drop_table("evidence_item")
    op.drop_table("evidence_sync_run")
    op.drop_table("evidence_scope")
    op.drop_table("evidence_source")

    op.execute(sa.text("DROP TYPE IF EXISTS evidence_item_status"))
    op.execute(sa.text("DROP TYPE IF EXISTS evidence_kind"))
    op.execute(sa.text("DROP TYPE IF EXISTS evidence_content_level"))
    op.execute(sa.text("DROP TYPE IF EXISTS sync_status"))
