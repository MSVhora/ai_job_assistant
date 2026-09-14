import html
import re
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Literal, Protocol

import httpx
from pydantic import BaseModel, Field, field_validator

from app.core.errors import InvalidSourceFilterError
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


SourceFilterValue = str | int | bool | list[str]

_MAX_OPTION_LIST_ITEMS = 50
_MAX_OPTION_ITEM_LEN = 200


class SourceFilterOption(BaseModel):
    value: str = Field(min_length=1, max_length=100)
    label: str = Field(min_length=1, max_length=100)


class SourceFilterDecl(BaseModel):
    key: str = Field(min_length=1, max_length=50, pattern=r"^[a-z][a-z0-9_]*$")
    label: str = Field(min_length=1, max_length=100)
    type: Literal["text", "number", "select", "multiselect", "boolean"]
    options: list[SourceFilterOption] | None = None
    required: bool = False
    placeholder: str | None = Field(default=None, max_length=100)
    help_text: str | None = Field(default=None, max_length=200)


class JobSearchQuery(BaseModel):
    query: str = ""
    title_phrase: str | None = None
    skills_any: list[str] = Field(default_factory=list)
    exclude_any: list[str] = Field(default_factory=list)
    location: str | None = None
    country: str
    results_wanted: int = Field(default=50, ge=1, le=50)
    max_days_old: int | None = Field(default=None, ge=1, le=90)
    salary_min: float | None = Field(default=None, ge=0)
    salary_max: float | None = Field(default=None, ge=0)
    salary_currency: str | None = Field(default=None, pattern=r"^[A-Za-z]{3}$")
    options: dict[str, "SourceFilterValue"] = Field(default_factory=dict)

    @field_validator("country", mode="after")
    @classmethod
    def _lowercase_country(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("title_phrase", mode="after")
    @classmethod
    def _strip_title(cls, value: str | None) -> str | None:
        return value.strip() if value else value


def date_posted_bucket(max_days_old: int | None) -> str:
    """Map the shared day-count freshness filter to a LinkedIn datePosted bucket."""
    if max_days_old is None:
        return "anyTime"
    if max_days_old <= 1:
        return "past24h"
    if max_days_old <= 7:
        return "pastWeek"
    if max_days_old <= 30:
        return "pastMonth"
    return "anyTime"


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
    expires_at: datetime | None = None
    is_closed: bool = False
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

    def filters(self) -> list[SourceFilterDecl]: ...

    async def search(self, query: JobSearchQuery) -> list[RawJobPosting]: ...

    def normalize(self, raw: RawJobPosting) -> JobPostingData: ...


ClientFactory = Callable[[], httpx.AsyncClient]


def _validate_option_value(decl: SourceFilterDecl, value: object) -> None:
    noun = f"filter '{decl.key}'"
    if decl.type == "number":
        if type(value) is not int:
            raise InvalidSourceFilterError(f"{noun} must be an integer")
        return
    if decl.type == "boolean":
        if type(value) is not bool:
            raise InvalidSourceFilterError(f"{noun} must be true or false")
        return
    if decl.type == "select":
        allowed = {option.value for option in decl.options or []}
        if type(value) is not str or value not in allowed:
            allowed_list = ", ".join(sorted(allowed))
            raise InvalidSourceFilterError(f"{noun} must be one of: {allowed_list}")
        return
    if decl.type == "multiselect":
        if not isinstance(value, list) or not value:
            raise InvalidSourceFilterError(f"{noun} must be a non-empty list of strings")
        if any(type(item) is not str for item in value):
            raise InvalidSourceFilterError(f"{noun} must be a non-empty list of strings")
        if len(value) > _MAX_OPTION_LIST_ITEMS:
            raise InvalidSourceFilterError(
                f"{noun} must have at most {_MAX_OPTION_LIST_ITEMS} entries"
            )
        if any(len(item) == 0 or len(item) > _MAX_OPTION_ITEM_LEN for item in value):
            raise InvalidSourceFilterError(
                f"{noun} entries must be between 1 and {_MAX_OPTION_ITEM_LEN} characters"
            )
        return
    if type(value) is not str or not value.strip():
        raise InvalidSourceFilterError(f"{noun} must be a non-empty string")
    if len(value) > _MAX_OPTION_ITEM_LEN:
        raise InvalidSourceFilterError(f"{noun} must be at most {_MAX_OPTION_ITEM_LEN} characters")


def validate_source_options(
    declarations: list[SourceFilterDecl], options: dict[str, SourceFilterValue], source_name: str
) -> None:
    """Validate per-source option values against the source's declaration.

    Raises InvalidSourceFilterError (400) naming the offending key; C{options} is
    the request-side dict already capped by the schema (12 keys).
    """
    decls = {decl.key: decl for decl in declarations}
    for key, value in options.items():
        decl = decls.get(key)
        if decl is None:
            raise InvalidSourceFilterError(f"unknown filter '{key}' for source '{source_name}'")
        _validate_option_value(decl, value)
