from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.profile import RevisionSummary, StructuredProfile

GapFillStatus = Literal["in_progress", "complete"]


class GapFillMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=2000)


class GapFillRequest(BaseModel):
    messages: list[GapFillMessage] = Field(default=[], max_length=30)


class GapFillField(BaseModel):
    key: str
    label: str


class GapFillAppliedField(BaseModel):
    field: str
    label: str
    value: str


class GapFillResponse(BaseModel):
    reply: str
    status: GapFillStatus
    missing_fields: list[GapFillField]
    applied_fields: list[GapFillAppliedField]
    structured_profile: StructuredProfile
    revision: RevisionSummary | None = None
