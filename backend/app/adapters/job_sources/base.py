from collections.abc import Callable
from datetime import datetime
from typing import Protocol

import httpx
from pydantic import BaseModel, Field, field_validator

from app.models import JobType, RemoteType


class ConnectorError(Exception):
    pass


class JobSearchQuery(BaseModel):
    query: str
    location: str | None = None
    country: str
    results_wanted: int = Field(default=50, ge=1, le=50)

    @field_validator("country", mode="after")
    @classmethod
    def _lowercase_country(cls, value: str) -> str:
        return value.strip().lower()


class RawJobPosting(BaseModel):
    external_id: str
    payload: dict[str, object]


class JobPostingData(BaseModel):
    external_id: str = Field(min_length=1, max_length=255)
    title: str = Field(min_length=1, max_length=500)
    company: str | None = Field(default=None, max_length=255)
    url: str | None = Field(default=None, max_length=2048)
    location: str | None = Field(default=None, max_length=255)
    job_type: JobType | None = None
    remote_type: RemoteType | None = None
    description: str | None = None
    posted_at: datetime | None = None
    salary_min: float | None = Field(default=None, ge=0)
    salary_max: float | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, pattern=r"^[A-Za-z]{3}$")
    raw_payload: dict[str, object]


class JobSource(Protocol):
    name: str
    is_official_api: bool
    disclosure_required: bool

    def is_configured(self) -> bool: ...

    async def search(self, query: JobSearchQuery) -> list[RawJobPosting]: ...

    def normalize(self, raw: RawJobPosting) -> JobPostingData: ...


ClientFactory = Callable[[], httpx.AsyncClient]
