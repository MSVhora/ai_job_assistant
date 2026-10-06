import uuid

import pytest
from fakes import FakeAgentLLM, install_acompletion

from app.core.config import get_settings
from app.services.agent_grounding import (
    check_answer,
    ground,
    markers_in,
    split_sentences,
    strip_markers,
)
from app.services.agent_retrieval import ContextBlock

ACHIEVEMENT = uuid.uuid4()
ITEM = uuid.uuid4()
BODY = "Cut the nightly import from 42 minutes to 9 minutes by batching writes in Python"


def blocks(*, private: bool = False) -> list[ContextBlock]:
    return [
        ContextBlock(
            marker="A1",
            kind="achievement",
            text=f"Title: Faster nightly import\nAction: {BODY}",
            corpus=(f"Title: Faster nightly import\nAction: {BODY}", BODY),
            skills=("Python",),
            achievement_id=ACHIEVEMENT,
            private=private,
        ),
        ContextBlock(
            marker="E1",
            kind="evidence",
            text=f"note: {BODY}",
            corpus=(BODY,),
            achievement_id=ACHIEVEMENT,
            evidence_item_id=ITEM,
            private=private,
        ),
        ContextBlock(
            marker="J",
            kind="job",
            text="Job: Data Engineer at Initech. We run Kafka and Airflow.",
            corpus=("Job: Data Engineer at Initech. We run Kafka and Airflow.",),
        ),
    ]


@pytest.fixture(autouse=True)
def _settings(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "gemini_api_key", "test-key")
    monkeypatch.setattr(settings, "llm_retry_attempts", 1)
    monkeypatch.setattr(settings, "llm_retry_base_delay_s", 0.0)


async def no_repair(_answer: str, _problems: list[str]) -> str:
    msg = "repair must not be called"
    raise AssertionError(msg)


def test_sentences_keep_their_markers_even_after_the_full_stop() -> None:
    parts = split_sentences("I cut it from 3.5 to 2 seconds. [A1] Then I shipped it [E1]. Done!")

    assert parts == ["I cut it from 3.5 to 2 seconds. [A1]", "Then I shipped it [E1].", "Done!"]
    assert markers_in(parts[0]) == ["A1"]
    assert strip_markers(parts[1]) == "Then I shipped it ."


async def test_a_supported_cited_sentence_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    llm = FakeAgentLLM()
    install_acompletion(monkeypatch, llm)
    answer = "I cut the nightly import from 42 minutes to 9 minutes by batching writes [A1][E1]."

    checked = await check_answer(answer, blocks())

    assert checked.flags == []
    assert llm.count("judge") == 1


@pytest.mark.parametrize(
    ("sentence", "fragment"),
    [
        ("I cut the nightly import from 42 minutes to 3 minutes by batching writes [A1].", "3"),
        ("I rewrote the import in Rust to speed it up [A1].", "Rust"),
        ("I shipped the batching change in v2.4.1 of the importer [A1].", "v2.4.1"),
        ("I tuned the import during 2019 for the finance team [A1].", "2019"),
    ],
)
async def test_an_unsupported_number_tool_version_or_year_is_caught(
    monkeypatch: pytest.MonkeyPatch, sentence: str, fragment: str
) -> None:
    install_acompletion(monkeypatch, FakeAgentLLM())

    checked = await check_answer(sentence, blocks())

    assert len(checked.flags) == 1
    assert fragment in checked.flags[0].reason


async def test_an_ownership_upgrade_is_caught(monkeypatch: pytest.MonkeyPatch) -> None:
    install_acompletion(monkeypatch, FakeAgentLLM())

    checked = await check_answer("I led the nightly import work in Python [A1].", blocks())

    assert "more ownership" in checked.flags[0].reason


async def test_a_factual_sentence_without_a_marker_is_flagged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_acompletion(monkeypatch, FakeAgentLLM())

    checked = await check_answer("I led the platform team for several years.", blocks())

    assert [flag.reason for flag in checked.flags] == [
        "states something about the candidate without citing evidence"
    ]


async def test_a_marker_that_is_not_a_source_is_flagged(monkeypatch: pytest.MonkeyPatch) -> None:
    install_acompletion(monkeypatch, FakeAgentLLM())

    checked = await check_answer("I batched the writes [A9].", blocks())

    assert "A9" in checked.flags[0].reason


async def test_the_job_description_cannot_back_a_claim_about_the_candidate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_acompletion(monkeypatch, FakeAgentLLM())

    checked = await check_answer("I built the Kafka pipeline [J].", blocks())

    assert "job description alone" in checked.flags[0].reason


async def test_the_judge_can_reject_a_sentence_the_rules_accept(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_acompletion(monkeypatch, FakeAgentLLM(judge_fail={"mentored"}))

    checked = await check_answer("I mentored two engineers on the import work [A1].", blocks())

    assert checked.flags[0].reason == "unsupported claim"


async def test_an_unavailable_judge_keeps_the_rule_checked_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_acompletion(monkeypatch, FakeAgentLLM(judge_error=True))

    checked = await check_answer("I batched the writes in Python [A1].", blocks())

    assert checked.flags == []
    assert checked.judge_unavailable is True


async def test_questions_and_offers_need_no_marker(monkeypatch: pytest.MonkeyPatch) -> None:
    install_acompletion(monkeypatch, FakeAgentLLM())

    checked = await check_answer(
        "Would you like me to go deeper? If you tell me why, I can make a note.",
        blocks(),
    )

    assert checked.flags == []


async def test_a_second_person_experience_claim_needs_a_marker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_acompletion(monkeypatch, FakeAgentLLM())

    checked = await check_answer("You mentored two interns during the migration.", blocks())

    assert [flag.reason for flag in checked.flags] == [
        "states something about the candidate without citing evidence"
    ]


async def test_one_repair_fixes_a_bad_sentence(monkeypatch: pytest.MonkeyPatch) -> None:
    llm = FakeAgentLLM()
    install_acompletion(monkeypatch, llm)
    repaired: list[list[str]] = []

    async def repair(_answer: str, problems: list[str]) -> str:
        repaired.append(problems)
        return "I batched the writes in Python [A1]."

    grounded = await ground("I batched the writes in Rust [A1].", blocks(), repair=repair)

    assert grounded.status == "grounded"
    assert grounded.repaired is True
    assert len(repaired) == 1
    assert "Rust" in repaired[0][0]
    assert grounded.markers == ["A1"]


async def test_a_still_failing_answer_keeps_only_the_grounded_subset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_acompletion(monkeypatch, FakeAgentLLM())

    async def repair(_answer: str, _problems: list[str]) -> str:
        return "I batched the writes in Python [A1]. I also rewrote it in Rust [A1]."

    grounded = await ground("I rewrote it in Rust [A1].", blocks(), repair=repair)

    assert grounded.status == "partial"
    assert grounded.text == "I batched the writes in Python [A1]."
    assert grounded.flagged_sentences == ["I also rewrote it in Rust [A1]."]


async def test_an_answer_with_nothing_grounded_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    install_acompletion(monkeypatch, FakeAgentLLM())

    async def repair(_answer: str, _problems: list[str]) -> str:
        return "I rewrote it in Rust [A1]."

    grounded = await ground("I rewrote it in Rust [A1].", blocks(), repair=repair)

    assert grounded.status == "refused"
    assert grounded.text == ""


async def test_a_valid_answer_is_not_repaired(monkeypatch: pytest.MonkeyPatch) -> None:
    install_acompletion(monkeypatch, FakeAgentLLM())

    grounded = await ground("I batched the writes in Python [A1].", blocks(), repair=no_repair)

    assert grounded.status == "grounded"
    assert grounded.repaired is False
