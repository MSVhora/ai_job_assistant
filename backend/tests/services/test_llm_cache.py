import json

import pytest
from fakes import install_acompletion, llm_response
from pydantic import BaseModel
from sqlalchemy import select, text

from app.adapters.llm import LLMTask, StructuredResult, parse_structured, usage_meter
from app.core.config import get_settings
from app.core.db import session_factory
from app.models import LLMOutputCache
from app.services.llm_cache import cache_key, cached_parse_structured

pytestmark = pytest.mark.usefixtures("clean_tables")


class Claim(BaseModel):
    title: str


@pytest.fixture(autouse=True)
async def _empty_cache(clean_tables: None):
    async with session_factory() as session:
        await session.execute(text("DELETE FROM llm_output_cache"))
        await session.commit()
    yield
    async with session_factory() as session:
        await session.execute(text("DELETE FROM llm_output_cache"))
        await session.commit()


async def _lookup(
    session, calls_probe: list[dict[str, object]], *, version: str = "v1", parts: object = "chunk A"
) -> StructuredResult[Claim]:
    return await cached_parse_structured(
        session,
        task=LLMTask.extract,
        prompt_version=version,
        key_parts=parts,
        schema=Claim,
        call=lambda: parse_structured("p", schema=Claim, task=LLMTask.extract),
    )


def _provider(
    monkeypatch: pytest.MonkeyPatch, title: str = "Led migration"
) -> list[dict[str, object]]:
    return install_acompletion(monkeypatch, lambda **_: llm_response(json.dumps({"title": title})))


async def test_miss_calls_the_provider_once_and_stores_the_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _provider(monkeypatch)

    async with session_factory() as session:
        result = await _lookup(session, calls)
        await session.commit()

    assert result.data.title == "Led migration"
    assert len(calls) == 1
    async with session_factory() as session:
        row = (await session.execute(select(LLMOutputCache))).scalar_one()
    assert (row.task, row.prompt_version, row.output) == (
        "extract",
        "v1",
        {"title": "Led migration"},
    )
    assert row.model == get_settings().llm_model


async def test_hit_makes_no_provider_call_and_costs_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _provider(monkeypatch)
    async with session_factory() as session:
        await _lookup(session, calls)
        await session.commit()

    with usage_meter() as meter:
        async with session_factory() as session:
            hit = await _lookup(session, calls)

    assert len(calls) == 1
    assert hit.data.title == "Led migration"
    assert (hit.prompt_tokens, hit.completion_tokens, hit.cost_usd) == (0, 0, 0.0)
    assert (meter.cache_hits, meter.cache_misses) == (1, 0)


@pytest.mark.parametrize("change", ["version", "input", "model"])
async def test_changed_version_input_or_model_is_a_miss(
    change: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _provider(monkeypatch)
    async with session_factory() as session:
        await _lookup(session, calls)
        await session.commit()

    if change == "model":
        monkeypatch.setattr(get_settings(), "llm_model_extract", "custom/other-model")
    async with session_factory() as session:
        await _lookup(
            session,
            calls,
            version="v2" if change == "version" else "v1",
            parts="chunk B" if change == "input" else "chunk A",
        )
        await session.commit()

    assert len(calls) == 2
    async with session_factory() as session:
        rows = (await session.execute(select(LLMOutputCache))).scalars().all()
    assert len(rows) == 2


async def test_corrupt_cached_output_is_a_miss_and_is_overwritten(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _provider(monkeypatch, "Fresh title")
    key = cache_key(LLMTask.extract, get_settings().llm_model, "v1", "chunk A")
    async with session_factory() as session:
        session.add(
            LLMOutputCache(
                key=key,
                task="extract",
                model=get_settings().llm_model,
                prompt_version="v1",
                output={"wrong": "shape"},
                prompt_tokens=0,
                completion_tokens=0,
            )
        )
        await session.commit()

    async with session_factory() as session:
        result = await _lookup(session, calls)
        await session.commit()
        again = await _lookup(session, calls)

    assert result.data.title == "Fresh title"
    assert again.data.title == "Fresh title"
    assert len(calls) == 1
    async with session_factory() as session:
        stored = (await session.execute(select(LLMOutputCache))).scalar_one()
    assert stored.output == {"title": "Fresh title"}


def test_cache_key_is_canonical_and_input_sensitive() -> None:
    same_a = cache_key(LLMTask.extract, "m", "v1", {"b": 1, "a": [1, 2]})
    same_b = cache_key(LLMTask.extract, "m", "v1", {"a": [1, 2], "b": 1})

    assert same_a == same_b
    assert len(same_a) == 64
    assert cache_key(LLMTask.write, "m", "v1", {"b": 1, "a": [1, 2]}) != same_a
