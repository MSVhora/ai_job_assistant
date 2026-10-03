import enum
import uuid
from datetime import date, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy import text as sql_text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.evidence import SyncStatus


def _enum_values(enum_class: type[enum.Enum]) -> list[str]:
    return [str(member.value) for member in enum_class]


class AchievementStatus(enum.StrEnum):
    draft = "draft"
    approved = "approved"
    rejected = "rejected"
    archived = "archived"


class AchievementOrigin(enum.StrEnum):
    ai_extracted = "ai_extracted"
    user_created = "user_created"
    merged = "merged"


class AchievementRevisionSource(enum.StrEnum):
    ai_extraction = "ai_extraction"
    manual_edit = "manual_edit"
    merge = "merge"
    split_ = "split"  # `split` would shadow str.split on the StrEnum
    metric_confirmation = "metric_confirmation"
    status_change = "status_change"


class Achievement(Base):
    """A STAR achievement distilled from evidence. Only `approved` rows are used downstream."""

    __tablename__ = "achievement"
    __table_args__ = (
        CheckConstraint("difficulty BETWEEN 1 AND 5", name="difficulty_range"),
        Index("ix_achievement_candidate_status", "candidate_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4, server_default=sql_text("gen_random_uuid()")
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("candidate.id", ondelete="RESTRICT"), index=True
    )
    status: Mapped[AchievementStatus] = mapped_column(
        Enum(AchievementStatus, name="achievement_status", native_enum=True),
        default=AchievementStatus.draft,
        server_default=AchievementStatus.draft.value,
    )
    origin: Mapped[AchievementOrigin] = mapped_column(
        Enum(AchievementOrigin, name="achievement_origin", native_enum=True),
        default=AchievementOrigin.ai_extracted,
        server_default=AchievementOrigin.ai_extracted.value,
    )
    title: Mapped[str] = mapped_column(Text)
    situation: Mapped[str | None] = mapped_column(Text, nullable=True)
    task: Mapped[str | None] = mapped_column(Text, nullable=True)
    action: Mapped[str | None] = mapped_column(Text, nullable=True)
    result: Mapped[str | None] = mapped_column(Text, nullable=True)
    metrics: Mapped[list[dict[str, object]]] = mapped_column(
        JSONB, default=list, server_default=sql_text("'[]'::jsonb")
    )
    skills: Mapped[list[str]] = mapped_column(
        JSONB, default=list, server_default=sql_text("'[]'::jsonb")
    )
    impact_type: Mapped[str] = mapped_column(String(30), default="other")
    difficulty: Mapped[int] = mapped_column(SmallInteger, default=3)
    project_key: Mapped[str | None] = mapped_column(nullable=True)
    employer_ref: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    time_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    time_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    # Dimension pinned to Gemini gemini-embedding-001 (dimensions=768; native output is
    # 3072, truncated via the dimensions param). Changing the dimension =
    # new column + backfill migration, never a silent dimension change.
    embedding: Mapped[list[float] | None] = mapped_column(Vector(768), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(nullable=True)
    source_chunk_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    edited_by_user: Mapped[bool] = mapped_column(default=False, server_default=sql_text("false"))
    derived_from_private: Mapped[bool] = mapped_column(
        default=False, server_default=sql_text("false")
    )
    review_flags: Mapped[list[str]] = mapped_column(
        JSONB, default=list, server_default=sql_text("'[]'::jsonb")
    )
    evidence_stale_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AchievementEvidence(Base):
    __tablename__ = "achievement_evidence"
    __table_args__ = (
        UniqueConstraint("achievement_id", "item_id", name="uq_achievement_evidence_pair"),
        CheckConstraint("role IN ('primary', 'supporting')", name="role_values"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4, server_default=sql_text("gen_random_uuid()")
    )
    achievement_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("achievement.id", ondelete="CASCADE"), index=True
    )
    # RESTRICT: evidence under an achievement is never silently deleted.
    item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("evidence_item.id", ondelete="RESTRICT"), index=True
    )
    role: Mapped[str] = mapped_column(String(20), default="supporting")
    quote: Mapped[str | None] = mapped_column(Text, nullable=True)


class AchievementRevision(Base):
    """Audit trail (the `profile_revision` analogue); archive, never delete."""

    __tablename__ = "achievement_revision"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4, server_default=sql_text("gen_random_uuid()")
    )
    achievement_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("achievement.id", ondelete="RESTRICT"), index=True
    )
    source: Mapped[AchievementRevisionSource] = mapped_column(
        Enum(
            AchievementRevisionSource,
            name="achievement_revision_source",
            native_enum=True,
            values_callable=_enum_values,
        )
    )
    diff: Mapped[dict[str, object]] = mapped_column(
        JSONB, default=dict, server_default=sql_text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AchievementExtractionRun(Base):
    """One guarded extraction run; the partial unique index admits one active run per candidate."""

    __tablename__ = "achievement_extraction_run"
    __table_args__ = (
        Index(
            "uq_achievement_extraction_active_run",
            "candidate_id",
            unique=True,
            postgresql_where=sql_text("status IN ('pending','running')"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4, server_default=sql_text("gen_random_uuid()")
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("candidate.id", ondelete="RESTRICT"), index=True
    )
    status: Mapped[SyncStatus] = mapped_column(
        Enum(SyncStatus, name="sync_status", native_enum=True, create_type=False),
        default=SyncStatus.pending,
        server_default=SyncStatus.pending.value,
    )
    estimate: Mapped[dict[str, object]] = mapped_column(
        JSONB, default=dict, server_default=sql_text("'{}'::jsonb")
    )
    progress: Mapped[dict[str, object]] = mapped_column(
        JSONB, default=dict, server_default=sql_text("'{}'::jsonb")
    )
    usage: Mapped[dict[str, object]] = mapped_column(
        JSONB, default=dict, server_default=sql_text("'{}'::jsonb")
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
