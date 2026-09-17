import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class SearchPosting(Base):
    """Append-only posting↔search association (many-to-many).

    A posting found again by any later search gains a row; nothing is
    overwritten. `job_posting.job_search_id` was backfilled here then dropped.
    """

    __tablename__ = "search_posting"
    __table_args__ = (
        UniqueConstraint("search_id", "posting_id", name="uq_search_posting_search_posting"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    search_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("job_search.id", ondelete="CASCADE"), index=True
    )
    posting_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("job_posting.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class JobSearchStatus(enum.StrEnum):
    pending = "pending"
    running = "running"
    succeeded = "succeeded"
    partial = "partial"
    failed = "failed"


class JobSearch(Base):
    __tablename__ = "job_search"
    __table_args__ = (
        Index(
            "uq_job_search_active_run",
            "profile_id",
            "source",
            unique=True,
            postgresql_where=text("status IN ('pending', 'running')"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("profile.id", ondelete="CASCADE"), index=True
    )
    # The one source this run targets (see the partial unique index over
    # (profile_id, source) among non-terminal statuses — issue #36).
    source: Mapped[str] = mapped_column(String(length=64), index=True)
    status: Mapped[JobSearchStatus] = mapped_column(
        Enum(JobSearchStatus, name="job_search_status", native_enum=True),
        default=JobSearchStatus.pending,
    )
    query: Mapped[dict[str, object]] = mapped_column(JSONB)
    results: Mapped[list[dict[str, object]] | None] = mapped_column(JSONB, nullable=True)
    matching: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
