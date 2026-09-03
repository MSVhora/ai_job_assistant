import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Text, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


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
    vector_score: Mapped[float] = mapped_column(Float)
    role_fit: Mapped[float | None] = mapped_column(Float, nullable=True)
    company_fit: Mapped[float | None] = mapped_column(Float, nullable=True)
    final_score: Mapped[float] = mapped_column(Float)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
