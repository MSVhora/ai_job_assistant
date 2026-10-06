import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

KeywordPriority = Literal["critical", "important", "nice_to_have"]
SuggestionPriority = Literal["high", "medium", "low"]

_KEYWORD_PRIORITIES = frozenset({"critical", "important", "nice_to_have"})
_SUGGESTION_PRIORITIES = frozenset({"high", "medium", "low"})


def _normalize_enumerated(value: object, allowed: frozenset[str], fallback: str) -> object:
    if not isinstance(value, str):
        return value
    cleaned = value.strip().lower().replace(" ", "_").replace("-", "_")
    if cleaned in allowed:
        return cleaned
    return fallback


def _clamp_text(value: object, limit: int) -> object:
    if isinstance(value, str) and len(value) > limit:
        return value[:limit].rstrip()
    return value


MAX_JD_CHARS = 15000


class AtsScoreRequest(BaseModel):
    resume_id: uuid.UUID | None = None
    profile_id: uuid.UUID | None = None
    job_description: str = Field(min_length=50, max_length=MAX_JD_CHARS)

    @model_validator(mode="after")
    def require_exactly_one_source(self) -> "AtsScoreRequest":
        if (self.resume_id is None) == (self.profile_id is None):
            raise ValueError("provide exactly one of resume_id or profile_id")
        return self


class AtsCategoryScore(BaseModel):
    """One scored ATS category (format, keyword alignment, ...)."""

    name: str = Field(min_length=1, max_length=80)
    score: float = Field(ge=0, le=100, description="0-100 for this category")
    weight: float = Field(ge=0, le=1, description="contribution weight of this category")
    analysis: str = Field(min_length=1, max_length=1200)
    issues: list[str] = []

    @field_validator("analysis", mode="before")
    @classmethod
    def _clamp_analysis(cls, value: object) -> object:
        return _clamp_text(value, 1200)


class AtsKeywordHit(BaseModel):
    keyword: str = Field(min_length=1, max_length=120)
    priority: KeywordPriority = "nice_to_have"

    @field_validator("priority", mode="before")
    @classmethod
    def _normalize(cls, value: object) -> object:
        # "must have" → critical; unknown phrasing falls back to important.
        critical_phrases = {"must_have", "must have", "required"}
        if isinstance(value, str) and value.strip().lower() in critical_phrases:
            return "critical"
        return _normalize_enumerated(value, _KEYWORD_PRIORITIES, "important")


_SUGGESTION_AREAS = frozenset({"keywords", "format", "summary", "skills", "experience", "other"})


class AtsSuggestion(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    area: Literal["keywords", "format", "summary", "skills", "experience", "other"] = "other"
    detail: str = Field(min_length=1, max_length=1200)
    rewrite_example: str | None = Field(default=None, max_length=2000)
    priority: SuggestionPriority = "medium"

    @field_validator("priority", mode="before")
    @classmethod
    def _normalize_priority(cls, value: object) -> object:
        return _normalize_enumerated(value, _SUGGESTION_PRIORITIES, "medium")

    @field_validator("area", mode="before")
    @classmethod
    def _normalize_area(cls, value: object) -> object:
        return _normalize_enumerated(value, _SUGGESTION_AREAS, "other")

    @field_validator("detail", mode="before")
    @classmethod
    def _clamp_detail(cls, value: object) -> object:
        return _clamp_text(value, 1200)

    @field_validator("rewrite_example", mode="before")
    @classmethod
    def _clamp_rewrite(cls, value: object) -> object:
        return _clamp_text(value, 2000)


class AtsScoreResponse(BaseModel):
    source_resume_id: uuid.UUID | None
    source_profile_id: uuid.UUID | None
    overall_score: float = Field(ge=0, le=100)
    verdict: str = Field(default="Mixed match", min_length=1, max_length=200)
    summary: str = Field(min_length=1, max_length=1600)
    categories: list[AtsCategoryScore]
    matched_keywords: list[AtsKeywordHit]
    missing_keywords: list[AtsKeywordHit]
    strengths: list[str]
    gaps: list[str]
    suggestions: list[AtsSuggestion]
    prompt_version: str = "ats_prompt_v1"
    generated_at: datetime

    @field_validator("verdict", mode="before")
    @classmethod
    def _clamp_verdict(cls, value: object) -> object:
        # LLMs write full sentences; keep them intact, only guard the hard cap.
        return _clamp_text(value, 200)

    @field_validator("summary", mode="before")
    @classmethod
    def _clamp_summary(cls, value: object) -> object:
        return _clamp_text(value, 1600)
