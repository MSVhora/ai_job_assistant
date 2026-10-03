import hashlib
import json
import logging
from collections.abc import Awaitable, Callable

from pydantic import BaseModel, ValidationError
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.llm import LLMTask, StructuredResult, model_for, record_cache_lookup
from app.models import LLMOutputCache

logger = logging.getLogger(__name__)


def cache_key(task: LLMTask, model: str, prompt_version: str, key_parts: object) -> str:
    """SHA-256 over canonical JSON; `key_parts` must be the redacted, JSON-serializable inputs."""
    canonical = json.dumps(
        [task.value, model, prompt_version, key_parts],
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


async def cached_parse_structured[ModelT: BaseModel](
    session: AsyncSession,
    *,
    task: LLMTask,
    prompt_version: str,
    key_parts: object,
    schema: type[ModelT],
    call: Callable[[], Awaitable[StructuredResult[ModelT]]],
) -> StructuredResult[ModelT]:
    """Return the cached output for these inputs, or `call()` and store it.

    A hit costs no tokens (`cost_usd=0.0`). A cached row that no longer validates
    against `schema` is a miss and is overwritten. The caller owns the transaction.
    """
    model = model_for(task)
    key = cache_key(task, model, prompt_version, key_parts)
    row = await session.get(LLMOutputCache, key, populate_existing=True)
    if row is not None:
        try:
            data = schema.model_validate(row.output)
        except ValidationError:
            logger.warning("llm.cache invalid row; treating as miss task=%s", task.value)
        else:
            record_cache_lookup(hit=True)
            logger.info("llm.cache hit task=%s", task.value)
            return StructuredResult(data=data, prompt_tokens=0, completion_tokens=0, cost_usd=0.0)

    record_cache_lookup(hit=False)
    result = await call()
    values = {
        "key": key,
        "task": task.value,
        "model": model,
        "prompt_version": prompt_version,
        "output": result.data.model_dump(mode="json"),
        "prompt_tokens": result.prompt_tokens,
        "completion_tokens": result.completion_tokens,
    }
    stmt = insert(LLMOutputCache).values(**values)
    await session.execute(
        stmt.on_conflict_do_update(
            index_elements=[LLMOutputCache.key],
            set_={name: stmt.excluded[name] for name in values if name != "key"},
        )
    )
    return result
