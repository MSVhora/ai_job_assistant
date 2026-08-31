import json

import pytest
from fakes import VALID_PROFILE, install_acompletion, llm_response

from app.adapters.llm import LLMError, parse_structured
from app.schemas.profile import StructuredProfile
from app.services import profile_extraction


async def test_valid_json_returns_validated_model(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = install_acompletion(monkeypatch, lambda **kw: llm_response(json.dumps(VALID_PROFILE)))

    result = await parse_structured("resume text", schema=StructuredProfile, system="rules")

    assert result.data.contact.full_name == "Jane Doe"
    assert result.data.experience[0].bullets == ["Led reporting", "Built dashboards"]
    assert result.prompt_tokens == 10
    assert result.completion_tokens == 5
    assert len(calls) == 1
    assert "response_format" not in calls[0]
    system_content = calls[0]["messages"][0]["content"]
    assert system_content.startswith("rules")
    assert "JSON schema" in system_content
    assert "extra_sections" in system_content


async def test_fenced_and_prose_wrapped_json_parsed(monkeypatch: pytest.MonkeyPatch) -> None:
    content = f"Here you go:\n```json\n{json.dumps(VALID_PROFILE)}\n```\nDone."
    install_acompletion(monkeypatch, lambda **kw: llm_response(content))

    result = await parse_structured("resume text", schema=StructuredProfile)

    assert result.data.contact.email == "jane@example.com"


async def test_invalid_output_triggers_single_repair(monkeypatch: pytest.MonkeyPatch) -> None:
    responses = iter(
        [
            llm_response(json.dumps({"skills": ["SQL"]}), prompt_tokens=7, completion_tokens=3),
            llm_response(json.dumps(VALID_PROFILE), prompt_tokens=11, completion_tokens=4),
        ]
    )
    calls = install_acompletion(monkeypatch, lambda **kw: next(responses))

    result = await parse_structured("resume text", schema=StructuredProfile)

    assert result.data.contact.full_name == "Jane Doe"
    assert result.prompt_tokens == 18
    assert result.completion_tokens == 7
    assert len(calls) == 2
    repair_messages = calls[1]["messages"]
    assert len(repair_messages) == 2
    assert "did not validate" in repair_messages[-1]["content"]
    assert "contact" in repair_messages[-1]["content"]


async def test_non_json_output_triggers_repair(monkeypatch: pytest.MonkeyPatch) -> None:
    responses = iter(
        [llm_response("I cannot help with that."), llm_response(json.dumps(VALID_PROFILE))]
    )
    calls = install_acompletion(monkeypatch, lambda **kw: next(responses))

    result = await parse_structured("resume text", schema=StructuredProfile)

    assert result.data.contact.full_name == "Jane Doe"
    assert len(calls) == 2


async def test_repair_failure_raises_llm_error(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = install_acompletion(
        monkeypatch, lambda **kw: llm_response(json.dumps({"skills": ["SQL"]}))
    )

    with pytest.raises(LLMError, match="failed validation after repair"):
        await parse_structured("resume text", schema=StructuredProfile)

    assert len(calls) == 2


def test_build_prompt_truncates_resume_text() -> None:
    prompt = profile_extraction._build_prompt("a" * 300, 50)

    assert "a" * 50 in prompt
    assert "a" * 51 not in prompt
