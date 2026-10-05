import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import TOTAL_COUNT_HEADER, Pagination
from app.deps import get_db, pagination
from app.schemas.agent import (
    AgentMessageCreate,
    AgentSessionCreate,
    AgentSessionResponse,
    AgentSessionSummary,
    AgentTurnResponse,
)
from app.services import agent

router = APIRouter(prefix="/api/agent", tags=["agent"])


@router.post("/sessions", response_model=AgentSessionSummary, status_code=201)
async def create_agent_session(
    payload: AgentSessionCreate,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AgentSessionSummary:
    return await agent.create_session(session, payload)


@router.get("/sessions", response_model=list[AgentSessionSummary])
async def list_agent_sessions(
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[Pagination, Depends(pagination())],
    profile_id: Annotated[uuid.UUID | None, Query()] = None,
) -> list[AgentSessionSummary]:
    total = await agent.count_sessions(session, profile_id)
    response.headers[TOTAL_COUNT_HEADER] = str(total)
    return await agent.list_sessions(session, profile_id, page)


@router.get("/sessions/{session_id}", response_model=AgentSessionResponse)
async def get_agent_session(
    session_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AgentSessionResponse:
    return await agent.get_session(session, session_id)


@router.delete("/sessions/{session_id}", status_code=204)
async def delete_agent_session(
    session_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    await agent.delete_session(session, session_id)
    return Response(status_code=204)


@router.post("/sessions/{session_id}/messages", response_model=AgentTurnResponse)
async def send_agent_message(
    session_id: uuid.UUID,
    payload: AgentMessageCreate,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AgentTurnResponse:
    return await agent.answer(session, session_id, payload.content)
