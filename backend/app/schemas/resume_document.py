import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.profile import SourceLink

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


class Bullet(BaseModel):
    text: str = Field(min_length=1)
    achievement_id: uuid.UUID | None = None
    evidence_ids: list[uuid.UUID] = []
    metric_ids: list[str] = []
    from_private: bool = False
    score: float = 0.0
    origin: BulletOrigin = "generated"
    check: BulletCheck = "passed"


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


class ResumeDocumentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=200)
    page_target: int | None = Field(default=None, ge=1, le=4)
    template: str | None = Field(default=None, min_length=1, max_length=50)
    status: DocumentStatus | None = None
    content: ResumeContent | None = None


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
    comments: list[dict[str, object]]
    created_at: datetime
