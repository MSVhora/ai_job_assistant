import enum
import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy import (
    text as sql_text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class EvidenceKind(enum.StrEnum):
    commit = "commit"
    pull_request = "pull_request"
    review_comment = "review_comment"
    issue = "issue"
    readme = "readme"
    repo_summary = "repo_summary"
    note = "note"
    link = "link"
    resume_line = "resume_line"


class EvidenceItemStatus(enum.StrEnum):
    kept = "kept"
    filtered = "filtered"
    excluded = "excluded"


class SyncStatus(enum.StrEnum):
    pending = "pending"
    running = "running"
    paused = "paused"
    succeeded = "succeeded"
    failed = "failed"


class ContentLevel(enum.StrEnum):
    messages_and_prs = "messages_and_prs"
    metadata_only = "metadata_only"


class EvidenceSourceAccount(Base):
    """Per-candidate connector config (ORM name differs from the `EvidenceSource` protocol)."""

    __tablename__ = "evidence_source"
    __table_args__ = (
        UniqueConstraint("candidate_id", "kind", name="uq_evidence_source_candidate_kind"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4, server_default=sql_text("gen_random_uuid()")
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("candidate.id", ondelete="RESTRICT"), index=True
    )
    kind: Mapped[str] = mapped_column(String(50))
    account_login: Mapped[str | None] = mapped_column(nullable=True)
    extra_identities: Mapped[list[str]] = mapped_column(
        JSONB, default=list, server_default=sql_text("'[]'::jsonb")
    )
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scopes_refreshed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    token_scopes: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EvidenceScope(Base):
    __tablename__ = "evidence_scope"
    __table_args__ = (UniqueConstraint("source_id", "ref", name="uq_evidence_scope_source_ref"),)

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4, server_default=sql_text("gen_random_uuid()")
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("evidence_source.id", ondelete="CASCADE"), index=True
    )
    ref: Mapped[str] = mapped_column(String(255))
    is_private: Mapped[bool] = mapped_column(default=False, server_default=sql_text("false"))
    is_fork: Mapped[bool] = mapped_column(default=False, server_default=sql_text("false"))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    pushed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    contributed: Mapped[bool] = mapped_column(default=False, server_default=sql_text("false"))
    visible: Mapped[bool] = mapped_column(default=True, server_default=sql_text("true"))
    new_since_refresh: Mapped[bool] = mapped_column(default=False, server_default=sql_text("false"))
    enabled: Mapped[bool] = mapped_column(default=False, server_default=sql_text("false"))
    content_level: Mapped[ContentLevel] = mapped_column(
        Enum(ContentLevel, name="evidence_content_level", native_enum=True),
        default=ContentLevel.messages_and_prs,
        server_default=ContentLevel.messages_and_prs.value,
    )
    employer_ref: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    cursor: Mapped[dict[str, object]] = mapped_column(
        JSONB, default=dict, server_default=sql_text("'{}'::jsonb")
    )
    sync_state: Mapped[SyncStatus] = mapped_column(
        Enum(SyncStatus, name="sync_status", native_enum=True, create_type=False),
        default=SyncStatus.pending,
        server_default=SyncStatus.pending.value,
    )
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class EvidenceSyncRun(Base):
    """One guarded sync run; the partial unique index admits one active run per source."""

    __tablename__ = "evidence_sync_run"
    __table_args__ = (
        Index(
            "uq_evidence_sync_active_run",
            "source_id",
            unique=True,
            postgresql_where=sql_text("status IN ('pending','running')"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4, server_default=sql_text("gen_random_uuid()")
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("evidence_source.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[SyncStatus] = mapped_column(
        Enum(SyncStatus, name="sync_status", native_enum=True, create_type=False),
        default=SyncStatus.pending,
        server_default=SyncStatus.pending.value,
    )
    progress: Mapped[dict[str, object]] = mapped_column(
        JSONB, default=dict, server_default=sql_text("'{}'::jsonb")
    )
    rate_limit: Mapped[dict[str, object]] = mapped_column(
        JSONB, default=dict, server_default=sql_text("'{}'::jsonb")
    )
    resume_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    usage: Mapped[dict[str, object]] = mapped_column(
        JSONB, default=dict, server_default=sql_text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class EvidenceItem(Base):
    """Atomic normalized evidence; filtered items are kept (status) so the user can restore them."""

    __tablename__ = "evidence_item"
    __table_args__ = (
        UniqueConstraint(
            "candidate_id", "kind", "external_id", name="uq_evidence_item_candidate_kind_external"
        ),
        Index("ix_evidence_item_candidate_project", "candidate_id", "project_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4, server_default=sql_text("gen_random_uuid()")
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("candidate.id", ondelete="RESTRICT"), index=True
    )
    # SET NULL: removing a scope keeps the evidence (provenance pointer only).
    scope_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("evidence_scope.id", ondelete="SET NULL"), nullable=True, index=True
    )
    kind: Mapped[EvidenceKind] = mapped_column(
        Enum(EvidenceKind, name="evidence_kind", native_enum=True)
    )
    external_id: Mapped[str] = mapped_column(String(255))
    project_key: Mapped[str | None] = mapped_column(nullable=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    body: Mapped[str] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    authored_by_user: Mapped[bool] = mapped_column(default=True, server_default=sql_text("true"))
    status: Mapped[EvidenceItemStatus] = mapped_column(
        Enum(EvidenceItemStatus, name="evidence_item_status", native_enum=True),
        default=EvidenceItemStatus.kept,
        server_default=EvidenceItemStatus.kept.value,
    )
    filter_reason: Mapped[str | None] = mapped_column(nullable=True)
    is_private: Mapped[bool] = mapped_column(default=False, server_default=sql_text("false"))
    meta: Mapped[dict[str, object]] = mapped_column(
        JSONB, default=dict, server_default=sql_text("'{}'::jsonb")
    )
    content_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class EvidenceChunk(Base):
    __tablename__ = "evidence_chunk"
    __table_args__ = (CheckConstraint("token_count >= 0", name="token_count_nonneg"),)

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4, server_default=sql_text("gen_random_uuid()")
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("candidate.id", ondelete="RESTRICT"), index=True
    )
    kind: Mapped[str] = mapped_column(String(50))
    project_key: Mapped[str | None] = mapped_column(nullable=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    text: Mapped[str] = mapped_column(Text)
    token_count: Mapped[int] = mapped_column(default=0, server_default=sql_text("0"))
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    chunker_version: Mapped[str] = mapped_column(String(50))
    extracted_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    contains_private: Mapped[bool] = mapped_column(default=False, server_default=sql_text("false"))
    # Dimension pinned to Gemini gemini-embedding-001 (dimensions=768; native output is
    # 3072, truncated via the dimensions param). Changing the dimension =
    # new column + backfill migration, never a silent dimension change.
    embedding: Mapped[list[float] | None] = mapped_column(Vector(768), nullable=True)
    time_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    time_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class EvidenceChunkItem(Base):
    __tablename__ = "evidence_chunk_item"

    chunk_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("evidence_chunk.id", ondelete="CASCADE"), primary_key=True
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("evidence_item.id", ondelete="CASCADE"), primary_key=True, index=True
    )
