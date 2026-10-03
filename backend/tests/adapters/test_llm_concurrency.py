import asyncio

import litellm
import pytest
from fakes import llm_response

from app.adapters.llm import generate
from app.core.config import get_settings


class InFlightProbe:
    def __init__(self) -> None:
        self.current = 0
        self.peak = 0

    async def __call__(self, **_: object) -> object:
        self.current += 1
        self.peak = max(self.peak, self.current)
        await asyncio.sleep(0.01)
        self.current -= 1
        return llm_response("ok")


async def _burst(calls: int) -> None:
    await asyncio.gather(*(generate(f"p{i}") for i in range(calls)))


@pytest.mark.parametrize("cap", [1, 2, 3])
def test_parallel_calls_never_exceed_the_configured_cap(
    cap: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "llm_max_concurrency", cap)
    probe = InFlightProbe()
    monkeypatch.setattr(litellm, "acompletion", probe)

    asyncio.run(_burst(9))

    assert probe.peak == cap


def test_the_cap_holds_across_sequential_event_loops(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "llm_max_concurrency", 2)
    probe = InFlightProbe()
    monkeypatch.setattr(litellm, "acompletion", probe)

    asyncio.run(_burst(6))
    asyncio.run(_burst(6))

    assert probe.peak == 2
    assert probe.current == 0
