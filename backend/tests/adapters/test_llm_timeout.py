import litellm
import pytest
from fakes import embedding_response, install_acompletion, install_aembedding, llm_response

from app.adapters.llm import LLMError, embed, generate
from app.core.config import get_settings


async def _no_delay(_: float) -> None:
    return None


@pytest.fixture(autouse=True)
def fast_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.adapters.retry.asyncio.sleep", _no_delay)


def provider_timeout() -> litellm.exceptions.Timeout:
    return litellm.exceptions.Timeout(
        message="timed out", model="gemini/test", llm_provider="gemini"
    )


async def test_generate_passes_configured_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "llm_timeout_s", 12.5)
    calls = install_acompletion(monkeypatch, lambda **kw: llm_response("ok"))

    await generate("prompt")

    assert calls[0]["timeout"] == 12.5


async def test_embed_passes_configured_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "llm_timeout_s", 7.0)
    calls = install_aembedding(monkeypatch, lambda **kw: embedding_response([[0.1]]))

    await embed(["text"])

    assert calls[0]["timeout"] == 7.0


async def test_generate_retries_a_timeout_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    responses = iter([provider_timeout(), llm_response("ok")])
    calls = install_acompletion(monkeypatch, lambda **kw: next(responses))

    result = await generate("prompt")

    assert result.text == "ok"
    assert len(calls) == 2


async def test_generate_reports_a_persistent_timeout_plainly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(get_settings(), "llm_retry_attempts", 2)
    calls = install_acompletion(monkeypatch, lambda **kw: provider_timeout())

    with pytest.raises(LLMError, match="request timed out"):
        await generate("prompt")

    assert len(calls) == 2


async def test_embed_retries_a_timeout_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    responses = iter([provider_timeout(), embedding_response([[0.5]])])
    calls = install_aembedding(monkeypatch, lambda **kw: next(responses))

    result = await embed(["text"])

    assert result.vectors == [[0.5]]
    assert len(calls) == 2
