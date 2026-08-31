from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db
from app.schemas.resume import ResumeUploadResponse
from app.services import resume_service

router = APIRouter(prefix="/api", tags=["resume"])


@router.post("/resume", response_model=ResumeUploadResponse, status_code=201)
async def upload_resume(
    file: Annotated[UploadFile, File(...)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResumeUploadResponse:
    return await resume_service.upload_resume(session, file)
