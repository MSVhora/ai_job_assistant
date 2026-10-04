import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.profile import SourceLink

MAX_JD_CHARS = 20_000
BulletOrigin = Literal["generated", "profile_verbatim", "user_edited"]
BulletCheck = Literal["passed", "needs_review", "failed"]
ConflictKind = Literal[
    "date_outside_employment",
    "employer_not_in_profile",
    "identity_mismatch",
    "skill_missing_in_profile",
    "skill_without_evidence",
    "metric_contradiction",
    "overlapping_roles",
]
ConflictSeverity = Literal["info", "warning", "error"]
ConflictAction = Literal["edit_profile", "keep_as_is"]
DocumentStatus = Literal["draft", "final"]
NotIncludedReason = Literal["did_not_fit", "needs_review", "overlap_omitted", "not_written"]
TailoringStrength = Literal["light", "balanced", "strong"]
ResumeTemplate = Literal["classic", "compact"]
CommentSection = Literal["work", "projects"]
CommentStatus = Literal["open", "applied", "rejected"]


class Bullet(BaseModel):
    id: str = ""
    text: str = Field(min_length=1)
    achievement_id: uuid.UUID | None = None
    evidence_ids: list[uuid.UUID] = []
    metric_ids: list[str] = []
    from_private: bool = False
    score: float = 0.0
    origin: BulletOrigin = "generated"
    check: BulletCheck = "passed"
    pinned: bool = False
    approved_anyway: bool = False
    flags: list[str] = []


class Basics(BaseModel):
    full_name: str = Field(min_length=1)
    label: str | None = Field(default=None, description="the profile headline")
    summary: str | None = None
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    country: str | None = None
    links: list[SourceLink] = []


class WorkEntry(BaseModel):
    id: str = ""
    company: str | None = None
    title: str | None = None
    location: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    is_current: bool = False
    highlights: list[Bullet] = []


class EducationEntry(BaseModel):
    institution: str | None = None
    degree: str | None = None
    field: str | None = None
    start_date: str | None = None
    end_date: str | None = None


class ProjectEntry(BaseModel):
    id: str = ""
    name: str
    role: str | None = None
    url: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    description: str | None = None
    technologies: list[str] = []
    highlights: list[Bullet] = []


class AwardEntry(BaseModel):
    title: str
    issuer: str | None = None
    issued_date: str | None = None


class CertificateEntry(BaseModel):
    name: str
    issuer: str | None = None
    issued_date: str | None = None


class ExtraEntry(BaseModel):
    title: str = Field(min_length=1)
    entries: list[str] = Field(min_length=1)


class ResumeContent(BaseModel):
    """JSON Resume-shaped sections whose highlights are provenance-carrying `Bullet`s.

    Field names follow `StructuredProfile` so the mapping is lossless; the JSON Resume
    field names (`name`, `position`, `highlights` as strings, ...) are produced by export.
    """

    basics: Basics
    skills: list[str] = []
    work: list[WorkEntry] = []
    education: list[EducationEntry] = []
    projects: list[ProjectEntry] = []
    awards: list[AwardEntry] = []
    certificates: list[CertificateEntry] = []
    extra_sections: list[ExtraEntry] = []


class NotIncluded(BaseModel):
    id: str
    priority: float = 0.0
    reason: NotIncludedReason


class Layout(BaseModel):
    pages: int | None = None
    preset: str | None = None
    font_pt: float | None = None
    margin_in: float | None = None
    included_ids: list[str] = []
    not_included: list[NotIncluded] = []
    steps: list[str] = []
    short_on_evidence: bool = False


class Conflict(BaseModel):
    key: str
    kind: ConflictKind
    severity: ConflictSeverity
    message: str
    refs: dict[str, str] = {}
    suggested_actions: list[ConflictAction] = []


class ConflictResolution(BaseModel):
    key: str
    action: Literal["keep_as_is"] = "keep_as_is"
    resolved_at: datetime


class ConflictsResponse(BaseModel):
    open: list[Conflict]
    resolved: list[Conflict]
    github_checked: bool
    note: str | None = None


class ResolveConflictRequest(BaseModel):
    action: Literal["keep_as_is", "reopen"]


class ResumeDocumentCreate(BaseModel):
    profile_id: uuid.UUID
    title: str | None = Field(default=None, min_length=1, max_length=200)
    page_target: int = Field(default=1, ge=1, le=4)
    match_id: uuid.UUID | None = None
    template: ResumeTemplate = "classic"
    job_description: str | None = Field(default=None, min_length=1, max_length=MAX_JD_CHARS)
    tailoring_strength: TailoringStrength = "balanced"
    exclude_private: bool = False

    @model_validator(mode="after")
    def _one_jd_source(self) -> "ResumeDocumentCreate":
        if self.job_description is not None and self.match_id is not None:
            msg = "send either job_description or match_id, not both"
            raise ValueError(msg)
        return self


class ResumeDocumentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=200)
    page_target: int | None = Field(default=None, ge=1, le=4)
    template: ResumeTemplate | None = None
    status: DocumentStatus | None = None
    content: ResumeContent | None = None


class CommentTarget(BaseModel):
    section: CommentSection
    block_id: str = Field(min_length=1, max_length=64)
    bullet_id: str | None = Field(default=None, min_length=1, max_length=64)


class CommentCreate(BaseModel):
    target: CommentTarget
    text: str = Field(min_length=1, max_length=1000)


class CommentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=1000)


class ResumeComment(BaseModel):
    id: str
    target: CommentTarget
    text: str
    status: CommentStatus = "open"
    reason: str | None = None
    action: Literal["add_note"] | None = None
    created_at: datetime
    resolved_at: datetime | None = None


class BulletUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str | None = Field(default=None, min_length=1, max_length=600)
    pinned: bool | None = None


class RegenerateRequest(BaseModel):
    block_id: str | None = Field(default=None, min_length=1, max_length=64)


class JDAnalysis(BaseModel):
    must_haves: list[str] = Field(default_factory=list[str], max_length=15)
    nice_to_haves: list[str] = Field(default_factory=list[str], max_length=15)
    keywords: list[str] = Field(default_factory=list[str], max_length=30)
    seniority: str | None = None
    domain: str | None = None


class PoolEntry(BaseModel):
    achievement_id: uuid.UUID
    block_id: str
    title: str
    priority: float
    rank: int
    written: bool = False


class OmittedRole(BaseModel):
    block_id: str
    company: str | None
    title: str | None
    priority: float
    overlaps_with: str | None
    reason: str
    position: int = 0
    entry: WorkEntry


class GapItem(BaseModel):
    requirement: str
    nearest_evidence: str | None = None
    nearest_achievement_id: uuid.UUID | None = None
    action: Literal["add_note"] = "add_note"


class GenerationUsage(BaseModel):
    calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float | None = None
    cache_hits: int = 0
    cache_misses: int = 0


class Generation(BaseModel):
    """What a content run produced besides the content: the ranked pool, dropped roles, gaps."""

    tailoring_strength: TailoringStrength = "balanced"
    exclude_private: bool = False
    jd: JDAnalysis | None = None
    pool: list[PoolEntry] = []
    omitted_roles: list[OmittedRole] = []
    included_roles: list[str] = []
    gaps: list[GapItem] = []
    warnings: list[str] = []
    unplaced_count: int = 0
    private_bullet_count: int = 0
    usage: GenerationUsage = GenerationUsage()


class ResumeDocumentSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    profile_id: uuid.UUID
    match_id: uuid.UUID | None
    title: str
    page_target: int
    status: DocumentStatus
    version: int
    updated_at: datetime


class ResumeDocumentResponse(ResumeDocumentSummary):
    jd_weight: float
    template: str
    content: ResumeContent
    layout: Layout
    comments: list[ResumeComment]
    generation: Generation
    created_at: datetime
