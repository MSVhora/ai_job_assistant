import pytest

from app.adapters.retry import TransientError, retry_after_header, retryable_status, with_retry
from app.core.config import get_settings


async def _no_delay(_: float) -> None:
    return None


@pytest.fixture(autouse=True)
def fast_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.adapters.retry.asyncio.sleep", _no_delay)


async def test_retries_transient_until_success() -> None:
    calls = {"count": 0}

    async def call() -> str:
        calls["count"] += 1
        if calls["count"] < 3:
            msg = "status 429"
            raise TransientError(msg)
        return "ok"

    assert (
        await with_retry("test", call, is_retryable=lambda exc: isinstance(exc, TransientError))
        == "ok"
    )
    assert calls["count"] == 3


async def test_gives_up_after_configured_attempts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "llm_retry_attempts", 2)
    calls = {"count": 0}

    async def call() -> str:
        calls["count"] += 1
        msg = "status 429"
        raise TransientError(msg)

    with pytest.raises(TransientError):
        await with_retry("test", call, is_retryable=lambda exc: isinstance(exc, TransientError))
    assert calls["count"] == 2


async def test_retry_after_pins_the_delay(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "llm_retry_attempts", 2)
    sleeps: list[float] = []

    async def record_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr("app.adapters.retry.asyncio.sleep", record_sleep)

    async def call() -> str:
        msg = "status 429"
        raise TransientError(msg, retry_after_s=7.5)

    with pytest.raises(TransientError):
        await with_retry("test", call, is_retryable=lambda exc: isinstance(exc, TransientError))

    assert sleeps == [7.5]


async def test_non_retryable_fails_fast() -> None:
    calls = {"count": 0}

    async def call() -> str:
        calls["count"] += 1
        msg = "bad input"
        raise ValueError(msg)

    with pytest.raises(ValueError, match="bad input"):
        await with_retry("test", call, is_retryable=lambda exc: False)
    assert calls["count"] == 1


def test_retryable_status() -> None:
    assert retryable_status(429)
    assert retryable_status(503)
    assert not retryable_status(401)
    assert not retryable_status(None)


def test_retry_after_header_parsing() -> None:
    assert retry_after_header("5") == 5.0
    assert retry_after_header(3) == 3.0
    assert retry_after_header("Wed, 21 Oct 2015 07:28:00 GMT") is None
    assert retry_after_header("-1") is None
    assert retry_after_header(None) is None
