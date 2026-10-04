import logging
from dataclasses import replace

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.llm import (
    CostEstimate,
    LLMError,
    LLMTask,
    estimate_structured_cost,
    format_cost,
    is_llm_configured,
    parse_structured,
)
from app.core.errors import (
    EmployerMergeSuggestionError,
    LLMNotConfiguredError,
    NoEmployersToCompareError,
)
from app.schemas.evidence import EmployerMergeSuggestion, EmployerMergeSuggestionsResponse
from app.services.employer_mapping import load_profile_facts
from app.services.evidence_items import candidate_id_or_none
from app.services.llm_cache import cached_parse_structured, has_cached_output
from app.services.prompts.employer_merge import (
    EMPLOYER_MERGE_PROMPT_VERSION,
    SYSTEM_PROMPT,
    build_prompt,
)

logger = logging.getLogger(__name__)

MIN_GROUP_SIZE = 2
EXPECTED_COMPLETION_TOKENS = 400


class _Group(BaseModel):
    canonical: str
    members: list[str]
    reason: str = ""


class _Output(BaseModel):
    groups: list[_Group] = Field(default_factory=list[_Group])


async def _names(session: AsyncSession) -> list[str]:
    """The employers to compare: one name per company group, none already merged away."""
    if not is_llm_configured():
        raise LLMNotConfiguredError
    candidate_id = await candidate_id_or_none(session)
    groups = (
        [] if candidate_id is None else (await load_profile_facts(session, candidate_id)).groups
    )
    names = sorted((group.name for group in groups), key=str.casefold)
    if len(names) < MIN_GROUP_SIZE:
        raise NoEmployersToCompareError
    return names


def _key_parts(names: list[str]) -> dict[str, object]:
    return {"names": names}


def validated(output: _Output, names: list[str]) -> list[EmployerMergeSuggestion]:
    """Keep only suggestions made of names we sent: no invented names, no overlaps, two or more."""
    known = {name.casefold(): name for name in names}
    used: set[str] = set()
    kept: list[EmployerMergeSuggestion] = []
    for group in output.groups:
        members = list(
            dict.fromkeys(
                known[member.casefold()]
                for member in group.members
                if member.casefold() in known and known[member.casefold()] not in used
            )
        )
        canonical = known.get(group.canonical.casefold())
        if len(members) < MIN_GROUP_SIZE or canonical not in members:
            continue
        used.update(members)
        kept.append(
            EmployerMergeSuggestion(canonical=canonical, members=members, reason=group.reason[:300])
        )
    return kept


async def estimate_suggestions(session: AsyncSession) -> CostEstimate:
    """Cost of `suggest_merges` without calling the model; free when the answer is cached."""
    names = await _names(session)
    estimate = estimate_structured_cost(
        build_prompt(names),
        schema=_Output,
        system=SYSTEM_PROMPT,
        expected_completion_tokens=EXPECTED_COMPLETION_TOKENS,
        task=LLMTask.classify,
    )
    cached = await has_cached_output(
        session,
        task=LLMTask.classify,
        prompt_version=EMPLOYER_MERGE_PROMPT_VERSION,
        key_parts=_key_parts(names),
        schema=_Output,
    )
    return replace(estimate, prompt_tokens=0, completion_tokens=0, usd=0.0) if cached else estimate


async def suggest_merges(session: AsyncSession) -> EmployerMergeSuggestionsResponse:
    """Ask the model which differently named companies are one employer; nothing is stored."""
    names = await _names(session)
    try:
        result = await cached_parse_structured(
            session,
            task=LLMTask.classify,
            prompt_version=EMPLOYER_MERGE_PROMPT_VERSION,
            key_parts=_key_parts(names),
            schema=_Output,
            call=lambda: parse_structured(
                build_prompt(names),
                schema=_Output,
                system=SYSTEM_PROMPT,
                temperature=0.0,
                task=LLMTask.classify,
            ),
        )
    except LLMError as exc:
        logger.warning("employers.merge_suggest failed error_type=%s", type(exc).__name__)
        raise EmployerMergeSuggestionError(str(exc)) from exc
    suggestions = validated(result.data, names)
    logger.info(
        "employers.merge_suggest names=%d groups=%d prompt_tokens=%s completion_tokens=%s "
        "cost_usd=%s",
        len(names),
        len(suggestions),
        result.prompt_tokens,
        result.completion_tokens,
        format_cost(result.cost_usd),
    )
    return EmployerMergeSuggestionsResponse(
        suggestions=suggestions,
        cost_usd=result.cost_usd,
        cached=result.prompt_tokens == 0 and result.completion_tokens == 0,
    )
