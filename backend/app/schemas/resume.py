import uuid
from datetime import datetime

from pydantic import BaseModel

from app.schemas.job_search import StoredSearchQueries
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
    search_queries: StoredSearchQueries | None = None


class ResumeSummaryResponse(BaseModel):
    resume_id: uuid.UUID
    original_filename: str
    content_type: str
    size_bytes: int
    page_count: int | None
    created_at: datetime
    parsed_at: datetime | None
    parse_version: str | None
    has_draft: bool
    source_profile_names: list[str]
