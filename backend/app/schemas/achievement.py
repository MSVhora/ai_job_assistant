import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.achievement import AchievementOrigin, AchievementStatus
from app.schemas.cost import CostEstimateResponse

ImpactType = Literal[
    "performance",
    "reliability",
    "revenue",
    "cost",
    "quality",
    "velocity",
    "scale",
    "security",
    "ux",
    "leadership",
    "other",
]
MAX_ACHIEVEMENTS_PER_CHUNK = 3


class MetricClaim(BaseModel):
    text: str = Field(min_length=1, max_length=200)
    source_quote: str = Field(min_length=1, max_length=400)
    evidence_ids: list[str] = Field(default_factory=list[str])


class ExtractedAchievement(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    situation: str = Field(min_length=1)
    task: str = Field(min_length=1)
    action: str = Field(min_length=1)
    result: str | None = None
    result_quote: str | None = None
    metrics: list[MetricClaim] = Field(default_factory=list[MetricClaim])
    skills: list[str] = Field(default_factory=list[str])
    impact_type: ImpactType = "other"
    difficulty: int = 3
    evidence_ids: list[str] = Field(default_factory=list[str])
    time_start: str | None = None
    time_end: str | None = None


class ExtractionBatch(BaseModel):
    achievements: list[ExtractedAchievement] = Field(
        default_factory=list[ExtractedAchievement], max_length=MAX_ACHIEVEMENTS_PER_CHUNK
    )


class EvidenceLinkResponse(BaseModel):
    item_id: uuid.UUID
    role: str
    quote: str | None


class AchievementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: AchievementStatus
    origin: AchievementOrigin
    title: str
    situation: str | None
    task: str | None
    action: str | None
    result: str | None
    metrics: list[dict[str, object]]
    skills: list[str]
    impact_type: str
    difficulty: int
    project_key: str | None
    employer_ref: dict[str, object] | None
    time_start: date | None
    time_end: date | None
    review_flags: list[str]
    derived_from_private: bool
    edited_by_user: bool
    evidence_stale_at: datetime | None
    created_at: datetime
    updated_at: datetime
    evidence: list[EvidenceLinkResponse] = Field(default_factory=list[EvidenceLinkResponse])


class ExtractionEstimateResponse(BaseModel):
    estimate_id: str
    chunks_total: int
    chunks_up_to_date: int
    chunks_cached: int
    chunks_to_extract: int
    llm_cost: CostEstimateResponse
    embedding_cost: CostEstimateResponse
    total_usd: float | None
    private_chunks: int
    private_share: float


class ExtractRequest(BaseModel):
    confirmed_estimate_id: str = Field(min_length=64, max_length=64)


class ExtractionStartResponse(BaseModel):
    run_id: uuid.UUID
    status: str


class ExtractionRunResponse(BaseModel):
    id: uuid.UUID
    status: str
    estimate: dict[str, object]
    progress: dict[str, object]
    usage: dict[str, object]
    error: str | None
    created_at: datetime
    updated_at: datetime
