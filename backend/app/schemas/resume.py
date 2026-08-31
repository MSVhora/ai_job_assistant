import uuid
from datetime import datetime

from pydantic import BaseModel


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
