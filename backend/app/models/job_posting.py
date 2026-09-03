import enum
import uuid
from datetime import datetime
from decimal import Decimal

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String, Text, UniqueConstraint, func
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
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    source: Mapped[str] = mapped_column(String(50))
    external_id: Mapped[str] = mapped_column(String(255))
    title: Mapped[str]
    company: Mapped[str | None] = mapped_column(String(255), nullable=True)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
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
    salary_min: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    salary_max: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    raw_payload: Mapped[dict[str, object]] = mapped_column(JSONB)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    job_search_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("job_search.id", ondelete="SET NULL"), nullable=True, index=True
    )
