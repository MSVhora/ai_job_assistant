import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import cast

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.llm import LLMError, LLMTask, UsageMeter, parse_structured, usage_meter
from app.core.errors import AgentSessionNotFoundError, ProfileNotFoundError
from app.core.pagination import DEFAULT_PAGE, Pagination
from app.models import AgentMessage, AgentRole, AgentSession, Profile
from app.schemas.agent import (
    AgentMessageResponse,
    AgentSessionCreate,
    AgentSessionResponse,
    AgentSessionSummary,
    AgentTurnResponse,
    AnswerDraft,
    Citation,
    Grounding,
    QuestionType,
)
from app.services import agent_templates as templates
from app.services.agent_context import job_block, profile_block
from app.services.agent_grounding import Grounded, ground
from app.services.agent_memory import (
    fold_summary,
    load_messages,
    recent_turns,
    standalone_question,
)
from app.services.agent_retrieval import ContextBlock, retrieve
from app.services.agent_router import asks_for_rationale, needs_rewrite, route_question
from app.services.evidence_items import candidate_id_or_none
from app.services.prompts.agent import (
    ANSWER_SYSTEM,
    build_answer_prompt,
    build_repair_prompt,
)

logger = logging.getLogger(__name__)

RATIONALE_CUES = re.compile(
    r"\b(because|so that|in order to|instead of|rather than|trade-?off|to avoid|due to"
    r"|reason|decided|chose|motivated|since)\b",
    re.IGNORECASE,
)
DEFAULT_TITLE = "Interview practice"
TITLE_CHARS = 200


@dataclass
class Reply:
    """What one turn produced, before it is stored."""

    content: str
    kind: QuestionType | None
    citations: list[Citation] = field(default_factory=list[Citation])
    grounding: Grounding = field(default_factory=Grounding)


def _message_response(message: AgentMessage) -> AgentMessageResponse:
    return AgentMessageResponse(
        id=message.id,
        session_id=message.session_id,
        role=message.role.value,
        content=message.content,
        question_type=cast("QuestionType | None", message.question_type),
        citations=[Citation.model_validate(item) for item in message.citations],
        grounding=Grounding.model_validate(message.grounding),
        created_at=message.created_at,
    )


async def owned_session(session: AsyncSession, session_id: uuid.UUID) -> AgentSession:
    candidate_id = await candidate_id_or_none(session)
    row = await session.get(AgentSession, session_id)
    if row is None or candidate_id is None or row.candidate_id != candidate_id:
        raise AgentSessionNotFoundError
    return row


async def create_session(session: AsyncSession, payload: AgentSessionCreate) -> AgentSessionSummary:
    candidate_id = await candidate_id_or_none(session)
    profile = await session.get(Profile, payload.profile_id)
    if profile is None or candidate_id is None or profile.candidate_id != candidate_id:
        raise ProfileNotFoundError
    if payload.match_id is not None:
        await job_block(session, profile.id, payload.match_id)
    row = AgentSession(
        candidate_id=candidate_id,
        profile_id=profile.id,
        match_id=payload.match_id,
        title=(payload.title or DEFAULT_TITLE)[:TITLE_CHARS],
        style_notes=payload.style_notes,
    )
    session.add(row)
    await session.flush()
    await session.refresh(row)
    return AgentSessionSummary.model_validate(row)


async def count_sessions(session: AsyncSession, profile_id: uuid.UUID | None) -> int:
    statement = select(func.count()).select_from(AgentSession)
    if profile_id is not None:
        statement = statement.where(AgentSession.profile_id == profile_id)
    return (await session.execute(statement)).scalar_one()


async def list_sessions(
    session: AsyncSession, profile_id: uuid.UUID | None, page: Pagination = DEFAULT_PAGE
) -> list[AgentSessionSummary]:
    statement = select(AgentSession).order_by(AgentSession.updated_at.desc(), AgentSession.id)
    if profile_id is not None:
        statement = statement.where(AgentSession.profile_id == profile_id)
    rows = await session.execute(statement.limit(page.limit).offset(page.offset))
    return [AgentSessionSummary.model_validate(row) for row in rows.scalars().all()]


async def get_session(session: AsyncSession, session_id: uuid.UUID) -> AgentSessionResponse:
    row = await owned_session(session, session_id)
    messages = await load_messages(session, row.id)
    summary = AgentSessionSummary.model_validate(row)
    return AgentSessionResponse(
        **summary.model_dump(), messages=[_message_response(m) for m in messages]
    )


async def delete_session(session: AsyncSession, session_id: uuid.UUID) -> None:
    row = await owned_session(session, session_id)
    await session.delete(row)


def _citations(blocks: list[ContextBlock], markers: list[str]) -> list[Citation]:
    by_marker = {block.marker: block for block in blocks}
    return [
        Citation(
            marker=marker,
            kind=block.kind,
            achievement_id=block.achievement_id,
            evidence_item_id=block.evidence_item_id,
            url=block.url,
            quote=block.quote,
            private=block.private,
        )
        for marker in markers
        if (block := by_marker.get(marker)) is not None
    ]


def _plain_prompt_blocks(blocks: list[ContextBlock]) -> list[tuple[str, str]]:
    return [(block.marker, block.text) for block in blocks]


def _rationale_missing(question: str, kind: QuestionType, blocks: list[ContextBlock]) -> bool:
    if kind != "technical" or not asks_for_rationale(question):
        return False
    evidence = [block for block in blocks if block.kind in {"achievement", "evidence"}]
    return not any(RATIONALE_CUES.search(part) for block in evidence for part in block.corpus)


def _templated(content: str, kind: QuestionType, *, no_evidence: bool = False) -> Reply:
    grounding = Grounding(status="not_applicable", no_evidence=no_evidence)
    return Reply(content=content, kind=kind, grounding=grounding)


async def _write_answer(
    question: str,
    kind: QuestionType,
    blocks: list[ContextBlock],
    agent_session: AgentSession,
    messages: list[AgentMessage],
    *,
    rationale_missing: bool,
) -> str:
    prompt = build_answer_prompt(
        question=question,
        kind=kind,
        blocks=_plain_prompt_blocks(blocks),
        history=recent_turns(messages),
        summary=agent_session.summary or "",
        style_notes=agent_session.style_notes,
        rationale_missing=rationale_missing,
    )
    result = await parse_structured(
        prompt, schema=AnswerDraft, system=ANSWER_SYSTEM, temperature=0.0, task=LLMTask.write
    )
    return result.data.answer


async def _repair(answer: str, problems: list[str], blocks: list[ContextBlock]) -> str:
    result = await parse_structured(
        build_repair_prompt(answer, problems, _plain_prompt_blocks(blocks)),
        schema=AnswerDraft,
        system=ANSWER_SYSTEM,
        temperature=0.0,
        task=LLMTask.write,
    )
    return result.data.answer


def _finish(
    grounded: Grounded, blocks: list[ContextBlock], kind: QuestionType, *, offer_note: bool
) -> Reply:
    if grounded.status == "refused":
        grounding = Grounding(
            status="refused",
            flagged_sentences=grounded.flagged_sentences,
            repaired=grounded.repaired,
            judge_unavailable=grounded.judge_unavailable,
            no_evidence=True,
        )
        return Reply(content=templates.UNGROUNDED, kind=kind, grounding=grounding)
    citations = _citations(blocks, grounded.markers)
    content = grounded.text
    if offer_note:
        content = f"{content} {templates.NOTE_OFFER}"
    gaps = (
        ["Part of the answer could not be confirmed from your evidence and was left out."]
        if grounded.status == "partial"
        else []
    )
    grounding = Grounding(
        status=grounded.status,
        flagged_sentences=grounded.flagged_sentences,
        gaps=gaps,
        repaired=grounded.repaired,
        used_private=any(citation.private for citation in citations),
        judge_unavailable=grounded.judge_unavailable,
        suggest_note=offer_note,
    )
    return Reply(content=content, kind=kind, citations=citations, grounding=grounding)


async def _respond(
    session: AsyncSession,
    agent_session: AgentSession,
    question: str,
    messages: list[AgentMessage],
) -> Reply:
    routed = await route_question(question)
    kind = routed.kind
    if kind == "out_of_scope":
        return _templated(templates.OUT_OF_SCOPE, kind)
    if kind == "motivation" and agent_session.match_id is None:
        return _templated(templates.NEEDS_JOB, kind)
    history = recent_turns(messages)
    query = question
    if needs_rewrite(question, has_history=bool(history)):
        query = await standalone_question(question, history, agent_session.summary or "")
    retrieval = await retrieve(session, agent_session.candidate_id, query, intro=kind == "intro")
    if retrieval.approved == 0:
        return _templated(templates.NO_APPROVED, kind, no_evidence=True)
    if not retrieval.blocks:
        return _templated(templates.NO_EVIDENCE, kind, no_evidence=True)
    profile = await session.get(Profile, agent_session.profile_id)
    if profile is None:
        raise ProfileNotFoundError
    blocks = [profile_block(profile)]
    if agent_session.match_id is not None:
        job = await job_block(session, agent_session.profile_id, agent_session.match_id)
        if job is not None:
            blocks.append(job)
    blocks.extend(retrieval.blocks)
    missing = _rationale_missing(query, kind, retrieval.blocks)
    answer = await _write_answer(
        question, kind, blocks, agent_session, messages, rationale_missing=missing
    )

    async def repair(previous: str, problems: list[str]) -> str:
        return await _repair(previous, problems, blocks)

    grounded = await ground(answer, blocks, kind=kind, repair=repair)
    return _finish(grounded, blocks, kind, offer_note=missing and grounded.status != "refused")


def _usage(meter: UsageMeter) -> dict[str, object]:
    return {
        "calls": sum(task.calls for task in meter.tasks.values()),
        "prompt_tokens": meter.prompt_tokens,
        "completion_tokens": meter.completion_tokens,
        "cost_usd": meter.cost_usd,
    }


async def answer(session: AsyncSession, session_id: uuid.UUID, question: str) -> AgentTurnResponse:
    """One turn: persist the question, answer it from approved evidence, persist the answer."""
    agent_session = await owned_session(session, session_id)
    earlier = await load_messages(session, agent_session.id)
    user_row = AgentMessage(session_id=agent_session.id, role=AgentRole.user, content=question)
    session.add(user_row)
    await session.flush()
    with usage_meter() as meter:
        try:
            reply = await _respond(session, agent_session, question, earlier)
        except LLMError as exc:
            # The request session rolls back on an exception, which would lose the question, so
            # a model failure is stored as a reply the user can retry from.
            logger.warning("agent.answer failed session_id=%s error=%s", agent_session.id, exc)
            reply = Reply(
                content=templates.UNAVAILABLE,
                kind=None,
                grounding=Grounding(status="refused", error=True),
            )
    user_row.question_type = reply.kind
    agent_session.updated_at = datetime.now(UTC)
    assistant_row = AgentMessage(
        session_id=agent_session.id,
        role=AgentRole.assistant,
        content=reply.content,
        question_type=reply.kind,
        citations=[citation.model_dump(mode="json") for citation in reply.citations],
        grounding=reply.grounding.model_dump(mode="json"),
        usage=_usage(meter),
    )
    session.add(assistant_row)
    await session.flush()
    await fold_summary(agent_session, [*earlier, user_row, assistant_row])
    logger.info(
        "agent.answer session_id=%s type=%s status=%s citations=%d",
        agent_session.id,
        reply.kind,
        reply.grounding.status,
        len(reply.citations),
    )
    await session.refresh(user_row)
    await session.refresh(assistant_row)
    return AgentTurnResponse(
        user_message=_message_response(user_row), assistant_message=_message_response(assistant_row)
    )
