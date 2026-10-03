from collections.abc import AsyncIterator
from datetime import datetime
from typing import Protocol

from app.schemas.evidence import (
    EvidenceItemData,
    ScopeCandidate,
    ScopeState,
    SourceIdentity,
    SyncPage,
)

RawEvidence = dict[str, object]


class EvidenceSourceError(Exception):
    pass


class EvidenceSourceConfigError(EvidenceSourceError):
    pass


class EvidenceSourcePausedError(EvidenceSourceError):
    """The run must stop and resume later (request budget, rate-limit floor, long Retry-After)."""

    def __init__(self, reason: str, resume_at: datetime | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.resume_at = resume_at


class EvidenceSource(Protocol):
    """Stateful, incremental evidence connector (sibling of `JobSource`).

    Lifecycle: `identify` → `list_scopes` → `sync_scope` per opted-in scope,
    resumable through the scope cursor carried by each `SyncPage`.
    """

    name: str

    def is_configured(self) -> bool: ...

    async def identify(self) -> SourceIdentity: ...

    async def list_scopes(self) -> list[ScopeCandidate]: ...

    def sync_scope(self, scope: ScopeState) -> AsyncIterator[SyncPage]: ...

    def normalize(self, raw: RawEvidence) -> EvidenceItemData: ...
