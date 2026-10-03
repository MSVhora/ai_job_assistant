import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    SmallInteger,
    String,
    Text,
    func,
)
from sqlalchemy import text as sql_text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class ResumeDocumentStatus(enum.StrEnum):
    draft = "draft"
    final = "final"


class ResumeDocument(Base):
    """One tailored resume: structured content with per-bullet provenance, never a rendered file."""

    __tablename__ = "resume_document"
    __table_args__ = (
        CheckConstraint("page_target BETWEEN 1 AND 4", name="page_target_range"),
        CheckConstraint("jd_weight BETWEEN 0 AND 0.5", name="jd_weight_range"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4, server_default=sql_text("gen_random_uuid()")
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("candidate.id", ondelete="RESTRICT"), index=True
    )
    # CASCADE: a document is an output of one profile and goes with it.
    profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("profile.id", ondelete="CASCADE"), index=True
    )
    # SET NULL: the match is only the provenance of the job description.
    match_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("match.id", ondelete="SET NULL"), index=True, nullable=True
    )
    title: Mapped[str] = mapped_column(String(200))
    page_target: Mapped[int] = mapped_column(SmallInteger, default=1, server_default="1")
    jd_weight: Mapped[float] = mapped_column(Float, default=0.0, server_default="0")
    template: Mapped[str] = mapped_column(String(50), default="classic", server_default="classic")
    job_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    jd_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    content: Mapped[dict[str, object]] = mapped_column(
        JSONB, default=dict, server_default=sql_text("'{}'::jsonb")
    )
    layout: Mapped[dict[str, object]] = mapped_column(
        JSONB, default=dict, server_default=sql_text("'{}'::jsonb")
    )
    conflicts: Mapped[list[dict[str, object]]] = mapped_column(
        JSONB, default=list, server_default=sql_text("'[]'::jsonb")
    )
    comments: Mapped[list[dict[str, object]]] = mapped_column(
        JSONB, default=list, server_default=sql_text("'[]'::jsonb")
    )
    generation: Mapped[dict[str, object]] = mapped_column(
        JSONB, default=dict, server_default=sql_text("'{}'::jsonb")
    )
    status: Mapped[ResumeDocumentStatus] = mapped_column(
        Enum(ResumeDocumentStatus, name="resume_document_status", native_enum=True),
        default=ResumeDocumentStatus.draft,
        server_default=ResumeDocumentStatus.draft.value,
    )
    version: Mapped[int] = mapped_column(default=1, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ResumeDocumentRevision(Base):
    """Content snapshot written on every save; the newest 20 per document are kept."""

    __tablename__ = "resume_document_revision"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4, server_default=sql_text("gen_random_uuid()")
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("resume_document.id", ondelete="CASCADE"), index=True
    )
    version: Mapped[int]
    content: Mapped[dict[str, object]] = mapped_column(
        JSONB, default=dict, server_default=sql_text("'{}'::jsonb")
    )
    source: Mapped[str] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
