from typing import Any

import pytest
from fakes import FakeResumeLLM, install_acompletion, seed_resume_world

from app.adapters.llm import LLMError
from app.core.config import get_settings
from app.core.db import session_factory
from app.schemas.resume_document import JDAnalysis
from app.services import resume_documents
from app.services.resume_builder import load_links
from app.services.resume_verify import numbers_in
from app.services.resume_writer import (
    JUDGE_UNAVAILABLE,
    BlockSpec,
    WriteItem,
    WrittenItem,
    build_item,
    write_block,
)

pytestmark = pytest.mark.usefixtures("clean_tables")

PAST = BlockSpec("acme", "Senior Engineer at Acme Corp", current=False)
CURRENT = BlockSpec("beta", "Engineer at Beta Inc", current=True)


@pytest.fixture(autouse=True)
def _settings(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "gemini_api_key", "test-key")
    monkeypatch.setattr(settings, "llm_retry_attempts", 1)
    monkeypatch.setattr(settings, "llm_retry_base_delay_s", 0.0)


async def items_for(
    *titles: str, jd: JDAnalysis | None = None
) -> tuple[list[WriteItem], dict[str, Any]]:
    world = await seed_resume_world()
    async with session_factory() as session:
        achievements = await resume_documents.approved_achievements(session, world["candidate"])
        links = await load_links(session, [a.id for a in achievements])
    chosen = [a for a in achievements if a.title in titles]
    built = [build_item(f"A{n}", a, links[a.id], jd, 0.5) for n, a in enumerate(chosen, start=1)]
    return built, world


async def run(block: BlockSpec, items: list[WriteItem]) -> list[WrittenItem]:
    async with session_factory() as session:
        result = await write_block(session, block, items)
        await session.commit()
        return result


async def test_no_golden_achievement_yields_a_fabricated_number(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    items, _ = await items_for(
        "Faster nightly import",
        "Retry budget for the loader",
        "Kubernetes rollout",
        "Docs generator",
    )
    install_acompletion(monkeypatch, FakeResumeLLM())

    written = await run(PAST, items)

    for result in written:
        assert result.bullet is not None
        assert numbers_in(result.bullet.text) <= result.item.source.numbers
        assert result.bullet.check == "passed"
        assert result.bullet.evidence_ids == [result.item.snippets[0].item_id]


async def test_a_lint_failure_triggers_exactly_one_regeneration_then_needs_review(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    items, _ = await items_for("Docs generator")
    llm = FakeResumeLLM(writer=lambda *_: "Successfully wrote a robust docs generator")
    install_acompletion(monkeypatch, llm)

    written = await run(PAST, items)

    assert llm.count("write") == 2
    assert written[0].bullet is not None
    assert written[0].bullet.check == "needs_review"
    assert "uses the filler 'successfully'" in written[0].bullet.flags
    second_request = llm.items("Docs generator")[1]
    assert second_request["previous"] == "Successfully wrote a robust docs generator"
    assert "uses the filler 'robust'" in second_request["violations"]


async def test_an_ownership_upgrade_is_caught_and_repaired(monkeypatch: pytest.MonkeyPatch) -> None:
    items, _ = await items_for("Retry budget for the loader")

    def writer(_key: str, item: dict[str, Any], _current: bool) -> str | None:
        return (
            "Led the retry budget for the loader"
            if item["previous"] is None
            else "Contributed a retry budget for the loader"
        )

    llm = FakeResumeLLM(writer=writer)
    install_acompletion(monkeypatch, llm)

    written = await run(PAST, items)

    assert (
        "'led' claims more ownership than the evidence shows"
        in llm.items("Retry budget for the loader")[1]["violations"]
    )
    assert written[0].bullet is not None
    assert (written[0].bullet.text, written[0].bullet.check) == (
        "Contributed a retry budget for the loader",
        "passed",
    )


async def test_the_second_run_is_served_from_the_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    items, _ = await items_for("Faster nightly import", "Docs generator")
    llm = FakeResumeLLM()
    install_acompletion(monkeypatch, llm)

    first = await run(PAST, items)
    calls = len(llm.calls)
    second = await run(PAST, items)

    assert len(llm.calls) == calls
    assert [w.bullet for w in first] == [w.bullet for w in second]


async def test_tense_follows_the_block(monkeypatch: pytest.MonkeyPatch) -> None:
    items, _ = await items_for("Docs generator")
    install_acompletion(monkeypatch, FakeResumeLLM())

    past = await run(PAST, items)
    current = await run(CURRENT, items)

    assert past[0].bullet is not None
    assert current[0].bullet is not None
    assert past[0].bullet.text.startswith("Delivered")
    assert current[0].bullet.text.startswith("Deliver ")


async def test_a_declined_item_is_rejected_not_written(monkeypatch: pytest.MonkeyPatch) -> None:
    items, _ = await items_for("Docs generator")
    install_acompletion(monkeypatch, FakeResumeLLM(writer=lambda *_: ""))

    written = await run(PAST, items)

    assert (written[0].bullet, written[0].rejected_reason) == (None, "not in evidence")


async def test_a_missing_bullet_is_repaired_once(monkeypatch: pytest.MonkeyPatch) -> None:
    items, _ = await items_for("Docs generator")
    llm = FakeResumeLLM(drop_first_write=True)
    install_acompletion(monkeypatch, llm)

    written = await run(PAST, items)

    assert llm.count("write") == 2
    assert written[0].bullet is not None
    assert written[0].bullet.check == "passed"


async def test_an_unavailable_judge_flags_for_review_without_a_regeneration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    items, _ = await items_for("Docs generator")
    llm = FakeResumeLLM()

    def handler(**kwargs: Any) -> object:
        if "check resume bullets" in kwargs["messages"][0]["content"]:
            return LLMError("down")
        return llm(**kwargs)

    install_acompletion(monkeypatch, handler)

    written = await run(PAST, items)

    assert llm.count("write") == 1
    assert written[0].bullet is not None
    assert written[0].bullet.flags == [JUDGE_UNAVAILABLE]
    assert written[0].bullet.check == "needs_review"


async def test_more_than_eight_items_are_written_in_chunks(monkeypatch: pytest.MonkeyPatch) -> None:
    items, _ = await items_for("Docs generator")
    many = [WriteItem(**{**item.__dict__, "key": f"A{n}"}) for n, item in enumerate(items * 9, 1)]
    llm = FakeResumeLLM()
    install_acompletion(monkeypatch, llm)

    written = await run(PAST, many)

    assert llm.count("write") == 2
    assert len(written) == 9


async def test_jd_wording_is_offered_only_for_supported_terms() -> None:
    jd = JDAnalysis(keywords=["Kubernetes", "Snowflake"])
    items, _ = await items_for("Kubernetes rollout", "Docs generator", jd=jd)

    rollout = next(i for i in items if i.facts["title"] == "Kubernetes rollout")
    docs = next(i for i in items if i.facts["title"] == "Docs generator")

    assert [t.wording for t in rollout.allowed] == ["Kubernetes"]
    assert rollout.disallowed == ("Snowflake",)
    assert docs.allowed == ()
    assert set(docs.disallowed) == {"Kubernetes", "Snowflake"}


async def test_evidence_is_redacted_before_it_reaches_the_prompt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    world = await seed_resume_world(
        extra=[
            {
                "key": "pii",
                "title": "Contact importer",
                "employer_ref": {"company": "Acme Corp", "start_date": "Jan 2019"},
                "body": "Wrote the importer; owner is jane.roe@example.com",
                "skills": ["Python"],
                "difficulty": 2,
                "impact_type": "other",
                "start": (2020, 1, 1),
            }
        ]
    )
    async with session_factory() as session:
        achievements = await resume_documents.approved_achievements(session, world["candidate"])
        links = await load_links(session, [a.id for a in achievements])
    target = next(a for a in achievements if a.title == "Contact importer")

    item = build_item("A1", target, links[target.id], None, 0.5)

    assert "jane.roe@example.com" not in " ".join(item.evidence_lines)
