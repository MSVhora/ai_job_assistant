import uuid

import pytest
from sqlalchemy import select

from app.core.db import session_factory
from app.core.errors import DuplicateEvidenceError, EvidenceItemNotFoundError
from app.models import Candidate, EvidenceItem, EvidenceItemStatus, EvidenceKind
from app.schemas.evidence import LinkCreate, NoteCreate, NoteUpdate
from app.services import evidence_notes

pytestmark = pytest.mark.usefixtures("clean_tables")


async def items() -> list[EvidenceItem]:
    async with session_factory() as session:
        return list((await session.execute(select(EvidenceItem))).scalars().all())


async def test_create_note_stores_a_kept_note_with_a_slugged_project_key() -> None:
    async with session_factory() as session:
        created = await evidence_notes.create_note(
            session, NoteCreate(title="Payments Migration!", body="Moved 40 services.")
        )
        await session.commit()

    assert created.kind is EvidenceKind.note
    assert created.project_key == "note:payments-migration"
    assert created.status is EvidenceItemStatus.kept
    assert created.occurred_at is not None


async def test_duplicate_note_content_is_a_conflict() -> None:
    async with session_factory() as session:
        await evidence_notes.create_note(session, NoteCreate(title="A", body="Same text"))
        await session.commit()

    async with session_factory() as session:
        with pytest.raises(DuplicateEvidenceError):
            await evidence_notes.create_note(session, NoteCreate(title="A", body="Same text"))


async def test_editing_a_note_supersedes_the_old_version() -> None:
    async with session_factory() as session:
        original = await evidence_notes.create_note(session, NoteCreate(body="First draft"))
        await session.commit()

    async with session_factory() as session:
        updated, _ = await evidence_notes.update_note(
            session, original.id, NoteUpdate(body="Second draft with detail")
        )
        await session.commit()

    assert updated.id != original.id
    stored = {item.id: item for item in await items()}
    assert stored[original.id].status is EvidenceItemStatus.excluded
    assert stored[original.id].meta["superseded_by"] == str(updated.id)
    assert stored[updated.id].status is EvidenceItemStatus.kept


async def test_editing_with_identical_content_changes_nothing() -> None:
    async with session_factory() as session:
        original = await evidence_notes.create_note(session, NoteCreate(title="T", body="Body"))
        await session.commit()

    async with session_factory() as session:
        same, _ = await evidence_notes.update_note(session, original.id, NoteUpdate(body="Body"))
        await session.commit()

    assert same.id == original.id
    assert len(await items()) == 1


async def test_title_can_be_cleared_by_sending_null() -> None:
    async with session_factory() as session:
        original = await evidence_notes.create_note(session, NoteCreate(title="T", body="Body"))
        await session.commit()

    async with session_factory() as session:
        updated, _ = await evidence_notes.update_note(
            session, original.id, NoteUpdate.model_validate({"title": None})
        )
        await session.commit()

    assert updated.title is None
    assert updated.body == "Body"


async def test_deleting_a_note_excludes_it_and_it_can_be_recreated() -> None:
    async with session_factory() as session:
        created = await evidence_notes.create_note(session, NoteCreate(body="Keep me"))
        await session.commit()
    async with session_factory() as session:
        await evidence_notes.delete_note(session, created.id)
        await session.commit()

    async with session_factory() as session:
        notes, total = await evidence_notes.list_notes(session)
        assert (notes, total) == ([], 0)
        revived = await evidence_notes.create_note(session, NoteCreate(body="Keep me"))
        await session.commit()

    assert revived.id == created.id
    assert revived.status is EvidenceItemStatus.kept


async def test_unknown_foreign_and_non_note_ids_are_404() -> None:
    async with session_factory() as session:
        link = await evidence_notes.create_link(session, LinkCreate(url="https://example.com/talk"))
        stranger = Candidate()
        session.add(stranger)
        await session.flush()
        foreign = EvidenceItem(
            candidate_id=stranger.id,
            kind=EvidenceKind.note,
            external_id="x",
            body="not yours",
            content_hash="x",
        )
        session.add(foreign)
        await session.commit()
        foreign_id = foreign.id

    async with session_factory() as session:
        for item_id in (uuid.uuid4(), foreign_id, link.id):
            with pytest.raises(EvidenceItemNotFoundError):
                await evidence_notes.delete_note(session, item_id)
            with pytest.raises(EvidenceItemNotFoundError):
                await evidence_notes.update_note(session, item_id, NoteUpdate(body="x"))


async def test_links_are_stored_without_fetching_and_text_marks_them_chunkable() -> None:
    async with session_factory() as session:
        bare = await evidence_notes.create_link(
            session,
            LinkCreate(url="https://play.google.com/store/apps/details?id=x", title="My app"),
        )
        pasted = await evidence_notes.create_link(
            session,
            LinkCreate(url="https://example.com/post", text="Wrote about the loader design"),
        )
        await session.commit()

    assert bare.meta == {"url_only": True}
    assert bare.project_key == "link:play.google.com"
    assert bare.body == "My app"
    assert pasted.meta == {"url_only": False}
    assert pasted.body == "Wrote about the loader design"


async def test_duplicate_link_is_a_conflict() -> None:
    async with session_factory() as session:
        await evidence_notes.create_link(session, LinkCreate(url="https://example.com/a"))
        await session.commit()

    async with session_factory() as session:
        with pytest.raises(DuplicateEvidenceError):
            await evidence_notes.create_link(session, LinkCreate(url="https://example.com/a"))


@pytest.mark.parametrize(
    "url", ["javascript:alert(1)", "ftp://example.com/x", "file:///etc/passwd", "not a url"]
)
def test_only_http_and_https_links_validate(url: str) -> None:
    with pytest.raises(ValueError, match="url"):
        LinkCreate(url=url)  # type: ignore[arg-type]


def test_length_caps_and_empty_updates_are_rejected() -> None:
    with pytest.raises(ValueError, match="body"):
        NoteCreate(body="x" * 20_001)
    with pytest.raises(ValueError, match="title"):
        NoteCreate(title="t" * 201, body="ok")
    with pytest.raises(ValueError, match="send a title or a body"):
        NoteUpdate()
