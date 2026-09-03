"""Shared outbound retry policy: exponential backoff with jitter, honouring
Retry-After when a provider supplies it. Used by the LLM wrapper and every
job-source connector so rate-limit behaviour is identical across surfaces.

Delays and attempt counts come from Settings (LLM_RETRY_*), never hardcoded.
"""

import asyncio
import logging
import random
from collections.abc import Awaitable, Callable

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})
_MAX_DELAY_S = 60.0
_JITTER_FRACTION = 0.25


def retryable_status(status: int | None) -> bool:
    return status in _RETRYABLE_STATUS


def retry_after_header(value: object) -> float | None:
    """Parse a numeric Retry-After (seconds); HTTP-date form is ignored."""
    if isinstance(value, bool) or not isinstance(value, int | float | str):
        return None
    try:
        seconds = float(value) if isinstance(value, str) else float(value)
    except ValueError:
        return None
    return seconds if seconds >= 0 else None


class Transient(Exception):
    """A retry-worthy outcome that is not an exception at the call site
    (e.g. an HTTP 429 response). Carries an optional server-provided delay."""

    def __init__(self, description: str, retry_after_s: float | None = None) -> None:
        super().__init__(description)
        self.retry_after_s = retry_after_s


def _backoff_delay_s(attempt: int) -> float:
    settings = get_settings()
    base = max(0.0, settings.llm_retry_base_delay_s)
    delay = base * (2**attempt) * (1 + random.uniform(0, _JITTER_FRACTION))
    return min(delay, _MAX_DELAY_S)


async def with_retry[RunT](
    what: str,
    call: Callable[[], Awaitable[RunT]],
    *,
    is_retryable: Callable[[Exception], bool],
) -> RunT:
    """Run `call()` with the shared retry policy; re-raises the last failure.

    `is_retryable` classifies exceptions; Transient marks retry-worthy
    non-exceptions and may pin the delay via its retry_after_s.
    """
    attempts = max(1, get_settings().llm_retry_attempts)
    for attempt in range(attempts):
        try:
            return await call()
        except Transient as exc:
            last: Exception = exc
            pinned_delay = exc.retry_after_s
        except Exception as exc:
            if not is_retryable(exc):
                raise
            last = exc
            pinned_delay = None
        if attempt < attempts - 1:
            delay = pinned_delay if pinned_delay is not None else _backoff_delay_s(attempt)
            logger.warning(
                "%s transient failure (%s); retrying in %.1fs (attempt %d/%d)",
                what,
                last,
                delay,
                attempt + 2,
                attempts,
            )
            await asyncio.sleep(delay)
    raise last
