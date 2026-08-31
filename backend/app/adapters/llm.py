import json
import logging
import time
from dataclasses import dataclass

import litellm
from pydantic import BaseModel, ValidationError

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class LLMError(Exception):
    pass


@dataclass(frozen=True)
class GenerationResult:
    text: str
    prompt_tokens: int
    completion_tokens: int


@dataclass(frozen=True)
class EmbeddingResult:
    vectors: list[list[float]]
    prompt_tokens: int


@dataclass(frozen=True)
class StructuredResult[ModelT: BaseModel]:
    data: ModelT
    prompt_tokens: int
    completion_tokens: int


def is_llm_configured() -> bool:
    return get_settings().gemini_api_key is not None


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
    try:
        response = await litellm.acompletion(
            model=settings.llm_model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            api_key=settings.gemini_api_key,
        )
    except Exception as exc:
        raise LLMError(f"llm generation failed: {exc}") from exc

    duration_ms = (time.perf_counter() - start) * 1000
    usage = response.usage
    logger.info(
        "llm.generate model=%s duration_ms=%.0f prompt_tokens=%s completion_tokens=%s",
        settings.llm_model,
        duration_ms,
        usage.prompt_tokens,
        usage.completion_tokens,
    )
    return GenerationResult(
        text=response.choices[0].message.content or "",
        prompt_tokens=usage.prompt_tokens or 0,
        completion_tokens=usage.completion_tokens or 0,
    )


async def embed(texts: list[str]) -> EmbeddingResult:
    if not texts:
        return EmbeddingResult(vectors=[], prompt_tokens=0)

    settings = get_settings()
    start = time.perf_counter()
    try:
        response = await litellm.aembedding(
            model=settings.embedding_model,
            input=texts,
            api_key=settings.gemini_api_key,
        )
    except Exception as exc:
        raise LLMError(f"llm embedding failed: {exc}") from exc

    duration_ms = (time.perf_counter() - start) * 1000
    usage = response.usage
    logger.info(
        "llm.embed model=%s duration_ms=%.0f count=%d prompt_tokens=%s",
        settings.embedding_model,
        duration_ms,
        len(texts),
        usage.prompt_tokens,
    )
    return EmbeddingResult(
        vectors=[item["embedding"] for item in response.data],
        prompt_tokens=usage.prompt_tokens or 0,
    )


async def parse_structured[ModelT: BaseModel](
    prompt: str,
    *,
    schema: type[ModelT],
    system: str | None = None,
    temperature: float = 0.2,
    max_tokens: int | None = None,
) -> StructuredResult[ModelT]:
    settings = get_settings()
    # Prompt-instructed JSON instead of provider structured output: Gemini 2.5 Flash
    # loops and truncates on large responseSchema payloads (observed live 2026-08-31);
    # the schema is enforced by pydantic validation plus one repair round-trip.
    schema_json = _inline_json_schema_refs(schema.model_json_schema())
    json_rule = (
        "Respond with a single JSON object conforming to this JSON schema. "
        f"No prose, no markdown fences:\n{json.dumps(schema_json)}"
    )
    system_content = f"{system}\n\n{json_rule}" if system else json_rule

    start = time.perf_counter()
    first = await generate(
        prompt, system=system_content, temperature=temperature, max_tokens=max_tokens
    )
    try:
        data = schema.model_validate_json(_extract_json(first.text))
        prompt_tokens = first.prompt_tokens
        completion_tokens = first.completion_tokens
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
            raise LLMError(
                "structured output failed validation after repair: "
                f"{_format_validation_errors(repair_exc)}"
            ) from repair_exc
        prompt_tokens = first.prompt_tokens + repair.prompt_tokens
        completion_tokens = first.completion_tokens + repair.completion_tokens

    duration_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "llm.parse_structured model=%s duration_ms=%.0f prompt_tokens=%d completion_tokens=%d",
        settings.llm_model,
        duration_ms,
        prompt_tokens,
        completion_tokens,
    )
    return StructuredResult(
        data=data, prompt_tokens=prompt_tokens, completion_tokens=completion_tokens
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
    resolved = _resolve_refs(schema, defs if isinstance(defs, dict) else {})
    if isinstance(resolved, dict):
        resolved.pop("$defs", None)
    return resolved


def _resolve_refs(node: object, defs: dict[str, object]) -> object:
    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str):
            name = ref.rsplit("/", maxsplit=1)[-1]
            target = defs.get(name)
            return _resolve_refs(target if isinstance(target, dict) else {}, defs)
        return {key: _resolve_refs(value, defs) for key, value in node.items()}
    if isinstance(node, list):
        return [_resolve_refs(item, defs) for item in node]
    return node
