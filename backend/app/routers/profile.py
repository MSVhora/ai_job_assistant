import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db
from app.schemas.gap_fill import GapFillRequest, GapFillResponse
from app.schemas.profile import (
    ProfileCreate,
    ProfileResponse,
    ProfileSummary,
    ProfileUpdate,
)
from app.services import gap_fill, profile_service

router = APIRouter(prefix="/api", tags=["profile"])


@router.get("/profiles", response_model=list[ProfileSummary])
async def list_profiles(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[ProfileSummary]:
    return await profile_service.list_profiles(session)


@router.post("/profiles", response_model=ProfileResponse, status_code=201)
async def create_profile(
    payload: ProfileCreate,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ProfileResponse:
    return await profile_service.create_profile(session, payload)


@router.get("/profiles/{profile_id}", response_model=ProfileResponse)
async def get_profile(
    profile_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ProfileResponse:
    return await profile_service.get_profile(session, profile_id)


@router.patch("/profiles/{profile_id}", response_model=ProfileResponse)
async def update_profile(
    profile_id: uuid.UUID,
    payload: ProfileUpdate,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ProfileResponse:
    return await profile_service.save_profile(session, profile_id, payload)


@router.post("/profiles/{profile_id}/gap-fill", response_model=GapFillResponse)
async def gap_fill_profile(
    profile_id: uuid.UUID,
    payload: GapFillRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> GapFillResponse:
    return await gap_fill.run_gap_fill_turn(session, profile_id, payload)


@router.delete("/profiles/{profile_id}", status_code=204)
async def delete_profile(
    profile_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    await profile_service.delete_profile(session, profile_id)
