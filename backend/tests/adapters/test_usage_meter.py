import json

import pytest
from fakes import embedding_response, install_acompletion, install_aembedding, llm_response
from pydantic import BaseModel

from app.adapters.llm import (
    LLMTask,
    embed,
    generate,
    parse_structured,
    record_cache_lookup,
    usage_meter,
)
from app.core.config import get_settings


class Item(BaseModel):
    name: str


@pytest.fixture(autouse=True)
def _flat_prices(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "llm_price_in_per_mtok", 1.0)
    monkeypatch.setattr(settings, "llm_price_out_per_mtok", 2.0)
    monkeypatch.setattr(settings, "embedding_price_per_mtok", 0.5)


async def test_meter_accumulates_tokens_and_cost_per_task(monkeypatch: pytest.MonkeyPatch) -> None:
    install_acompletion(
        monkeypatch,
        lambda **_: llm_response("x", prompt_tokens=1_000_000, completion_tokens=500_000),
    )

    with usage_meter() as meter:
        await generate("a", task=LLMTask.extract)
        await generate("b", task=LLMTask.extract)
        await generate("c", task=LLMTask.write)
        await generate("d")

    assert meter.tasks["extract"].calls == 2
    assert meter.tasks["extract"].prompt_tokens == 2_000_000
    assert meter.tasks["write"].completion_tokens == 500_000
    assert set(meter.tasks) == {"extract", "write", "default"}
    assert meter.prompt_tokens == 4_000_000
    assert meter.completion_tokens == 2_000_000
    assert meter.cost_usd == pytest.approx(4 * (1.0 + 1.0))


async def test_meter_cost_is_unavailable_when_any_call_is_unpriced(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "llm_price_in_per_mtok", None)
    monkeypatch.setattr(settings, "llm_price_out_per_mtok", None)
    monkeypatch.setattr(settings, "llm_model_judge", "nope/unpriced-model")
    install_acompletion(monkeypatch, lambda **_: llm_response("x"))

    with usage_meter() as meter:
        await generate("a", task=LLMTask.judge)

    assert meter.tasks["judge"].cost_usd is None
    assert meter.cost_usd is None
    assert meter.prompt_tokens == 10


async def test_nested_meters_are_isolated(monkeypatch: pytest.MonkeyPatch) -> None:
    install_acompletion(monkeypatch, lambda **_: llm_response("x"))

    with usage_meter() as outer:
        await generate("a")
        with usage_meter() as inner:
            await generate("b")
            await generate("c")
        await generate("d")

    assert outer.tasks["default"].calls == 2
    assert inner.tasks["default"].calls == 2


async def test_calls_outside_a_meter_are_not_recorded(monkeypatch: pytest.MonkeyPatch) -> None:
    install_acompletion(monkeypatch, lambda **_: llm_response("x"))

    await generate("a")
    record_cache_lookup(hit=True)

    with usage_meter() as meter:
        pass
    assert meter.tasks == {}
    assert meter.cache_hits == 0


async def test_meter_counts_repair_calls_embeddings_and_cache_lookups(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    replies = iter(["oops", json.dumps({"name": "a"})])
    install_acompletion(monkeypatch, lambda **_: llm_response(next(replies)))
    install_aembedding(
        monkeypatch, lambda **kw: embedding_response([[0.0] * 768 for _ in kw["input"]])
    )

    with usage_meter() as meter:
        await parse_structured("p", schema=Item, task=LLMTask.extract)
        await embed(["a", "b"])
        record_cache_lookup(hit=True)
        record_cache_lookup(hit=False)
        record_cache_lookup(hit=False)

    assert meter.tasks["extract"].calls == 2
    assert meter.tasks["embed"].calls == 1
    assert (meter.cache_hits, meter.cache_misses) == (1, 2)
