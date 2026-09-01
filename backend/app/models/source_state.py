from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class SourceState(Base):
    __tablename__ = "source_state"

    source_name: Mapped[str] = mapped_column(String(50), primary_key=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
