import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

from app.models.evidence import ContentLevel, EvidenceItemStatus, EvidenceKind

__all__ = [
    "EvidenceItemData",
    "EvidenceKind",
    "EvidenceStatusResponse",
    "NoiseVerdict",
    "RateLimitInfo",
    "ScopeCandidate",
    "ScopeResponse",
    "ScopeState",
    "ScopeUpdateItem",
    "ScopeUpdateRequest",
    "SourceIdentity",
    "SyncPage",
    "SyncRequest",
    "SyncRunResponse",
    "SyncStartResponse",
    "TokenCheckResponse",
]


class EvidenceItemData(BaseModel):
    """Normalized evidence from any source (commit, PR, note, ...).

    `meta` carries structured, content-free facts (additions/deletions, parents,
    file paths, author login, labels) — never file contents or patches.
    """

    kind: EvidenceKind
    external_id: str = Field(min_length=1, max_length=255)
    project_key: str | None = None
    title: str | None = None
    body: str
    url: str | None = None
    occurred_at: datetime | None = None
    authored_by_user: bool = True
    meta: dict[str, object] = Field(default_factory=dict)


class NoiseVerdict(BaseModel):
    kept: bool
    reason: str | None = None


class SourceIdentity(BaseModel):
    login: str
    node_id: str | None = None
    emails: list[str] = Field(default_factory=list)
    name: str | None = None
    location: str | None = None
    permissions: list[str] = Field(default_factory=list)


class ScopeCandidate(BaseModel):
    ref: str
    is_private: bool = False
    is_fork: bool = False
    description: str | None = None
    pushed_at: datetime | None = None
    contributed: bool = False
    outside_lookback: bool = False


class ScopeState(BaseModel):
    ref: str
    is_private: bool = False
    content_level: ContentLevel = ContentLevel.messages_and_prs
    cursor: dict[str, object] = Field(default_factory=dict)
    since: datetime | None = None


class RateLimitInfo(BaseModel):
    api: str
    remaining: int | None = None
    limit: int | None = None
    reset_at: datetime | None = None


class SyncPage(BaseModel):
    """One page of normalized items plus the scope cursor to persist with it.

    `requests_used` is the number of requests spent since the previous page.
    """

    items: list[EvidenceItemData] = Field(default_factory=list[EvidenceItemData])
    next_cursor: dict[str, object] | None = None
    requests_used: int = 0
    rate_limits: list[RateLimitInfo] = Field(default_factory=list[RateLimitInfo])


class SyncRequest(BaseModel):
    mode: Literal["incremental", "full"] = "incremental"


class SyncStartResponse(BaseModel):
    sync_id: uuid.UUID
    status: str


class SyncRunResponse(BaseModel):
    id: uuid.UUID
    status: str
    mode: str
    progress: dict[str, object]
    rate_limit: dict[str, object]
    resume_at: datetime | None
    error: str | None
    usage: dict[str, object]
    created_at: datetime
    updated_at: datetime


class EvidenceStatusResponse(BaseModel):
    configured: bool
    login: str | None
    acknowledged_at: datetime | None
    last_synced_at: datetime | None
    scopes_total: int
    scopes_enabled: int
    scopes_unmapped: int = 0
    scopes_refreshed_at: datetime | None = None
    latest_sync: SyncRunResponse | None


class ScopeResponse(BaseModel):
    ref: str
    is_private: bool
    is_fork: bool
    description: str | None
    pushed_at: datetime | None
    enabled: bool
    is_new: bool
    content_level: ContentLevel
    sync_state: str
    last_synced_at: datetime | None
    employer_ref: dict[str, object] | None
    suggested_employer: dict[str, object] | None = None
    contributed: bool = False
    visible: bool = True


class TokenCheckResponse(BaseModel):
    login: str
    token_type: Literal["classic", "fine_grained_or_app"]
    scopes: list[str]
    private_access: bool | None
    warnings: list[str]


class EmployerOption(BaseModel):
    kind: Literal["experience", "personal"]
    label: str
    company: str | None = None
    start_date: str | None = None


class ScopeUpdateItem(BaseModel):
    ref: str = Field(min_length=3, max_length=255)
    enabled: bool | None = None
    content_level: ContentLevel | None = None
    employer_ref: dict[str, object] | None = None


class ScopeUpdateRequest(BaseModel):
    scopes: list[ScopeUpdateItem] = Field(min_length=1, max_length=200)
    acknowledged_disclosure: bool = False


class ItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: EvidenceKind
    external_id: str
    project_key: str | None
    title: str | None
    body: str
    url: str | None
    occurred_at: datetime | None
    authored_by_user: bool
    status: EvidenceItemStatus
    filter_reason: str | None
    is_private: bool
    meta: dict[str, object]
    created_at: datetime
    updated_at: datetime


class ItemUpdate(BaseModel):
    status: Literal["kept", "excluded"]


class NoteCreate(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    body: str = Field(min_length=1, max_length=20_000)


class NoteUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    body: str | None = Field(default=None, min_length=1, max_length=20_000)

    @model_validator(mode="after")
    def _require_a_change(self) -> "NoteUpdate":
        if not self.model_fields_set & {"title", "body"}:
            msg = "send a title or a body to change"
            raise ValueError(msg)
        return self


class LinkCreate(BaseModel):
    url: HttpUrl
    title: str | None = Field(default=None, max_length=200)
    text: str | None = Field(default=None, min_length=1, max_length=20_000)


class ResumeIngestRequest(BaseModel):
    profile_id: uuid.UUID


class ResumeIngestResponse(BaseModel):
    created: int
    unchanged: int
    excluded: int


class ChunkSummaryResponse(BaseModel):
    chunks: int
    tokens: int
    private_chunks: int
    private_share: float
    embedded: int
    pending_embedding: int
    by_kind: dict[str, int]
