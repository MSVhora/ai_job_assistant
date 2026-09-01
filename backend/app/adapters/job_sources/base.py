import html
import re
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol

import httpx
from pydantic import BaseModel, Field, field_validator

from app.models import JobType, RemoteType


class ConnectorError(Exception):
    pass


class ConnectorConfigError(ConnectorError):
    pass


_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def clean_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    text = _WS_RE.sub(" ", _TAG_RE.sub(" ", html.unescape(value))).strip()
    return text or None


def parse_datetime(value: object) -> datetime | None:
    if isinstance(value, bool) or not isinstance(value, str | int | float):
        return None
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed
    seconds = value / 1000 if value > 1e12 else value
    return datetime.fromtimestamp(seconds, tz=UTC)


class JobSearchQuery(BaseModel):
    query: str = ""
    title_phrase: str | None = None
    skills_any: list[str] = Field(default_factory=list)
    exclude_any: list[str] = Field(default_factory=list)
    location: str | None = None
    country: str
    results_wanted: int = Field(default=50, ge=1, le=50)
    salary_min: float | None = Field(default=None, ge=0)
    salary_max: float | None = Field(default=None, ge=0)
    salary_currency: str | None = Field(default=None, pattern=r"^[A-Za-z]{3}$")

    @field_validator("country", mode="after")
    @classmethod
    def _lowercase_country(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("title_phrase", mode="after")
    @classmethod
    def _strip_title(cls, value: str | None) -> str | None:
        return value.strip() if value else value


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
    supports_exclusions: bool

    def is_configured(self) -> bool: ...

    async def search(self, query: JobSearchQuery) -> list[RawJobPosting]: ...

    def normalize(self, raw: RawJobPosting) -> JobPostingData: ...


ClientFactory = Callable[[], httpx.AsyncClient]
