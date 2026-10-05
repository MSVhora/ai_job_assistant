import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

QuestionType = Literal[
    "intro", "behavioral", "technical", "motivation", "hypothetical", "out_of_scope"
]
GroundingStatus = Literal["grounded", "partial", "refused", "not_applicable"]
CitationKind = Literal["achievement", "evidence", "profile", "job"]
MessageRole = Literal["user", "assistant"]

MAX_QUESTION_CHARS = 2000
MAX_STYLE_NOTES_CHARS = 600


class AgentSessionCreate(BaseModel):
    profile_id: uuid.UUID
    match_id: uuid.UUID | None = None
    style_notes: str | None = Field(default=None, max_length=MAX_STYLE_NOTES_CHARS)
    title: str | None = Field(default=None, min_length=1, max_length=200)


class AgentMessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=MAX_QUESTION_CHARS)


class Citation(BaseModel):
    marker: str
    kind: CitationKind
    achievement_id: uuid.UUID | None = None
    evidence_item_id: uuid.UUID | None = None
    url: str | None = None
    quote: str | None = None
    private: bool = False


class Grounding(BaseModel):
    status: GroundingStatus = "not_applicable"
    flagged_sentences: list[str] = Field(default_factory=list[str])
    gaps: list[str] = Field(default_factory=list[str])
    repaired: bool = False
    used_private: bool = False
    judge_unavailable: bool = False
    no_evidence: bool = False
    suggest_note: bool = False
    error: bool = False


class AgentMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    session_id: uuid.UUID
    role: MessageRole
    content: str
    question_type: QuestionType | None = None
    citations: list[Citation] = Field(default_factory=list[Citation])
    grounding: Grounding = Field(default_factory=Grounding)
    created_at: datetime


class AgentSessionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    profile_id: uuid.UUID
    match_id: uuid.UUID | None
    title: str
    style_notes: str | None
    created_at: datetime
    updated_at: datetime


class AgentSessionResponse(AgentSessionSummary):
    messages: list[AgentMessageResponse] = Field(default_factory=list[AgentMessageResponse])


class AgentTurnResponse(BaseModel):
    user_message: AgentMessageResponse
    assistant_message: AgentMessageResponse


class QuestionClass(BaseModel):
    """Output of the fallback classifier."""

    type: QuestionType


class AnswerDraft(BaseModel):
    """The answer model's output: prose with inline `[A1]`/`[E1]`/`[P]`/`[J]` markers."""

    answer: str = Field(default="", max_length=6000)
    gaps: list[str] = Field(default_factory=list[str], max_length=8)


class SentenceVerdict(BaseModel):
    index: int = Field(ge=0)
    entailed: bool
    reason: str | None = None


class AnswerVerdicts(BaseModel):
    verdicts: list[SentenceVerdict] = Field(default_factory=list[SentenceVerdict], max_length=24)


class ConversationSummary(BaseModel):
    summary: str = Field(default="", max_length=1500)
