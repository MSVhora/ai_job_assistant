import pytest
from fakes import ProviderError, embedding_response, install_aembedding

from app.adapters.llm import LLMError, embed
from app.core.config import get_settings


async def _no_delay(_: float) -> None:
    return None


@pytest.fixture(autouse=True)
def fast_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.adapters.retry.asyncio.sleep", _no_delay)


async def test_embed_retries_on_rate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    responses = iter([ProviderError(429), embedding_response([[0.1, 0.2]], prompt_tokens=3)])
    calls = install_aembedding(monkeypatch, lambda **kw: next(responses))

    result = await embed(["text"])

    assert result.vectors == [[0.1, 0.2]]
    assert result.prompt_tokens == 3
    assert len(calls) == 2


async def test_embed_gives_up_after_configured_attempts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "llm_retry_attempts", 2)
    responses = iter([ProviderError(429), ProviderError(429)])
    calls = install_aembedding(monkeypatch, lambda **kw: next(responses))

    with pytest.raises(LLMError, match="llm embedding failed"):
        await embed(["text"])

    assert len(calls) == 2


async def test_embed_does_not_retry_client_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    responses = iter([ProviderError(400)])
    calls = install_aembedding(monkeypatch, lambda **kw: next(responses))

    with pytest.raises(LLMError, match="llm embedding failed"):
        await embed(["text"])

    assert len(calls) == 1
