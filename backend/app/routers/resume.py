import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Response, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import TOTAL_COUNT_HEADER, Pagination
from app.deps import get_db, pagination
from app.schemas.resume import DraftProfileResponse, ResumeSummaryResponse, ResumeUploadResponse
from app.services import profile_extraction, profile_service, resume_service

router = APIRouter(prefix="/api", tags=["resume"])


@router.post("/resumes", response_model=ResumeUploadResponse, status_code=201)
async def upload_resume(
    file: Annotated[UploadFile, File(...)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResumeUploadResponse:
    return await resume_service.upload_resume(session, file)


@router.get("/resumes", response_model=list[ResumeSummaryResponse])
async def list_resumes(
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[Pagination, Depends(pagination())],
) -> list[ResumeSummaryResponse]:
    response.headers[TOTAL_COUNT_HEADER] = str(await resume_service.count_resumes(session))
    return await resume_service.list_resumes(session, page)


@router.post("/resumes/{resume_id}/extract", response_model=DraftProfileResponse)
async def extract_resume(
    resume_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> DraftProfileResponse:
    return await profile_extraction.extract_resume_profile(session, resume_id)


@router.get("/resumes/{resume_id}/draft", response_model=DraftProfileResponse)
async def get_resume_draft(
    resume_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> DraftProfileResponse:
    return await profile_service.get_resume_draft(session, resume_id)
