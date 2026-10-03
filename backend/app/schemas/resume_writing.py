from pydantic import BaseModel, Field

MAX_BULLETS_PER_CALL = 8


class BulletDraft(BaseModel):
    key: str = Field(min_length=1, max_length=20)
    text: str = Field(default="", max_length=600)
    evidence_ids: list[str] = Field(default_factory=list[str])
    unsupported_reason: str | None = None


class BulletBatch(BaseModel):
    bullets: list[BulletDraft] = Field(default_factory=list[BulletDraft], max_length=16)


class Verdict(BaseModel):
    key: str = Field(min_length=1, max_length=20)
    entailed: bool
    reason: str | None = None


class Verdicts(BaseModel):
    verdicts: list[Verdict] = Field(default_factory=list[Verdict], max_length=16)
