import pytest

from app.adapters.retry import Transient, retry_after_header, retryable_status, with_retry
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
            raise Transient("status 429")
        return "ok"

    assert (
        await with_retry("test", call, is_retryable=lambda exc: isinstance(exc, Transient)) == "ok"
    )
    assert calls["count"] == 3


async def test_gives_up_after_configured_attempts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "llm_retry_attempts", 2)
    calls = {"count": 0}

    async def call() -> str:
        calls["count"] += 1
        raise Transient("status 429")

    with pytest.raises(Transient):
        await with_retry("test", call, is_retryable=lambda exc: isinstance(exc, Transient))
    assert calls["count"] == 2


async def test_retry_after_pins_the_delay(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "llm_retry_attempts", 2)
    sleeps: list[float] = []

    async def record_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr("app.adapters.retry.asyncio.sleep", record_sleep)

    async def call() -> str:
        raise Transient("status 429", retry_after_s=7.5)

    with pytest.raises(Transient):
        await with_retry("test", call, is_retryable=lambda exc: isinstance(exc, Transient))

    assert sleeps == [7.5]


async def test_non_retryable_fails_fast() -> None:
    calls = {"count": 0}

    async def call() -> str:
        calls["count"] += 1
        raise ValueError("bad input")

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
