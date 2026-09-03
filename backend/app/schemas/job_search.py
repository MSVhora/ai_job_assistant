import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models import JobPosting

JobSearchStatusLiteral = Literal["pending", "running", "succeeded", "partial", "failed"]

_MAX_TITLE = 80
_MAX_TERM = 40
_MAX_SKILLS = 3
_MAX_EXCLUDE = 2
_MAX_QUERY = 200
_MAX_QUERIES = 10


def _clean_terms(values: list[str] | None) -> list[str] | None:
    if values is None:
        return None
    cleaned = [term.strip() for term in values if term.strip()]
    return cleaned or None


class SourceQuerySpec(BaseModel):
    title: str | None = Field(default=None, max_length=_MAX_TITLE)
    skills: list[str] | None = Field(default=None, max_length=_MAX_SKILLS)
    exclude: list[str] | None = Field(default=None, max_length=_MAX_EXCLUDE)
    query: str | None = Field(default=None, max_length=_MAX_QUERY)

    @field_validator("title", "query", mode="after")
    @classmethod
    def _strip_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None

    @field_validator("skills", "exclude", mode="after")
    @classmethod
    def _strip_terms(cls, values: list[str] | None) -> list[str] | None:
        return _clean_terms(values)

    def has_content(self) -> bool:
        return bool(self.title or self.query or self.skills)


class StoredSearchQueries(BaseModel):
    queries: dict[str, SourceQuerySpec]
    generated_at: datetime
    generated_by: str
    prompt_version: str


class SearchQueryGenerateRequest(BaseModel):
    sources: list[str] | None = Field(default=None, max_length=_MAX_QUERIES)


class SearchQueriesResponse(BaseModel):
    queries: dict[str, SourceQuerySpec]
    generated_at: datetime
    generated_by: str


class JobSearchRequest(BaseModel):
    query: str | None = Field(default=None, min_length=1, max_length=_MAX_QUERY)
    profile_id: uuid.UUID | None = None
    source_queries: dict[str, SourceQuerySpec] | None = Field(default=None, max_length=_MAX_QUERIES)
    location: str | None = Field(default=None, max_length=200)
    country: str = Field(min_length=2, max_length=2, pattern=r"^[A-Za-z]{2}$")
    results_wanted: int = Field(default=50, ge=1, le=50)
    salary_min: float | None = Field(default=None, ge=0)
    salary_max: float | None = Field(default=None, ge=0)
    salary_currency: str | None = Field(default=None, pattern=r"^[A-Za-z]{3}$")
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

    @field_validator("salary_currency", mode="after")
    @classmethod
    def _uppercase_currency(cls, value: str | None) -> str | None:
        return value.strip().upper() if value else None

    @model_validator(mode="after")
    def _salary_range(self) -> "JobSearchRequest":
        if (
            self.salary_min is not None
            and self.salary_max is not None
            and self.salary_min > self.salary_max
        ):
            raise ValueError("salary_min must be <= salary_max")
        return self


class JobSearchStartResponse(BaseModel):
    search_id: uuid.UUID
    status: JobSearchStatusLiteral


class SourceOutcome(BaseModel):
    source: str
    status: Literal["ok", "failed", "skipped"]
    count: int = 0
    warning: str | None = None


class MatchingOutcome(BaseModel):
    status: Literal["ok", "failed", "skipped"]
    scored_count: int = 0
    rationale_count: int = 0
    rerank_prompt_tokens: int = 0
    rerank_completion_tokens: int = 0
    warning: str | None = None


class JobSearchStatusResponse(BaseModel):
    search_id: uuid.UUID
    status: JobSearchStatusLiteral
    query: dict[str, Any]
    results: list[SourceOutcome] = []
    matching: MatchingOutcome | None = None
    created_at: datetime
    updated_at: datetime


class SourceInfoResponse(BaseModel):
    name: str
    is_official_api: bool
    disclosure_required: bool
    is_configured: bool
    enabled: bool
    supports_exclusions: bool = False


class SourceEnableRequest(BaseModel):
    acknowledged_disclosure: bool = False


class JobPostingSummary(BaseModel):
    id: uuid.UUID
    source: str
    title: str
    company: str | None = None
    url: str | None = None
    location: str | None = None
    posted_at: datetime | None = None
    salary_min: float | None = Field(default=None, ge=0)
    salary_max: float | None = Field(default=None, ge=0)
    currency: str | None = None

    @classmethod
    def from_posting(cls, posting: JobPosting) -> "JobPostingSummary":
        return cls(
            id=posting.id,
            source=posting.source,
            title=posting.title,
            company=posting.company,
            url=posting.url,
            location=posting.location,
            posted_at=posting.posted_at,
            salary_min=float(posting.salary_min) if posting.salary_min is not None else None,
            salary_max=float(posting.salary_max) if posting.salary_max is not None else None,
            currency=posting.currency,
        )
