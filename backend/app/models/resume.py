import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base

if TYPE_CHECKING:
    from app.models.candidate import Candidate


class Resume(Base):
    __tablename__ = "resume"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("candidate.id", ondelete="RESTRICT"), index=True
    )
    file_path: Mapped[str]
    original_filename: Mapped[str]
    content_type: Mapped[str]
    size_bytes: Mapped[int]
    extracted_text: Mapped[str | None]
    page_count: Mapped[int | None]
    parsed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    parse_version: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    candidate: Mapped["Candidate"] = relationship(back_populates="resumes")
