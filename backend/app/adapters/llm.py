import json
import logging
import time
from dataclasses import dataclass
from http import HTTPStatus
from typing import Literal, cast

import litellm
from pydantic import BaseModel, ValidationError

from app.adapters.retry import with_retry
from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)

_RETRYABLE_STATUS_CODES = frozenset(
    {
        HTTPStatus.TOO_MANY_REQUESTS,
        HTTPStatus.INTERNAL_SERVER_ERROR,
        HTTPStatus.BAD_GATEWAY,
        HTTPStatus.SERVICE_UNAVAILABLE,
        HTTPStatus.GATEWAY_TIMEOUT,
    }
)


class LLMError(Exception):
    pass


def _is_transport_retryable(exc: Exception) -> bool:
    status = getattr(exc, "status_code", None)
    if isinstance(status, int) and status in _RETRYABLE_STATUS_CODES:
        return True
    return isinstance(exc, (litellm.exceptions.Timeout, litellm.exceptions.APIConnectionError))


def _failure_reason(exc: Exception) -> str:
    status = getattr(exc, "status_code", None)
    if isinstance(exc, litellm.exceptions.RateLimitError) or status == HTTPStatus.TOO_MANY_REQUESTS:
        return "rate limited by the provider - retry shortly"
    if isinstance(exc, litellm.exceptions.Timeout):
        return "request timed out"
    if isinstance(exc, litellm.exceptions.APIConnectionError):
        return "could not reach the provider"
    if isinstance(status, int) and status >= HTTPStatus.INTERNAL_SERVER_ERROR:
        return "provider service error - retry shortly"
    return "provider rejected the request"


@dataclass(frozen=True)
class GenerationResult:
    text: str
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float | None = None


@dataclass(frozen=True)
class EmbeddingResult:
    vectors: list[list[float]]
    prompt_tokens: int
    cost_usd: float | None = None


@dataclass(frozen=True)
class StructuredResult[ModelT: BaseModel]:
    data: ModelT
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float | None = None


PriceBasis = Literal["configured_prices", "litellm_price_map", "unavailable"]

_TOKENS_PER_MILLION = 1_000_000
_APPROX_CHARS_PER_TOKEN = 4
_PRICE_LOOKUP_ERRORS = (litellm.exceptions.BadRequestError, KeyError, ValueError, TypeError)
_TOKEN_COUNT_ERRORS = (litellm.exceptions.BadRequestError, KeyError, ValueError, TypeError)


@dataclass(frozen=True)
class CostEstimate:
    """USD is None when the model's price is unknown — never a guessed number."""

    prompt_tokens: int
    completion_tokens: int
    usd: float | None
    basis: PriceBasis


def estimate_tokens(messages: list[dict[str, str]], model: str | None = None) -> int:
    """Token count of a chat prompt via LiteLLM's tokenizer; chars/4 when it cannot count."""
    resolved = model or get_settings().llm_model
    try:
        return int(litellm.token_counter(model=resolved, messages=messages))  # pyright: ignore[reportUnknownMemberType]  # litellm: partially unknown signature
    except _TOKEN_COUNT_ERRORS:
        chars = sum(len(message["content"]) for message in messages)
        return -(-chars // _APPROX_CHARS_PER_TOKEN)


def _map_prices_per_mtok(model: str) -> tuple[float, float] | None:
    try:
        prompt_usd, completion_usd = litellm.cost_per_token(  # pyright: ignore[reportUnknownMemberType]  # litellm: partially unknown signature
            model=model,
            prompt_tokens=_TOKENS_PER_MILLION,
            completion_tokens=_TOKENS_PER_MILLION,
        )
    except _PRICE_LOOKUP_ERRORS:
        return None
    return float(prompt_usd), float(completion_usd)


def estimate_cost(model: str, prompt_tokens: int, completion_tokens: int = 0) -> CostEstimate:
    """Price `prompt_tokens`/`completion_tokens` for `model`.

    Settings overrides win over LiteLLM's price map; a direction with no known
    price makes the whole estimate unavailable.
    """
    settings = get_settings()
    if model == settings.embedding_model:
        override_in, override_out = settings.embedding_price_per_mtok, 0.0
    else:
        override_in, override_out = settings.llm_price_in_per_mtok, settings.llm_price_out_per_mtok
    mapped = _map_prices_per_mtok(model) if override_in is None or override_out is None else None
    price_in = override_in if override_in is not None else (mapped[0] if mapped else None)
    price_out = override_out if override_out is not None else (mapped[1] if mapped else None)
    if price_in is None or price_out is None:
        return CostEstimate(prompt_tokens, completion_tokens, None, "unavailable")
    usd = (prompt_tokens * price_in + completion_tokens * price_out) / _TOKENS_PER_MILLION
    overridden = override_in is not None or override_out is not None
    return CostEstimate(
        prompt_tokens,
        completion_tokens,
        usd,
        "configured_prices" if overridden else "litellm_price_map",
    )


def format_cost(usd: float | None) -> str:
    return "unknown" if usd is None else f"{usd:.6f}"


def is_llm_configured() -> bool:
    return get_settings().gemini_api_key is not None


def _token_counts(response: object) -> tuple[int, int]:
    usage = getattr(response, "usage", None)
    prompt = getattr(usage, "prompt_tokens", None)
    completion = getattr(usage, "completion_tokens", None)
    return (
        prompt if isinstance(prompt, int) else 0,
        completion if isinstance(completion, int) else 0,
    )


def _completion_text(response: object) -> str:
    choices = getattr(response, "choices", None)
    content = getattr(getattr(choices[0], "message", None), "content", None) if choices else None
    return content if isinstance(content, str) else ""


async def _completion_with_retry(
    settings: Settings,
    messages: list[dict[str, str]],
    temperature: float,
    max_tokens: int | None,
) -> object:
    async def _call() -> object:
        return await litellm.acompletion(  # pyright: ignore[reportUnknownMemberType]  # litellm: partially unknown signature
            model=settings.llm_model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            api_key=settings.gemini_api_key,
            timeout=settings.llm_timeout_s,
        )

    try:
        return await with_retry("llm.generate", _call, is_retryable=_is_transport_retryable)
    except Exception as exc:
        reason = _failure_reason(exc)
        logger.warning("llm.generate failed (%s): %s", type(exc).__name__, reason)
        msg = f"llm generation failed: {reason}"
        raise LLMError(msg) from exc


async def generate(
    prompt: str,
    *,
    system: str | None = None,
    temperature: float = 0.2,
    max_tokens: int | None = None,
) -> GenerationResult:
    settings = get_settings()
    messages: list[dict[str, str]] = []
    if system is not None:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    start = time.perf_counter()
    response = await _completion_with_retry(settings, messages, temperature, max_tokens)

    duration_ms = (time.perf_counter() - start) * 1000
    prompt_tokens, completion_tokens = _token_counts(response)
    cost_usd = estimate_cost(settings.llm_model, prompt_tokens, completion_tokens).usd
    logger.info(
        "llm.generate model=%s duration_ms=%.0f prompt_tokens=%s completion_tokens=%s cost_usd=%s",
        settings.llm_model,
        duration_ms,
        prompt_tokens,
        completion_tokens,
        format_cost(cost_usd),
    )
    return GenerationResult(
        text=_completion_text(response),
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        cost_usd=cost_usd,
    )


def _embedding_vectors(response: object) -> list[list[float]]:
    items: list[dict[str, list[float]]] = getattr(response, "data", [])
    return [item["embedding"] for item in items]


async def embed(texts: list[str]) -> EmbeddingResult:
    if not texts:
        return EmbeddingResult(vectors=[], prompt_tokens=0)

    settings = get_settings()
    start = time.perf_counter()

    async def _call() -> object:
        return await litellm.aembedding(  # pyright: ignore[reportUnknownMemberType]  # litellm: partially unknown signature
            model=settings.embedding_model,
            input=texts,
            dimensions=settings.embedding_dimensions,
            api_key=settings.gemini_api_key,
            timeout=settings.llm_timeout_s,
        )

    try:
        response = await with_retry("llm.embed", _call, is_retryable=_is_transport_retryable)
    except Exception as exc:
        reason = _failure_reason(exc)
        logger.warning("llm.embed failed (%s): %s", type(exc).__name__, reason)
        msg = f"llm embedding failed: {reason}"
        raise LLMError(msg) from exc

    duration_ms = (time.perf_counter() - start) * 1000
    prompt_tokens, _ = _token_counts(response)
    cost_usd = estimate_cost(settings.embedding_model, prompt_tokens).usd
    logger.info(
        "llm.embed model=%s duration_ms=%.0f count=%d prompt_tokens=%s cost_usd=%s",
        settings.embedding_model,
        duration_ms,
        len(texts),
        prompt_tokens,
        format_cost(cost_usd),
    )
    return EmbeddingResult(
        vectors=_embedding_vectors(response), prompt_tokens=prompt_tokens, cost_usd=cost_usd
    )


def structured_system_prompt(schema: type[BaseModel], system: str | None) -> str:
    # Prompt-instructed JSON instead of provider structured output: Gemini 2.5 Flash
    # loops and truncates on large responseSchema payloads (observed live 2026-08-31);
    # the schema is enforced by pydantic validation plus one repair round-trip.
    schema_json = _inline_json_schema_refs(schema.model_json_schema())
    json_rule = (
        "Respond with a single JSON object conforming to this JSON schema. "
        f"No prose, no markdown fences:\n{json.dumps(schema_json)}"
    )
    return f"{system}\n\n{json_rule}" if system else json_rule


def estimate_structured_cost(
    prompt: str,
    *,
    schema: type[BaseModel],
    system: str | None = None,
    expected_completion_tokens: int,
) -> CostEstimate:
    """Cost of one `parse_structured` call, without calling the provider.

    A validation failure triggers one repair round-trip, so the real cost can be up to about
    twice this; callers phrase it as an approximate figure.
    """
    model = get_settings().llm_model
    messages = [
        {"role": "system", "content": structured_system_prompt(schema, system)},
        {"role": "user", "content": prompt},
    ]
    return estimate_cost(model, estimate_tokens(messages, model), expected_completion_tokens)


async def parse_structured[ModelT: BaseModel](
    prompt: str,
    *,
    schema: type[ModelT],
    system: str | None = None,
    temperature: float = 0.2,
    max_tokens: int | None = None,
) -> StructuredResult[ModelT]:
    settings = get_settings()
    system_content = structured_system_prompt(schema, system)

    start = time.perf_counter()
    first = await generate(
        prompt, system=system_content, temperature=temperature, max_tokens=max_tokens
    )
    try:
        data = schema.model_validate_json(_extract_json(first.text))
        prompt_tokens = first.prompt_tokens
        completion_tokens = first.completion_tokens
        cost_usd = first.cost_usd
    except ValidationError as exc:
        logger.warning("llm.parse_structured validation failed; attempting one repair call")
        repair_prompt = (
            "The previous response did not validate against the schema. "
            f"Validation errors: {_format_validation_errors(exc)}\n"
            f"Previous response:\n{first.text[:4000]}\n"
            "Return the corrected JSON object only."
        )
        repair = await generate(
            repair_prompt, system=system_content, temperature=temperature, max_tokens=max_tokens
        )
        try:
            data = schema.model_validate_json(_extract_json(repair.text))
        except ValidationError as repair_exc:
            msg = (
                "structured output failed validation after repair: "
                f"{_format_validation_errors(repair_exc)}"
            )
            raise LLMError(msg) from repair_exc
        prompt_tokens = first.prompt_tokens + repair.prompt_tokens
        completion_tokens = first.completion_tokens + repair.completion_tokens
        cost_usd = (
            first.cost_usd + repair.cost_usd
            if first.cost_usd is not None and repair.cost_usd is not None
            else None
        )

    duration_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "llm.parse_structured model=%s duration_ms=%.0f prompt_tokens=%d completion_tokens=%d "
        "cost_usd=%s",
        settings.llm_model,
        duration_ms,
        prompt_tokens,
        completion_tokens,
        format_cost(cost_usd),
    )
    return StructuredResult(
        data=data,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        cost_usd=cost_usd,
    )


def _extract_json(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        newline = text.find("\n")
        text = text[newline + 1 :] if newline != -1 else text[3:]
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3]
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        text = text[start : end + 1]
    return text.strip()


def _format_validation_errors(exc: ValidationError) -> str:
    parts = [
        f"{'.'.join(str(loc) for loc in error['loc'])}: {error['msg']}"
        for error in exc.errors()[:20]
    ]
    return "; ".join(parts)


def _inline_json_schema_refs(schema: dict[str, object]) -> dict[str, object]:
    defs = schema.get("$defs")
    resolved = _resolve_refs(
        schema, cast("dict[str, object]", defs) if isinstance(defs, dict) else {}
    )
    if isinstance(resolved, dict):
        resolved = cast("dict[str, object]", resolved)
        resolved.pop("$defs", None)
        return resolved
    return schema


def _resolve_refs(node: object, defs: dict[str, object]) -> object:
    if isinstance(node, dict):
        mapping = cast("dict[str, object]", node)
        ref = mapping.get("$ref")
        if isinstance(ref, str):
            name = ref.rsplit("/", maxsplit=1)[-1]
            target = defs.get(name)
            return _resolve_refs(
                cast("dict[str, object]", target) if isinstance(target, dict) else {}, defs
            )
        return {key: _resolve_refs(value, defs) for key, value in mapping.items()}
    if isinstance(node, list):
        return [_resolve_refs(item, defs) for item in cast("list[object]", node)]
    return node
