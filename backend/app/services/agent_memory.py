import logging
import re
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.llm import LLMError, LLMTask, generate
from app.core.config import get_settings
from app.models import AgentMessage, AgentSession
from app.services.agent_grounding import strip_markers
from app.services.prompts.agent import (
    REWRITE_SYSTEM,
    SUMMARY_SYSTEM,
    build_rewrite_prompt,
    build_summary_prompt,
)
from app.services.resume_verify import build_source, check_claims

logger = logging.getLogger(__name__)

TURN_CHARS = 700
SUMMARY_CHARS = 1500
QUESTION_NOTE_CHARS = 80


def turn(message: AgentMessage) -> tuple[str, str]:
    text = strip_markers(message.content)[:TURN_CHARS]
    return ("Candidate" if message.role.value == "user" else "Coach", text)


def recent_turns(messages: Sequence[AgentMessage]) -> list[tuple[str, str]]:
    """The last `AGENT_HISTORY_TURNS` turns (a turn is a question and its answer), verbatim."""
    window = get_settings().agent_history_turns * 2
    return [turn(message) for message in messages[-window:]]


async def load_messages(session: AsyncSession, session_id: object) -> list[AgentMessage]:
    result = await session.execute(
        select(AgentMessage)
        .where(AgentMessage.session_id == session_id)
        .order_by(AgentMessage.created_at, AgentMessage.id)
    )
    return list(result.scalars().all())


def fallback_summary(previous: str, folded: Sequence[tuple[str, str]]) -> str:
    """Deterministic summary: the questions asked so far, with no generated text."""
    asked = [text[:QUESTION_NOTE_CHARS] for role, text in folded if role == "Candidate"]
    base = previous or "Earlier in this conversation the candidate asked:"
    merged = f"{base} " + "; ".join(asked) if asked else base
    return merged[:SUMMARY_CHARS]


async def fold_summary(agent_session: AgentSession, messages: Sequence[AgentMessage]) -> None:
    """Fold turns that fell out of the window into `summary`; conversation state only."""
    window = get_settings().agent_history_turns * 2
    through = len(messages) - window
    if through <= agent_session.summarized_through:
        return
    folded = [turn(message) for message in messages[agent_session.summarized_through : through]]
    previous = agent_session.summary or ""
    try:
        result = await generate(
            build_summary_prompt(previous, folded),
            system=SUMMARY_SYSTEM,
            temperature=0.0,
            max_tokens=400,
            task=LLMTask.classify,
        )
        summary = " ".join(result.text.split())[:SUMMARY_CHARS]
    except LLMError as exc:
        logger.warning("agent.memory summary failed error=%s", exc)
        return
    source = build_source([previous, *(text for _, text in folded)])
    if not summary or check_claims(summary, source):
        summary = fallback_summary(previous, folded)
    agent_session.summary = summary
    agent_session.summarized_through = through


async def standalone_question(
    question: str, history: Sequence[tuple[str, str]], summary: str
) -> str:
    """Rewrite a follow-up so it stands alone; the original question on any failure."""
    try:
        result = await generate(
            build_rewrite_prompt(question, history, summary),
            system=REWRITE_SYSTEM,
            temperature=0.0,
            max_tokens=200,
            task=LLMTask.classify,
        )
    except LLMError as exc:
        logger.warning("agent.memory rewrite failed error=%s", exc)
        return question
    rewritten = re.sub(r"\s+", " ", result.text).strip()
    return rewritten[: len(question) * 3 + 200] or question
