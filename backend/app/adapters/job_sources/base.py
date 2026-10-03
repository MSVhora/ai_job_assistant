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
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return None
        return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed
    seconds = value / 1000 if value > _EPOCH_MILLIS_THRESHOLD else value
    return datetime.fromtimestamp(seconds, tz=UTC)


_EPOCH_MILLIS_THRESHOLD = 1e12
_DAYS_PER_WEEK = 7
_DAYS_PER_MONTH = 30

SourceFilterValue = str | int | bool | list[str]


class TermPlan(BaseModel):
    """Per-source rendered search terms, produced by the rendering layer.

    Precedence (decided in services/query_rendering.py, not in connectors):

    - adzuna: ``what_phrase`` when a title exists, ``what_or``/``what_and``
      combined with it, ``what_exclude`` always, and ``what`` (free text)
      only when there is no ``what_phrase``.
    - linkedin (apify_ actors): ``keywords`` is the NL semantic brief
      (``"{title} with {skills}, {seniority} level"``, issue #35); a
      user-typed request query overrides it, and the spec's exclude terms
      become an appended ``not …`` clause in either case (the only
      exclusion channel post-Aug-2026). No salary text. ``date_posted`` is
      the freshness bucket.
    """

    what_and: list[str] = Field(default_factory=list)
    what_or: list[str] = Field(default_factory=list)
    what_phrase: str | None = None
    what_exclude: list[str] = Field(default_factory=list)
    what: str | None = None
    keywords: str | None = None
    location: str | None = None
    date_posted: str | None = None


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
    """Connector-level query payload: shared filters plus the rendered terms.

    ``term_plan`` carries the per-source term precedence decided in
    ``services/query_rendering.py``; connectors map it mechanically onto
    their API params and never make precedence decisions of their own.
    """

    query: str = ""
    term_plan: TermPlan | None = None
    location: str | None = None
    country: str
    results_wanted: int = Field(default=50, ge=1, le=100)
    max_days_old: int | None = Field(default=None, ge=1, le=90)
    salary_min: float | None = Field(default=None, ge=0)
    salary_max: float | None = Field(default=None, ge=0)
    salary_currency: str | None = Field(default=None, pattern=r"^[A-Za-z]{3}$")
    options: dict[str, "SourceFilterValue"] = Field(default_factory=dict)

    @field_validator("country", mode="after")
    @classmethod
    def _lowercase_country(cls, value: str) -> str:
        return value.strip().lower()


def date_posted_bucket(max_days_old: int | None) -> str:
    """Map the shared day-count freshness filter to a LinkedIn datePosted bucket.

    The bucket values are the LinkedIn actor's accepted enum
    (anyTime / past24Hours / pastWeek / pastMonth) — note the capital H on
    past24Hours; anything else is rejected with a 400 at run creation.
    """
    if max_days_old is None:
        return "anyTime"
    if max_days_old <= 1:
        return "past24Hours"
    if max_days_old <= _DAYS_PER_WEEK:
        return "pastWeek"
    if max_days_old <= _DAYS_PER_MONTH:
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
            msg = f"{noun} must be an integer"
            raise InvalidSourceFilterError(msg)
        return
    if decl.type == "boolean":
        if type(value) is not bool:
            msg = f"{noun} must be true or false"
            raise InvalidSourceFilterError(msg)
        return
    if decl.type == "select":
        allowed = {option.value for option in decl.options or []}
        if type(value) is not str or value not in allowed:
            allowed_list = ", ".join(sorted(allowed))
            msg = f"{noun} must be one of: {allowed_list}"
            raise InvalidSourceFilterError(msg)
        return
    if decl.type == "multiselect":
        if not isinstance(value, list) or not value:
            msg = f"{noun} must be a non-empty list of strings"
            raise InvalidSourceFilterError(msg)
        if any(type(item) is not str for item in value):
            msg = f"{noun} must be a non-empty list of strings"
            raise InvalidSourceFilterError(msg)
        if len(value) > _MAX_OPTION_LIST_ITEMS:
            msg = f"{noun} must have at most {_MAX_OPTION_LIST_ITEMS} entries"
            raise InvalidSourceFilterError(msg)
        if any(len(item) == 0 or len(item) > _MAX_OPTION_ITEM_LEN for item in value):
            msg = f"{noun} entries must be between 1 and {_MAX_OPTION_ITEM_LEN} characters"
            raise InvalidSourceFilterError(msg)
        return
    if type(value) is not str or not value.strip():
        msg = f"{noun} must be a non-empty string"
        raise InvalidSourceFilterError(msg)
    if len(value) > _MAX_OPTION_ITEM_LEN:
        msg = f"{noun} must be at most {_MAX_OPTION_ITEM_LEN} characters"
        raise InvalidSourceFilterError(msg)


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
            msg = f"unknown filter '{key}' for source '{source_name}'"
            raise InvalidSourceFilterError(msg)
        _validate_option_value(decl, value)
