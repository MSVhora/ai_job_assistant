import logging
import re
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field

from app.adapters.llm import LLMError, LLMTask, parse_structured
from app.schemas.agent import AnswerVerdicts, GroundingStatus
from app.services.agent_retrieval import ContextBlock
from app.services.prompts.agent import JUDGE_SYSTEM, build_judge_prompt
from app.services.resume_terms import scan_skills
from app.services.resume_verify import (
    IRREGULAR_PAST,
    NOT_PAST_ED,
    OWNERSHIP_FAMILIES,
    Source,
    build_source,
    check_claims,
    merge_sources,
    numbers_in,
)

logger = logging.getLogger(__name__)

MARKER_PATTERN = r"\[(?:A\d+|E\d+|P|J)\]"
MARKER = re.compile(r"\[(A\d+|E\d+|P|J)\]")
SENTENCE = re.compile(rf"\s*((?:[^.!?]|[.!?](?=\w))+[.!?]*(?:\s*{MARKER_PATTERN})*)", re.DOTALL)
FIRST_PERSON_PAST = re.compile(
    r"\b(?:i|we)\s+([a-z]+)\b|\bmy (?:team|manager|colleagues)\b", re.IGNORECASE
)
SAFE_UNCITED = re.compile(
    r"^(?:the evidence|i (?:can|can't|cannot|don't|do not|could not|couldn't|have no)|if you"
    r"|would you|let me know|happy to|i'd (?:be glad|suggest|like to)|my evidence|there is no)",
    re.IGNORECASE,
)
SHORT_SENTENCE_WORDS = 5
JUDGE_BATCH = 12
EVIDENCE_LINE_CHARS = 700
UNCITED = "states something about the candidate without citing evidence"


@dataclass(frozen=True)
class Flag:
    index: int
    sentence: str
    reason: str


@dataclass
class Checked:
    sentences: list[str]
    flags: list[Flag] = field(default_factory=list[Flag])
    judge_unavailable: bool = False

    @property
    def flagged_indexes(self) -> set[int]:
        return {flag.index for flag in self.flags}


@dataclass(frozen=True)
class Grounded:
    text: str
    status: GroundingStatus
    flagged_sentences: list[str]
    repaired: bool
    judge_unavailable: bool
    markers: list[str]


Repair = Callable[[str, list[str]], Awaitable[str]]


def split_sentences(text: str) -> list[str]:
    return [match.group(1).strip() for match in SENTENCE.finditer(text) if match.group(1).strip()]


def markers_in(sentence: str) -> list[str]:
    seen: list[str] = []
    for marker in MARKER.findall(sentence):
        if marker not in seen:
            seen.append(marker)
    return seen


def strip_markers(text: str) -> str:
    return re.sub(r"\s{2,}", " ", MARKER.sub("", text)).strip()


def _claims_experience(plain: str) -> bool:
    for match in FIRST_PERSON_PAST.finditer(plain):
        verb = match.group(1)
        if verb is None:
            return True
        word = verb.lower()
        if word in IRREGULAR_PAST or (word.endswith("ed") and word not in NOT_PAST_ED):
            return True
    return False


def is_factual(plain: str, *, kind: str) -> bool:
    """Whether an uncited sentence needs a citation (questions, offers and hedges do not)."""
    if plain.endswith("?") or len(plain.split()) <= SHORT_SENTENCE_WORDS:
        return False
    if numbers_in(plain) or scan_skills(plain) or _claims_experience(plain):
        return True
    if SAFE_UNCITED.match(plain):
        return False
    return kind != "hypothetical"


def _source_for(blocks: Sequence[ContextBlock]) -> Source:
    return merge_sources(build_source(block.corpus, block.skills) for block in blocks)


def _ownership_violations(plain: str, corpus: str) -> list[str]:
    """Led, owned, architected and similar verbs need the evidence to use them too."""
    lowered, evidence = plain.casefold(), corpus.casefold()
    for family in OWNERSHIP_FAMILIES:
        used = re.search(family, lowered)
        if used and not re.search(family, evidence):
            return [f"'{used.group(0)}' claims more ownership than the evidence shows"]
    return []


def _flag_sentence(
    index: int, sentence: str, by_marker: dict[str, ContextBlock], kind: str
) -> tuple[Flag | None, list[ContextBlock]]:
    cited = markers_in(sentence)
    plain = strip_markers(sentence)
    unknown = [marker for marker in cited if marker not in by_marker]
    if unknown:
        return Flag(index, sentence, f"cites {unknown[0]}, which is not a source"), []
    if not cited:
        reason = UNCITED if is_factual(plain, kind=kind) else None
        return (Flag(index, sentence, reason) if reason else None), []
    blocks = [by_marker[marker] for marker in cited]
    if all(block.kind == "job" for block in blocks) and _claims_experience(plain):
        reason = "claims experience on the strength of the job description alone"
        return Flag(index, sentence, reason), blocks
    source = _source_for(blocks)
    violations = [*check_claims(plain, source), *_ownership_violations(plain, source.corpus)]
    if violations:
        return Flag(index, sentence, violations[0]), blocks
    return None, blocks


async def _judge(pending: list[tuple[int, str, list[ContextBlock]]], checked: Checked) -> None:
    for start in range(0, len(pending), JUDGE_BATCH):
        batch = pending[start : start + JUDGE_BATCH]
        items = [
            (index, plain, [block.text[:EVIDENCE_LINE_CHARS] for block in blocks])
            for index, plain, blocks in batch
        ]
        try:
            result = await parse_structured(
                build_judge_prompt(items),
                schema=AnswerVerdicts,
                system=JUDGE_SYSTEM,
                temperature=0.0,
                task=LLMTask.judge,
            )
        except LLMError as exc:
            logger.warning("agent.grounding judge unavailable error=%s", exc)
            checked.judge_unavailable = True
            return
        sentences = {index: plain for index, plain, _ in batch}
        for verdict in result.data.verdicts:
            if not verdict.entailed and verdict.index in sentences:
                reason = verdict.reason or "the cited evidence does not support it"
                checked.flags.append(Flag(verdict.index, checked.sentences[verdict.index], reason))


async def check_answer(answer: str, blocks: Sequence[ContextBlock], *, kind: str) -> Checked:
    """Deterministic checks on every sentence, then the entailment judge on the cited ones."""
    by_marker = {block.marker: block for block in blocks}
    checked = Checked(sentences=split_sentences(answer))
    pending: list[tuple[int, str, list[ContextBlock]]] = []
    for index, sentence in enumerate(checked.sentences):
        flag, cited = _flag_sentence(index, sentence, by_marker, kind)
        if flag is not None:
            checked.flags.append(flag)
        elif cited:
            pending.append((index, strip_markers(sentence), cited))
    await _judge(pending, checked)
    return checked


def _used_markers(sentences: Sequence[str]) -> list[str]:
    used: list[str] = []
    for sentence in sentences:
        for marker in markers_in(sentence):
            if marker not in used:
                used.append(marker)
    return used


def _grounded(checked: Checked, *, repaired: bool) -> Grounded:
    flagged = checked.flagged_indexes
    kept = [s for i, s in enumerate(checked.sentences) if i not in flagged]
    cited = [s for s in kept if markers_in(s)]
    if not checked.flags:
        status: GroundingStatus = "grounded"
    elif cited:
        status = "partial"
    else:
        status = "refused"
    return Grounded(
        text=" ".join(kept) if status != "refused" else "",
        status=status,
        flagged_sentences=[flag.sentence for flag in checked.flags],
        repaired=repaired,
        judge_unavailable=checked.judge_unavailable,
        markers=_used_markers(kept),
    )


async def ground(
    answer: str, blocks: Sequence[ContextBlock], *, kind: str, repair: Repair
) -> Grounded:
    """Validate; on failure one repair round-trip; what still fails is dropped, not shown."""
    first = await check_answer(answer, blocks, kind=kind)
    if not first.flags:
        return _grounded(first, repaired=False)
    problems = [f"'{flag.sentence}': {flag.reason}" for flag in first.flags]
    try:
        rewritten = await repair(answer, problems)
    except LLMError as exc:
        logger.warning("agent.grounding repair failed error=%s", exc)
        return _grounded(first, repaired=False)
    second = await check_answer(rewritten, blocks, kind=kind)
    return _grounded(second, repaired=True)
