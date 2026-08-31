import logging
import time
from dataclasses import dataclass

import litellm

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
