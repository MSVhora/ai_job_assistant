import pytest
from fakes import install_acompletion, llm_response
from pydantic import BaseModel

from app.adapters.llm import LLMTask, generate, model_for, parse_structured
from app.core.config import get_settings


class Verdict(BaseModel):
    ok: bool


@pytest.fixture(autouse=True)
def _clear_task_models(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    for task in LLMTask:
        monkeypatch.setattr(settings, f"llm_model_{task.value}", None)


def test_model_for_without_task_or_override_uses_the_default_model() -> None:
    assert model_for() == get_settings().llm_model
    for task in LLMTask:
        assert model_for(task) == get_settings().llm_model


@pytest.mark.parametrize("task", list(LLMTask))
def test_model_for_honours_each_task_setting(
    task: LLMTask, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), f"llm_model_{task.value}", f"custom/{task.value}-model")

    assert model_for(task) == f"custom/{task.value}-model"
    assert {model_for(other) for other in LLMTask if other is not task} == {
        get_settings().llm_model
    }
    assert model_for() == get_settings().llm_model


async def test_generate_sends_the_routed_model_to_the_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(get_settings(), "llm_model_write", "unknown-vendor/odd-model")
    calls = install_acompletion(monkeypatch, lambda **_: llm_response("hi"))

    await generate("p", task=LLMTask.write)
    await generate("p", task=LLMTask.extract)
    await generate("p")

    assert [call["model"] for call in calls] == [
        "unknown-vendor/odd-model",
        get_settings().llm_model,
        get_settings().llm_model,
    ]


async def test_parse_structured_routes_both_the_call_and_the_repair(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(get_settings(), "llm_model_judge", "custom/judge")
    replies = iter(["not json", '{"ok": true}'])
    calls = install_acompletion(monkeypatch, lambda **_: llm_response(next(replies)))

    result = await parse_structured("p", schema=Verdict, task=LLMTask.judge)

    assert result.data.ok is True
    assert [call["model"] for call in calls] == ["custom/judge", "custom/judge"]
