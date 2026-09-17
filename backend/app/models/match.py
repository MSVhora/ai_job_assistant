import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Index, Text, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class MatchRebuildStatus(enum.StrEnum):
    pending = "pending"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"


class Match(Base):
    __tablename__ = "match"
    __table_args__ = (
        UniqueConstraint("profile_id", "job_posting_id", name="uq_match_profile_job_posting"),
        Index("ix_match_profile_final_score", "profile_id", text("final_score DESC")),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("profile.id", ondelete="CASCADE"), index=True
    )
    job_posting_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("job_posting.id", ondelete="CASCADE"), index=True
    )
    # Issue #37: nullable when the posting never got embedded — fallback rows
    # score on skill + recency + salary alone (weight-renormalized).
    vector_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    skill_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    recency_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    salary_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    role_fit: Mapped[float | None] = mapped_column(Float, nullable=True)
    company_fit: Mapped[float | None] = mapped_column(Float, nullable=True)
    final_score: Mapped[float] = mapped_column(Float)
    # Issue #39 engagement signals: first-write-wins timestamps recorded by
    # /api/matches/{id}/signals and the /apply redirect; unsave/undismiss NULL
    # them back. Never touch scoring — they feed query tuning only.
    first_opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    clicked_apply_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    saved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class MatchRebuild(Base):
    """One explicit per-profile match-corpus rebuild run (v3 D7).

    Provides DB-queryable background status for `POST /api/profiles/{id}/rebuild-matches`;
    the run banner polls the latest row. `corpus_count` = postings found by the
    profile's own searches, `scored_count` = those with embeddings.
    """

    __tablename__ = "match_rebuild"
    __table_args__ = (Index("ix_match_rebuild_profile_created", "profile_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("profile.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[MatchRebuildStatus] = mapped_column(
        Enum(MatchRebuildStatus, name="match_rebuild_status", native_enum=True),
        default=MatchRebuildStatus.pending,
    )
    corpus_count: Mapped[int] = mapped_column(default=0, server_default=text("0"))
    scored_count: Mapped[int] = mapped_column(default=0, server_default=text("0"))
    warning: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
