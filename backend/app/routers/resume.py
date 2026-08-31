import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db
from app.schemas.resume import DraftProfileResponse, ResumeUploadResponse
from app.services import profile_extraction, resume_service

router = APIRouter(prefix="/api", tags=["resume"])


@router.post("/resume", response_model=ResumeUploadResponse, status_code=201)
async def upload_resume(
    file: Annotated[UploadFile, File(...)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResumeUploadResponse:
    return await resume_service.upload_resume(session, file)


@router.post("/resume/{resume_id}/extract", response_model=DraftProfileResponse)
async def extract_resume(
    resume_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> DraftProfileResponse:
    return await profile_extraction.extract_resume_profile(session, resume_id)
