import uuid
from datetime import datetime

from pydantic import BaseModel

from app.schemas.profile import StructuredProfile


class ResumeUploadResponse(BaseModel):
    resume_id: uuid.UUID
    candidate_id: uuid.UUID
    original_filename: str
    content_type: str
    size_bytes: int
    extracted_text: str
    page_count: int | None
    parsed_at: datetime
    parse_version: str


class DraftProfileResponse(BaseModel):
    resume_id: uuid.UUID
    candidate_id: uuid.UUID
    draft_profile: StructuredProfile
    parse_version: str
    parsed_at: datetime
