import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.llm import LLMError, LLMTask, UsageMeter, parse_structured, usage_meter
from app.core.errors import AgentSessionNotFoundError, ProfileNotFoundError
from app.core.pagination import DEFAULT_PAGE, Pagination
from app.models import AgentMessage, AgentRole, AgentSession, JobPosting, Match, Profile
from app.schemas.agent import (
    AgentMessageResponse,
    AgentSessionCreate,
    AgentSessionResponse,
    AgentSessionSummary,
    AgentTurnResponse,
    AnswerDraft,
    Citation,
    Grounding,
    PinnedJob,
)
from app.services import agent_templates as templates
from app.services.agent_context import job_block, profile_block
from app.services.agent_grounding import Grounded, ground, markers_in
from app.services.agent_memory import (
    fold_summary,
    load_messages,
    recent_turns,
    standalone_question,
)
from app.services.agent_retrieval import ContextBlock, retrieve
from app.services.evidence_items import candidate_id_or_none
from app.services.prompts.agent import (
    ANSWER_SYSTEM,
    build_answer_prompt,
    build_repair_prompt,
)

logger = logging.getLogger(__name__)

DEFAULT_TITLE = "New chat"
TITLE_CHARS = 200
AUTO_TITLE_CHARS = 60
FOLLOW_UP = re.compile(
    r"\b(that|this|those|these|it|its|they|them|there|the (project|team|system|service|tool))\b"
    r"|^(why|how|and|what about|so|then)\b",
    re.IGNORECASE,
)
MAX_FOLLOW_UP_WORDS = 8


@dataclass
class Reply:
    """What one turn produced, before it is stored."""

    content: str
    citations: list[Citation] = field(default_factory=list[Citation])
    grounding: Grounding = field(default_factory=Grounding)


def _message_response(message: AgentMessage) -> AgentMessageResponse:
    return AgentMessageResponse(
        id=message.id,
        session_id=message.session_id,
        role=message.role.value,
        content=message.content,
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
        **summary.model_dump(),
        summary=row.summary,
        job=await _pinned_job(session, row),
        messages=[_message_response(m) for m in messages],
    )


async def _pinned_job(session: AsyncSession, row: AgentSession) -> PinnedJob | None:
    if row.match_id is None:
        return None
    match = await session.get(Match, row.match_id)
    posting = await session.get(JobPosting, match.job_posting_id) if match else None
    if match is None or posting is None:
        return None
    return PinnedJob(
        title=posting.title, company=posting.company, url=posting.url, rationale=match.rationale
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
            label=block.label,
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


def _needs_rewrite(question: str, *, has_history: bool) -> bool:
    """A follow-up refers back to the conversation ("why?", "that project")."""
    if not has_history:
        return False
    return FOLLOW_UP.search(question) is not None or len(question.split()) <= MAX_FOLLOW_UP_WORDS


async def _write_answer(
    question: str,
    blocks: list[ContextBlock],
    agent_session: AgentSession,
    messages: list[AgentMessage],
) -> str:
    prompt = build_answer_prompt(
        question=question,
        blocks=_plain_prompt_blocks(blocks),
        history=recent_turns(messages),
        summary=agent_session.summary or "",
        style_notes=agent_session.style_notes,
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


def _finish(grounded: Grounded, blocks: list[ContextBlock]) -> Reply:
    citations = _citations(blocks, grounded.markers)
    if grounded.status == "refused" or not citations:
        grounding = Grounding(
            status="refused" if grounded.status == "refused" else "not_applicable",
            flagged_sentences=grounded.flagged_sentences,
            repaired=grounded.repaired,
            judge_unavailable=grounded.judge_unavailable,
            no_evidence=True,
        )
        cited_claims = any(markers_in(sentence) for sentence in grounded.flagged_sentences)
        content = templates.UNGROUNDED if cited_claims else templates.NO_EVIDENCE
        return Reply(content=content, grounding=grounding)
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
    )
    return Reply(content=grounded.text, citations=citations, grounding=grounding)


async def _respond(
    session: AsyncSession,
    agent_session: AgentSession,
    question: str,
    messages: list[AgentMessage],
) -> Reply:
    history = recent_turns(messages)
    query = question
    if _needs_rewrite(question, has_history=bool(history)):
        query = await standalone_question(question, history, agent_session.summary or "")
    retrieval = await retrieve(session, agent_session.candidate_id, query)
    profile = await session.get(Profile, agent_session.profile_id)
    if profile is None:
        raise ProfileNotFoundError
    blocks = [profile_block(profile)]
    if agent_session.match_id is not None:
        job = await job_block(session, agent_session.profile_id, agent_session.match_id)
        if job is not None:
            blocks.append(job)
    blocks.extend(retrieval.blocks)
    answer = await _write_answer(question, blocks, agent_session, messages)

    async def repair(previous: str, problems: list[str]) -> str:
        return await _repair(previous, problems, blocks)

    return _finish(await ground(answer, blocks, repair=repair), blocks)


def _title_from(question: str) -> str:
    text = " ".join(question.split())
    if len(text) <= AUTO_TITLE_CHARS:
        return text
    return text[:AUTO_TITLE_CHARS].rsplit(" ", 1)[0].rstrip(".,;:?!") + "…"


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
                grounding=Grounding(status="refused", error=True),
            )
    agent_session.updated_at = datetime.now(UTC)
    if agent_session.title == DEFAULT_TITLE:
        agent_session.title = _title_from(question)
    assistant_row = AgentMessage(
        session_id=agent_session.id,
        role=AgentRole.assistant,
        content=reply.content,
        citations=[citation.model_dump(mode="json") for citation in reply.citations],
        grounding=reply.grounding.model_dump(mode="json"),
        usage=_usage(meter),
    )
    session.add(assistant_row)
    await session.flush()
    await fold_summary(agent_session, [*earlier, user_row, assistant_row])
    logger.info(
        "agent.answer session_id=%s status=%s citations=%d",
        agent_session.id,
        reply.grounding.status,
        len(reply.citations),
    )
    await session.refresh(user_row)
    await session.refresh(assistant_row)
    return AgentTurnResponse(
        user_message=_message_response(user_row), assistant_message=_message_response(assistant_row)
    )
