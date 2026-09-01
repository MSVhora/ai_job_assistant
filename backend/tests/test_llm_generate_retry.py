import pytest
from fakes import ProviderError, install_acompletion, llm_response

from app.adapters.llm import LLMError, generate


async def _no_delay(_: float) -> None:
    return None


@pytest.fixture(autouse=True)
def fast_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.adapters.llm.asyncio.sleep", _no_delay)


async def test_generate_retries_once_on_rate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    responses = iter([ProviderError(429), llm_response("ok", prompt_tokens=3, completion_tokens=2)])
    calls = install_acompletion(monkeypatch, lambda **kw: next(responses))

    result = await generate("prompt")

    assert result.text == "ok"
    assert result.prompt_tokens == 3
    assert result.completion_tokens == 2
    assert len(calls) == 2


async def test_generate_gives_up_after_second_rate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    responses = iter([ProviderError(429), ProviderError(429)])
    calls = install_acompletion(monkeypatch, lambda **kw: next(responses))

    with pytest.raises(LLMError, match="rate limited by the provider"):
        await generate("prompt")

    assert len(calls) == 2


async def test_generate_does_not_retry_client_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    responses = iter([ProviderError(400)])
    calls = install_acompletion(monkeypatch, lambda **kw: next(responses))

    with pytest.raises(LLMError, match="provider rejected the request"):
        await generate("prompt")

    assert len(calls) == 1


async def test_generate_retries_service_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    responses = iter([ProviderError(503), llm_response("ok")])
    calls = install_acompletion(monkeypatch, lambda **kw: next(responses))

    result = await generate("prompt")

    assert result.text == "ok"
    assert len(calls) == 2
