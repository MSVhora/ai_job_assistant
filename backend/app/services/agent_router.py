import logging
import re
from dataclasses import dataclass
from typing import Literal, get_args

from app.adapters.llm import LLMError, LLMTask, parse_structured
from app.schemas.agent import QuestionClass, QuestionType
from app.services.prompts.agent import CLASSIFY_SYSTEM, build_classify_prompt

logger = logging.getLogger(__name__)

DEFAULT_TYPE: QuestionType = "behavioral"
VALID_TYPES = frozenset(get_args(QuestionType))


def _rule(kind: QuestionType, *alternatives: str) -> tuple[QuestionType, re.Pattern[str]]:
    return kind, re.compile("|".join(alternatives), re.IGNORECASE)


RULES: tuple[tuple[QuestionType, re.Pattern[str]], ...] = (
    _rule(
        "out_of_scope",
        r"\b(?:weather|jokes?|poems?|recipes?|stock price|capital of|lottery|horoscope)\b",
        r"\bignore (?:all |your |the )?(?:previous|prior|above) (?:instructions|rules)",
        r"\bsystem prompt\b",
        r"\bwrite (?:me )?(?:a |an )?(?:essay|script|program)\b",
    ),
    _rule(
        "intro",
        r"\btell me about yourself\b",
        r"\bwalk me through your (?:background|resume|cv|career|experience)\b",
        r"\b(?:introduce|describe) yourself\b",
        r"\boverview of your (?:background|career)\b",
        r"\bwho are you\b",
    ),
    _rule(
        "motivation",
        r"\bwhy do you want\b",
        r"\bwhy are you (?:interested|leaving)\b",
        r"\bwhy (?:this|our) (?:role|company|job|position|team)\b",
        r"\bwhat attracts you\b",
        r"\bwhy should we hire you\b",
        r"\bwhy us\b",
        r"\bwhere do you see yourself\b",
        r"\bwhat interests you about\b",
    ),
    _rule(
        "behavioral",
        r"\btell me about a time\b",
        r"\bdescribe a (?:time|situation)\b",
        r"\bgive me an example\b",
        r"\ban example of a time\b",
        r"\bhave you ever\b",
        r"\bwhen did you\b",
        r"\bshare an experience\b",
        r"\ba time (?:when )?you\b",
    ),
    _rule(
        "hypothetical",
        r"\bhow (?:would|might) you\b",
        r"\bwhat would you do\b",
        r"\bif you (?:were|had|could)\b",
        r"\b(?:suppose|imagine|what if)\b",
    ),
    _rule(
        "technical",
        r"\bwhy did you (?:choose|use|pick|go with|decide|build|implement)\b",
        r"\bwhy .{1,60}\b(?:over|instead of|rather than)\b",
        r"\btrade-?offs?\b",
        r"\bhow did you (?:implement|build|design|test|debug|fix|optimi[sz]e|scale|deploy)\b",
        r"\bdebug(?:ged|ging)?\b",
        r"\b(?:architecture|design decision|algorithm|latency|database|schema|performance)\b",
        r"\bscalab\w+",
        r"\btechnical (?:challenge|decision)\b",
    ),
    _rule(
        "behavioral",
        r"\b(?:conflict|disagree\w*|failure|mistake|strength|weakness|leadership|led a team)\b",
        r"\b(?:biggest challenge|proudest|accomplish\w*|tight deadline|mentor\w*)\b",
        r"\bdifficult (?:colleague|stakeholder|situation)\b",
    ),
)

RATIONALE = re.compile(
    r"\bwhy\b.{0,80}\b(over|instead of|rather than|choose|chose|pick|picked|decide|decided|use|used"
    r"|go with|went with)\b|\btrade-?offs?\b|\bdecision\b",
    re.IGNORECASE,
)
FOLLOW_UP = re.compile(
    r"\b(that|this|those|these|it|its|they|them|there|the (project|team|system|service|tool))\b"
    r"|^(why|how|and|what about|so|then)\b",
    re.IGNORECASE,
)
MAX_FOLLOW_UP_WORDS = 8


@dataclass(frozen=True)
class Routed:
    kind: QuestionType
    via: Literal["rules", "llm", "default"]


def route_by_rules(question: str) -> QuestionType | None:
    for kind, pattern in RULES:
        if pattern.search(question):
            return kind
    return None


def asks_for_rationale(question: str) -> bool:
    return RATIONALE.search(question) is not None


def needs_rewrite(question: str, *, has_history: bool) -> bool:
    """A follow-up refers back to the conversation ("why?", "that project")."""
    if not has_history:
        return False
    return FOLLOW_UP.search(question) is not None or len(question.split()) <= MAX_FOLLOW_UP_WORDS


async def route_question(question: str) -> Routed:
    """Rules first (deterministic); the cheap model only when no rule fires."""
    if (kind := route_by_rules(question)) is not None:
        return Routed(kind, "rules")
    try:
        result = await parse_structured(
            build_classify_prompt(question),
            schema=QuestionClass,
            system=CLASSIFY_SYSTEM,
            temperature=0.0,
            task=LLMTask.classify,
        )
    except LLMError as exc:
        logger.warning("agent.route classifier failed error=%s", exc)
        return Routed(DEFAULT_TYPE, "default")
    return Routed(result.data.type, "llm")
