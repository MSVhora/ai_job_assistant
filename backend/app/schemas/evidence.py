from datetime import datetime

from pydantic import BaseModel, Field

from app.models.evidence import ContentLevel, EvidenceKind

__all__ = [
    "EvidenceItemData",
    "EvidenceKind",
    "NoiseVerdict",
    "ScopeCandidate",
    "ScopeState",
    "SourceIdentity",
    "SyncPage",
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
    emails: list[str] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)


class ScopeCandidate(BaseModel):
    ref: str
    is_private: bool = False
    is_fork: bool = False
    description: str | None = None
    pushed_at: datetime | None = None


class ScopeState(BaseModel):
    ref: str
    is_private: bool = False
    content_level: ContentLevel = ContentLevel.messages_and_prs
    cursor: dict[str, object] = Field(default_factory=dict)
    since: datetime | None = None


class SyncPage(BaseModel):
    items: list[EvidenceItemData] = Field(default_factory=list[EvidenceItemData])
    next_cursor: dict[str, object] | None = None
    requests_used: int = 0
