import enum
import uuid
from datetime import datetime
from decimal import Decimal

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class JobType(enum.StrEnum):
    full_time = "full_time"
    part_time = "part_time"
    contract = "contract"
    internship = "internship"
    temporary = "temporary"


class RemoteType(enum.StrEnum):
    remote = "remote"
    hybrid = "hybrid"
    on_site = "on_site"


class JobPosting(Base):
    __tablename__ = "job_posting"
    __table_args__ = (
        UniqueConstraint("source", "external_id", name="uq_job_posting_source_external_id"),
        # Issue #38: trigram index serving the cross-source dedupe candidate
        # lookup (`title % :title` with pg_trgm.similarity_threshold set per
        # statement — an explicit similarity() >= comparison is not indexable).
        Index(
            "ix_job_posting_title_trgm",
            "title",
            postgresql_using="gin",
            postgresql_ops={"title": "gin_trgm_ops"},
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    source: Mapped[str] = mapped_column(String(50))
    external_id: Mapped[str] = mapped_column(String(255))
    title: Mapped[str]
    company: Mapped[str | None] = mapped_column(String(255), nullable=True)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Issue #38: the run's resolved 2-letter country, stored for the dedupe
    # grouping key (same country = the runnable "location bucket"); refreshed
    # on re-fetch via the upsert's on_conflict path.
    country: Mapped[str | None] = mapped_column(String(2), nullable=True)
    # Issue #38: cross-source canonical grouping — NULL = this row is its own
    # canonical; a duplicate points at its canonical (which always has
    # canonical_id NULL — chains are resolved on write by posting_dedupe).
    canonical_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("job_posting.id", use_alter=True, name="fk_job_posting_canonical_id"),
        nullable=True,
        index=True,
    )
    # Issue #38: merged record — [{source, url}] of the duplicate postings
    # folded into this canonical row.
    source_urls: Mapped[list[dict[str, object]] | None] = mapped_column(JSONB, nullable=True)
    job_type: Mapped[JobType | None] = mapped_column(
        Enum(JobType, name="job_type", native_enum=True), nullable=True
    )
    remote_type: Mapped[RemoteType | None] = mapped_column(
        Enum(RemoteType, name="remote_type", native_enum=True), nullable=True
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Dimension pinned to Gemini gemini-embedding-001 (dimensions=768; native output is
    # 3072, truncated via the dimensions param). Changing the dimension =
    # new column + backfill migration, never a silent dimension change.
    embedding: Mapped[list[float] | None] = mapped_column(Vector(768), nullable=True)
    posted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_closed: Mapped[bool] = mapped_column(default=False, server_default=text("false"))
    salary_min: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    salary_max: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    raw_payload: Mapped[dict[str, object]] = mapped_column(JSONB)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
