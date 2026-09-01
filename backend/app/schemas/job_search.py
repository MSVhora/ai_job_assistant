import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

JobSearchStatusLiteral = Literal["pending", "running", "succeeded", "partial", "failed"]


class JobSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=200)
    location: str | None = Field(default=None, max_length=200)
    country: str = Field(min_length=2, max_length=2, pattern=r"^[A-Za-z]{2}$")
    results_wanted: int = Field(default=50, ge=1, le=50)
    sources: list[str] | None = Field(default=None, max_length=10)

    @field_validator("query", "location", mode="after")
    @classmethod
    def _blank_to_none(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        return trimmed or None

    @field_validator("country", mode="after")
    @classmethod
    def _lowercase_country(cls, value: str) -> str:
        return value.strip().lower()


class JobSearchStartResponse(BaseModel):
    search_id: uuid.UUID
    status: JobSearchStatusLiteral


class SourceOutcome(BaseModel):
    source: str
    status: Literal["ok", "failed", "skipped"]
    count: int = 0
    warning: str | None = None


class JobSearchStatusResponse(BaseModel):
    search_id: uuid.UUID
    status: JobSearchStatusLiteral
    query: dict[str, Any]
    results: list[SourceOutcome] = []
    created_at: datetime
    updated_at: datetime


class SourceInfoResponse(BaseModel):
    name: str
    is_official_api: bool
    disclosure_required: bool
    is_configured: bool
