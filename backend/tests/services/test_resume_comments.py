import json
import uuid
from typing import Any

import pytest
from fakes import FakeResumeLLM, install_acompletion, seed_resume_world
from pydantic import ValidationError

from app.core.config import get_settings
from app.core.db import session_factory
from app.core.errors import (
    CommentNotFoundError,
    InvalidCommentTargetError,
    ResumeDocumentNotFoundError,
)
from app.schemas.resume_document import (
    BulletUpdate,
    CommentCreate,
    CommentTarget,
    CommentUpdate,
    ResumeDocumentCreate,
    ResumeDocumentResponse,
)
from app.services import resume_builder, resume_bullets, resume_comments

pytestmark = pytest.mark.usefixtures("clean_tables")


@pytest.fixture(autouse=True)
def _settings(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "gemini_api_key", "test-key")
    monkeypatch.setattr(settings, "llm_retry_attempts", 1)
    monkeypatch.setattr(settings, "llm_retry_base_delay_s", 0.0)


async def call(fn: Any, *args: Any) -> Any:
    async with session_factory() as session:
        result = await fn(session, *args)
        await session.commit()
        return result


async def generated(
    monkeypatch: pytest.MonkeyPatch, **kwargs: Any
) -> tuple[FakeResumeLLM, ResumeDocumentResponse, dict[str, Any]]:
    world = await seed_resume_world()
    llm = FakeResumeLLM(**kwargs)
    install_acompletion(monkeypatch, llm)
    document = await call(
        resume_builder.create_and_generate, ResumeDocumentCreate(profile_id=world["profile"])
    )
    return llm, document, world


def job(document: ResumeDocumentResponse, company: str) -> Any:
    return next(item for item in document.content.work if item.company == company)


def comment(document: ResumeDocumentResponse, company: str, text: str, **target: Any) -> Any:
    entry = job(document, company)
    return CommentCreate(
        target=CommentTarget(section="work", block_id=entry.id, **target), text=text
    )


async def test_a_rewrite_comment_regenerates_only_the_commented_block(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    llm, document, _ = await generated(monkeypatch)
    beta_before = json.dumps(job(document, "Beta Inc").model_dump(mode="json"), sort_keys=True)
    project_before = document.content.projects[0].model_dump()
    llm.texts["Faster nightly import"] = "Cut nightly import time by batching writes in Python"
    writes_before = llm.count("write")

    await call(
        resume_comments.add_comment,
        document.id,
        comment(document, "Acme Corp", "emphasize the batching, drop the platform wording"),
    )
    applied = await call(resume_comments.apply_comments, document.id)

    assert llm.count("write") == writes_before + 1
    acme = job(applied, "Acme Corp")
    assert "Cut nightly import time by batching writes in Python" in [
        b.text for b in acme.highlights
    ]
    assert (
        json.dumps(job(applied, "Beta Inc").model_dump(mode="json"), sort_keys=True) == beta_before
    )
    assert applied.content.projects[0].model_dump() == project_before
    assert [(c.status, c.reason) for c in applied.comments] == [("applied", None)]
    instruction = llm.items("Faster nightly import")[-1]["instruction"]
    assert "emphasize the batching" in instruction
    assert llm.items("Faster nightly import")[-1]["previous"] is not None


async def test_pinned_bullets_survive_and_a_pinned_target_is_not_applied(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, document, _ = await generated(monkeypatch)
    first = job(document, "Acme Corp").highlights[0]
    pinned = await call(
        resume_bullets.update_bullet, document.id, first.id, BulletUpdate(pinned=True)
    )
    await call(
        resume_comments.add_comment,
        document.id,
        comment(pinned, "Acme Corp", "shorten this", bullet_id=first.id),
    )

    applied = await call(resume_comments.apply_comments, document.id)

    kept = next(b for b in job(applied, "Acme Corp").highlights if b.id == first.id)
    assert kept.text == first.text
    assert applied.comments[0].status == "rejected"
    assert "pinned" in (applied.comments[0].reason or "")


async def test_a_comment_asking_for_an_unsupported_tool_is_rejected_with_add_note(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    llm, document, _ = await generated(monkeypatch)
    content_before = document.content.model_dump()
    writes_before = llm.count("write")

    await call(
        resume_comments.add_comment,
        document.id,
        comment(document, "Acme Corp", "add Kubernetes to the first bullet"),
    )
    applied = await call(resume_comments.apply_comments, document.id)

    rejected = applied.comments[0]
    assert (rejected.status, rejected.action) == ("rejected", "add_note")
    assert "Kubernetes" in (rejected.reason or "")
    assert llm.count("write") == writes_before
    assert applied.content.model_dump() == content_before


async def test_a_writer_that_declines_rejects_the_comment(monkeypatch: pytest.MonkeyPatch) -> None:
    llm, document, _ = await generated(monkeypatch)
    llm.writer = lambda _key, item, _current: "" if item["instruction"] else None

    await call(
        resume_comments.add_comment,
        document.id,
        comment(document, "Acme Corp", "mention the cost savings"),
    )
    applied = await call(resume_comments.apply_comments, document.id)

    assert (applied.comments[0].status, applied.comments[0].action) == ("rejected", "add_note")
    assert "not in evidence" in (applied.comments[0].reason or "")


async def test_rewritten_bullets_go_through_the_same_verifier(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    llm, document, _ = await generated(monkeypatch)
    llm.writer = lambda _key, item, _current: (
        "Delivered the import for 900 customers" if item["instruction"] else None
    )

    await call(
        resume_comments.add_comment,
        document.id,
        comment(document, "Acme Corp", "make it about customers"),
    )
    applied = await call(resume_comments.apply_comments, document.id)

    flagged = [b for b in job(applied, "Acme Corp").highlights if b.check == "needs_review"]
    assert flagged
    assert any("900" in flag for flag in flagged[0].flags)
    assert applied.comments[0].status == "applied"


async def test_applied_comments_stay_as_history_and_open_ones_are_not_reapplied(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    llm, document, _ = await generated(monkeypatch)
    await call(
        resume_comments.add_comment,
        document.id,
        comment(document, "Acme Corp", "tighten the wording"),
    )
    first = await call(resume_comments.apply_comments, document.id)
    writes = llm.count("write")

    second = await call(resume_comments.apply_comments, document.id)

    assert llm.count("write") == writes
    assert [c.status for c in second.comments] == ["applied"]
    assert second.comments[0].resolved_at is not None
    assert first.comments[0].id == second.comments[0].id


async def test_invalid_targets_are_unprocessable_and_comments_can_be_edited_and_deleted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, document, _ = await generated(monkeypatch)
    entry = job(document, "Acme Corp")

    with pytest.raises(InvalidCommentTargetError):
        await call(
            resume_comments.add_comment,
            document.id,
            CommentCreate(target=CommentTarget(section="work", block_id="nope"), text="x"),
        )
    with pytest.raises(InvalidCommentTargetError):
        await call(
            resume_comments.add_comment,
            document.id,
            CommentCreate(target=CommentTarget(section="projects", block_id=entry.id), text="x"),
        )
    with pytest.raises(InvalidCommentTargetError):
        await call(
            resume_comments.add_comment,
            document.id,
            comment(document, "Acme Corp", "x", bullet_id="missing"),
        )

    added = await call(
        resume_comments.add_comment, document.id, comment(document, "Acme Corp", "a")
    )
    comment_id = added.comments[0].id
    edited = await call(
        resume_comments.update_comment, document.id, comment_id, CommentUpdate(text="b")
    )
    removed = await call(resume_comments.delete_comment, document.id, comment_id)

    assert edited.comments[0].text == "b"
    assert removed.comments == []
    with pytest.raises(CommentNotFoundError):
        await call(resume_comments.delete_comment, document.id, comment_id)
    with pytest.raises(CommentNotFoundError):
        await call(resume_comments.update_comment, document.id, "x", CommentUpdate(text="b"))


async def test_comment_text_is_bounded() -> None:
    with pytest.raises(ValidationError):
        CommentCreate(target=CommentTarget(section="work", block_id="a"), text="x" * 1001)


async def test_every_comment_operation_404s_for_an_unknown_document(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, document, _ = await generated(monkeypatch)
    missing = uuid.uuid4()
    target = comment(document, "Acme Corp", "a")

    for operation, args in [
        (resume_comments.add_comment, (missing, target)),
        (resume_comments.update_comment, (missing, "x", CommentUpdate(text="b"))),
        (resume_comments.delete_comment, (missing, "x")),
        (resume_comments.apply_comments, (missing,)),
    ]:
        with pytest.raises(ResumeDocumentNotFoundError):
            await call(operation, *args)
