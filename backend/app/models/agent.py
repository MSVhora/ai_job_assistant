import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, Text, func
from sqlalchemy import text as sql_text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class AgentRole(enum.StrEnum):
    user = "user"
    assistant = "assistant"


class AgentSession(Base):
    """One interview-prep conversation, anchored on a profile and optionally on a matched job."""

    __tablename__ = "agent_session"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4, server_default=sql_text("gen_random_uuid()")
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("candidate.id", ondelete="RESTRICT"), index=True
    )
    # CASCADE: a session is an output of one profile and goes with it.
    profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("profile.id", ondelete="CASCADE"), index=True
    )
    # SET NULL: the match is only the provenance of the job context.
    match_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("match.id", ondelete="SET NULL"), index=True, nullable=True
    )
    title: Mapped[str] = mapped_column(String(200))
    style_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    summarized_through: Mapped[int] = mapped_column(default=0, server_default=sql_text("0"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AgentMessage(Base):
    __tablename__ = "agent_message"
    __table_args__ = (Index("ix_agent_message_session_created", "session_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4, server_default=sql_text("gen_random_uuid()")
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agent_session.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[AgentRole] = mapped_column(Enum(AgentRole, name="agent_role", native_enum=True))
    content: Mapped[str] = mapped_column(Text)
    question_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    citations: Mapped[list[dict[str, object]]] = mapped_column(
        JSONB, default=list, server_default=sql_text("'[]'::jsonb")
    )
    grounding: Mapped[dict[str, object]] = mapped_column(
        JSONB, default=dict, server_default=sql_text("'{}'::jsonb")
    )
    usage: Mapped[dict[str, object]] = mapped_column(
        JSONB, default=dict, server_default=sql_text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp()
    )
