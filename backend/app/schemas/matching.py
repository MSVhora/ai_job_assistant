from pydantic import BaseModel, Field, field_validator

from app.models import JobType, RemoteType

_MAX_LOCATION = 200


class MatchFilters(BaseModel):
    """User- or preference-driven hard filters applied in SQL before ranking."""

    location: str | None = Field(default=None, max_length=_MAX_LOCATION)
    remote_type: RemoteType | None = None
    job_type: JobType | None = None
    posted_within_days: int | None = Field(default=None, ge=1, le=90)

    @field_validator("location", mode="after")
    @classmethod
    def _blank_to_none(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        return trimmed or None
