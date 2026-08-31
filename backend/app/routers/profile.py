from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db
from app.schemas.profile import ProfileResponse, ProfileUpdateRequest
from app.services import profile_service

router = APIRouter(prefix="/api", tags=["profile"])


@router.get("/profile", response_model=ProfileResponse)
async def get_profile(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ProfileResponse:
    return await profile_service.get_profile(session)


@router.patch("/profile", response_model=ProfileResponse)
async def update_profile(
    payload: ProfileUpdateRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ProfileResponse:
    return await profile_service.save_profile(session, payload)
