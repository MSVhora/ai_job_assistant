import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.models import JobType, RemoteType
from app.schemas.job_search import JobPostingSummary, MatchingOutcome

_MAX_LOCATION = 200
_MAX_RATIONALE = 600

MatchSort = Literal["final_score", "vector_score", "posted_at"]

__all__ = [
    "MatchFilters",
    "MatchQueryParams",
    "MatchRebuildStatusResponse",
    "MatchResponse",
    "MatchSort",
    "RerankItem",
    "RerankResult",
    "MatchingOutcome",
]


class MatchRebuildStatusResponse(BaseModel):
    """Rebuild-run status; `id=None`, `status="idle"` when the profile never rebuilt.

    `stale_count` is computed at read time: stored matches whose posting is
    outside the profile's scoped corpus — the discrepancy the rebuild cleans.
    """

    id: uuid.UUID | None = None
    profile_id: uuid.UUID
    status: Literal["idle", "pending", "running", "succeeded", "failed"]
    stale_count: int
    corpus_count: int
    scored_count: int
    warning: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


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


class MatchQueryParams(MatchFilters):
    profile_id: uuid.UUID
    priority: float | None = Field(
        default=None,
        ge=0,
        le=1,
        description=(
            "role-fit vs company-fit weighting (1 = role-fit only); "
            "falls back to the profile's stored preference, then the server default"
        ),
    )
    sort: MatchSort = "final_score"
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)


class RerankItem(BaseModel):
    posting_id: uuid.UUID
    role_fit: float = Field(ge=0, le=10)
    company_fit: float = Field(ge=0, le=10)
    rationale: str = Field(min_length=1)


class RerankResult(BaseModel):
    items: list[RerankItem] = Field(default_factory=list)


class MatchResponse(BaseModel):
    id: uuid.UUID
    job_posting: JobPostingSummary
    vector_score: float | None = None
    skill_score: float | None = None
    recency_score: float | None = None
    salary_score: float | None = None
    role_fit: float | None = None
    company_fit: float | None = None
    final_score: float
    rationale: str | None = Field(default=None, max_length=_MAX_RATIONALE)
    created_at: datetime
    updated_at: datetime
