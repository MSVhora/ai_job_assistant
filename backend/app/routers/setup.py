from fastapi import APIRouter

from app.schemas.setup import SetupCheckResponse
from app.services import setup

router = APIRouter(prefix="/api", tags=["setup"])


@router.post("/setup/check", response_model=SetupCheckResponse)
async def setup_check() -> SetupCheckResponse:
    return setup.check()
