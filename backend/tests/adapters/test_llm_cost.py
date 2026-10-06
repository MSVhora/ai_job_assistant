import json
import logging

import litellm
import pytest
from fakes import (
    embedding_response,
    install_acompletion,
    install_aembedding,
    llm_response,
)
from pydantic import BaseModel

from app.adapters.llm import (
    embed,
    estimate_cost,
    estimate_structured_cost,
    estimate_tokens,
    generate,
    parse_structured,
)
from app.core.config import get_settings

KNOWN_MODEL = "gemini/gemini-2.5-flash"
UNKNOWN_MODEL = "nope/unknown-model"


@pytest.fixture(autouse=True)
def price_map(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin LiteLLM's price map: $0.30 in / $2.50 out per million tokens."""

    def fake_cost_per_token(
        *, model: str, prompt_tokens: int, completion_tokens: int
    ) -> tuple[float, float]:
        if model not in {KNOWN_MODEL, get_settings().embedding_model}:
            raise litellm.exceptions.BadRequestError(
                message="unknown model", model=model, llm_provider="none"
            )
        return prompt_tokens * 0.30 / 1e6, completion_tokens * 2.50 / 1e6

    monkeypatch.setattr(litellm, "cost_per_token", fake_cost_per_token)


class Greeting(BaseModel):
    text: str


def test_estimate_cost_uses_the_price_map_for_known_models() -> None:
    estimate = estimate_cost(KNOWN_MODEL, 10_000, 2_000)

    assert estimate.usd == pytest.approx(0.003 + 0.005)
    assert estimate.basis == "litellm_price_map"
    assert (estimate.prompt_tokens, estimate.completion_tokens) == (10_000, 2_000)


def test_estimate_cost_is_unavailable_for_unknown_models() -> None:
    estimate = estimate_cost(UNKNOWN_MODEL, 10_000, 2_000)

    assert estimate.usd is None
    assert estimate.basis == "unavailable"


def test_price_overrides_win_over_the_map(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "llm_price_in_per_mtok", 1.0)
    monkeypatch.setattr(get_settings(), "llm_price_out_per_mtok", 4.0)

    estimate = estimate_cost(KNOWN_MODEL, 1_000_000, 500_000)

    assert estimate.usd == pytest.approx(1.0 + 2.0)
    assert estimate.basis == "configured_prices"


def test_overrides_make_an_unknown_model_priceable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "llm_price_in_per_mtok", 1.0)
    monkeypatch.setattr(get_settings(), "llm_price_out_per_mtok", 1.0)

    assert estimate_cost(UNKNOWN_MODEL, 1_000_000, 0).usd == pytest.approx(1.0)


def test_a_single_override_uses_the_map_for_the_other_direction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(get_settings(), "llm_price_in_per_mtok", 1.0)

    estimate = estimate_cost(KNOWN_MODEL, 1_000_000, 1_000_000)

    assert estimate.usd == pytest.approx(1.0 + 2.5)
    assert estimate.basis == "configured_prices"


def test_a_single_override_on_an_unknown_model_stays_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(get_settings(), "llm_price_in_per_mtok", 1.0)

    assert estimate_cost(UNKNOWN_MODEL, 10, 10).usd is None


def test_embedding_model_is_priced_on_prompt_tokens_with_its_own_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(get_settings(), "embedding_price_per_mtok", 0.5)

    estimate = estimate_cost(get_settings().embedding_model, 2_000_000)

    assert estimate.usd == pytest.approx(1.0)


def test_estimate_tokens_counts_a_prompt() -> None:
    short = estimate_tokens([{"role": "user", "content": "hello"}])
    long = estimate_tokens([{"role": "user", "content": "hello world " * 100}])

    assert 0 < short < long


def test_estimate_structured_cost_includes_the_schema_overhead() -> None:
    plain = estimate_tokens([{"role": "user", "content": "hi"}])

    estimate = estimate_structured_cost("hi", schema=Greeting, expected_completion_tokens=50)

    assert estimate.prompt_tokens > plain
    assert estimate.completion_tokens == 50


async def test_generate_logs_and_returns_cost(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger="app.adapters.llm")
    install_acompletion(
        monkeypatch, lambda **kw: llm_response("ok", prompt_tokens=1000, completion_tokens=200)
    )

    result = await generate("prompt")

    assert result.cost_usd == pytest.approx(0.0003 + 0.0005)
    assert "cost_usd=0.000800" in caplog.text


async def test_unknown_model_logs_cost_unknown(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger="app.adapters.llm")
    monkeypatch.setattr(get_settings(), "llm_model", UNKNOWN_MODEL)
    install_acompletion(monkeypatch, lambda **kw: llm_response("ok"))

    result = await generate("prompt")

    assert result.cost_usd is None
    assert "cost_usd=unknown" in caplog.text


async def test_embed_logs_and_returns_cost(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger="app.adapters.llm")
    install_aembedding(
        monkeypatch, lambda **kw: embedding_response([[0.1]], prompt_tokens=1_000_000)
    )

    result = await embed(["text"])

    assert result.cost_usd == pytest.approx(0.30)
    assert "cost_usd=0.300000" in caplog.text


async def test_parse_structured_sums_the_repair_call_cost(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger="app.adapters.llm")
    responses = iter(
        [
            llm_response("not json", prompt_tokens=1000, completion_tokens=0),
            llm_response(json.dumps({"text": "hi"}), prompt_tokens=1000, completion_tokens=100),
        ]
    )
    install_acompletion(monkeypatch, lambda **kw: next(responses))

    result = await parse_structured("prompt", schema=Greeting)

    assert result.data.text == "hi"
    assert result.cost_usd == pytest.approx(0.0003 + 0.0003 + 0.00025)
    assert "llm.parse_structured" in caplog.text
    assert "cost_usd=0.000850" in caplog.text
