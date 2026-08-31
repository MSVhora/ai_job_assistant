import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class RevisionSource(enum.StrEnum):
    ai_extraction = "ai_extraction"
    manual_edit = "manual_edit"
    gap_fill = "gap_fill"
    reupload_merge = "reupload_merge"


class ProfileRevision(Base):
    __tablename__ = "profile_revision"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("candidate.id", ondelete="RESTRICT"), index=True
    )
    source: Mapped[RevisionSource] = mapped_column(
        Enum(RevisionSource, name="profile_revision_source", native_enum=True)
    )
    diff: Mapped[dict[str, object]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
