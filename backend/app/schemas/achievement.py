import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

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
    chunks_skipped_short: int = 0
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


class AchievementUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    situation: str | None = None
    task: str | None = None
    action: str | None = None
    result: str | None = None
    skills: list[str] | None = Field(default=None, max_length=30)
    impact_type: ImpactType | None = None
    difficulty: int | None = Field(default=None, ge=1, le=5)
    project_key: str | None = Field(default=None, max_length=255)
    # An employer you choose here outranks the repository's mapping; null clears the choice so
    # the achievement follows its repository's employer again.
    employer_ref: dict[str, object] | None = None
    time_start: date | None = None
    time_end: date | None = None

    @model_validator(mode="after")
    def _require_a_change(self) -> "AchievementUpdate":
        if not self.model_fields_set:
            msg = "send at least one field to change"
            raise ValueError(msg)
        if "title" in self.model_fields_set and self.title is None:
            msg = "title cannot be cleared"
            raise ValueError(msg)
        return self


class EvidenceLinkCreate(BaseModel):
    item_id: uuid.UUID
    role: Literal["primary", "supporting"] = "supporting"
    quote: str | None = Field(default=None, max_length=500)


class ConfirmMetricRequest(BaseModel):
    index: int = Field(ge=0)
    mode: Literal["as_written", "edit"]
    text: str | None = Field(default=None, min_length=1, max_length=200)

    @model_validator(mode="after")
    def _edit_needs_text(self) -> "ConfirmMetricRequest":
        if self.mode == "edit" and self.text is None:
            msg = "text is required when editing a metric"
            raise ValueError(msg)
        return self


class MergeRequest(BaseModel):
    ids: list[uuid.UUID] = Field(min_length=2, max_length=10)
    title: str | None = Field(default=None, min_length=1, max_length=200)
    situation: str | None = None
    task: str | None = None
    action: str | None = None
    result: str | None = None


class SplitRequest(BaseModel):
    evidence_item_ids: list[uuid.UUID] = Field(min_length=1, max_length=50)
    title: str | None = Field(default=None, min_length=1, max_length=200)


class AddImpactRequest(BaseModel):
    text: str = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def _not_blank(self) -> "AddImpactRequest":
        self.text = self.text.strip()
        if not self.text:
            msg = "describe the measurable outcome"
            raise ValueError(msg)
        return self


class BulkApproveRequest(BaseModel):
    ids: list[uuid.UUID] = Field(min_length=1, max_length=1000)


class BulkEligibleItem(BaseModel):
    id: uuid.UUID
    title: str
    evidence_count: int


class BulkEligibleResponse(BaseModel):
    count: int
    items: list[BulkEligibleItem]


class BulkSkipped(BaseModel):
    id: uuid.UUID
    reasons: list[str]


class BulkApproveResponse(BaseModel):
    approved: list[uuid.UUID]
    skipped: list[BulkSkipped]


class BulkTransitionResponse(BaseModel):
    done: list[uuid.UUID]
    skipped: list[BulkSkipped]


class RepositoryGroup(BaseModel):
    project_key: str | None
    total: int
    eligible: int
    draft_ids: list[uuid.UUID]
    eligible_ids: list[uuid.UUID]


class EmployerGroup(BaseModel):
    kind: Literal["employer", "personal", "unassigned"]
    label: str
    total: int
    eligible: int
    repositories: list[RepositoryGroup]


class AchievementGroupsResponse(BaseModel):
    groups: list[EmployerGroup]


class RetirePreview(BaseModel):
    prompt_version: str
    would_archive: int
    kept_edited: int
    kept_not_reextracted: int


class RetireOlderResult(BaseModel):
    archived: int


class RevisionResponse(BaseModel):
    id: uuid.UUID
    source: str
    diff: dict[str, object]
    created_at: datetime


class MergeProposalResponse(BaseModel):
    first_id: uuid.UUID
    first_title: str
    second_id: uuid.UUID
    second_title: str
    project_key: str | None
    similarity: float
