import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Profile(Base):
    __tablename__ = "profile"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("candidate.id", ondelete="RESTRICT"), index=True
    )
    name: Mapped[str]
    structured_profile: Mapped[dict[str, object]] = mapped_column(JSONB)
    # Dimension pinned to Gemini text-embedding-004 (768); changing embedding models =
    # new column + backfill migration, never a silent dimension change.
    embedding: Mapped[list[float] | None] = mapped_column(Vector(768), nullable=True)
    search_queries: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    source_resume_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("resume.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
