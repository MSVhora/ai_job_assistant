from datetime import datetime

from sqlalchemy import DateTime, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class LLMOutputCache(Base):
    """Structured LLM outputs keyed by a SHA-256 of (task, model, prompt version, redacted inputs).

    Deliberately not candidate-owned: rows are content-addressed and hold only outputs
    computed from already-redacted inputs, so there is no owner to scope them to.
    """

    __tablename__ = "llm_output_cache"
    __table_args__ = (Index("ix_llm_output_cache_created_at", "created_at"),)

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    task: Mapped[str] = mapped_column(String(20))
    model: Mapped[str] = mapped_column(Text)
    prompt_version: Mapped[str] = mapped_column(Text)
    output: Mapped[dict[str, object]] = mapped_column(JSONB)
    prompt_tokens: Mapped[int] = mapped_column(default=0)
    completion_tokens: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
