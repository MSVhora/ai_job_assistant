import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class JobSearchStatus(enum.StrEnum):
    pending = "pending"
    running = "running"
    succeeded = "succeeded"
    partial = "partial"
    failed = "failed"


class JobSearch(Base):
    __tablename__ = "job_search"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    status: Mapped[JobSearchStatus] = mapped_column(
        Enum(JobSearchStatus, name="job_search_status", native_enum=True),
        default=JobSearchStatus.pending,
    )
    query: Mapped[dict[str, object]] = mapped_column(JSONB)
    results: Mapped[list[dict[str, object]] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
