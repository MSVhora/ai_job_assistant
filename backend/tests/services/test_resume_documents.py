import uuid
from datetime import date
from typing import Any

import pytest
from fakes import golden_profile
from pydantic import ValidationError
from sqlalchemy import select

from app.adapters.evidence_sources.base import EvidenceSourceError
from app.core.config import get_settings
from app.core.db import session_factory
from app.core.errors import (
    ConflictNotFoundError,
    MatchNotFoundError,
    ProfileNotFoundError,
    ResumeDocumentNotFoundError,
)
from app.core.pagination import Pagination
from app.models import (
    Achievement,
    AchievementStatus,
    Candidate,
    Profile,
    ResumeDocument,
    ResumeDocumentRevision,
)
from app.schemas.evidence import SourceIdentity
from app.schemas.resume_document import (
    ResolveConflictRequest,
    ResumeDocumentCreate,
    ResumeDocumentUpdate,
)
from app.services import resume_documents as documents

pytestmark = pytest.mark.usefixtures("clean_tables")

ENGINE = {"company": "Engine Co", "start_date": "Jan 2020", "source": "user"}
BABBAGE = {"company": "Babbage Systems", "start_date": "Jul 2023", "source": "user"}
GHOST = {"company": "Ghost Corp", "start_date": "2019", "source": "user"}
LATENCY = {
    "text": "reduced p95 latency by 40%",
    "source_quote": "q",
    "evidence_ids": [],
    "verified": "evidence",
}


class FakeGitHub:
    def __init__(self, identity: SourceIdentity | Exception | None) -> None:
        self.identity = identity

    def is_configured(self) -> bool:
        return self.identity is not None

    async def identify(self) -> SourceIdentity:
        if isinstance(self.identity, Exception):
            raise self.identity
        assert self.identity is not None
        return self.identity


@pytest.fixture
def github(monkeypatch: pytest.MonkeyPatch) -> Any:
    def install(identity: SourceIdentity | Exception | None) -> None:
        monkeypatch.setattr(documents, "get_source", lambda _name: FakeGitHub(identity))

    install(SourceIdentity(login="ada", name="Augusta Byron", location="London, England"))
    return install


async def call(fn: Any, *args: Any, **kwargs: Any) -> Any:
    async with session_factory() as session:
        result = await fn(session, *args, **kwargs)
        await session.commit()
        return result


async def seed_profile(candidate_id: uuid.UUID | None = None) -> tuple[uuid.UUID, uuid.UUID]:
    async with session_factory() as session:
        if candidate_id is None:
            candidate = Candidate()
            session.add(candidate)
            await session.flush()
            candidate_id = candidate.id
        profile = Profile(
            candidate_id=candidate_id,
            name="Ada profile",
            structured_profile=golden_profile().model_dump(mode="json"),
        )
        session.add(profile)
        await session.flush()
        ids = (candidate_id, profile.id)
        await session.commit()
        return ids


async def seed_golden_achievements(candidate_id: uuid.UUID) -> None:
    rows: list[dict[str, Any]] = [
        {"title": "Outside", "employer_ref": BABBAGE, "time_start": date(2021, 3, 1)},
        {"title": "Ghost", "employer_ref": GHOST, "time_start": date(2019, 5, 1)},
        {
            "title": "Latency",
            "employer_ref": ENGINE,
            "time_start": date(2021, 5, 1),
            "metrics": [LATENCY],
            "skills": ["Python", "Kubernetes"],
        },
        {
            "title": "Platform",
            "employer_ref": ENGINE,
            "time_start": date(2021, 6, 1),
            "skills": ["SQL", "Terraform"],
        },
    ]
    async with session_factory() as session:
        for row in rows:
            session.add(
                Achievement(
                    candidate_id=candidate_id,
                    status=AchievementStatus.approved,
                    impact_type="performance",
                    difficulty=3,
                    **row,
                )
            )
        await session.commit()


async def new_document(profile_id: uuid.UUID, **kwargs: Any) -> uuid.UUID:
    created = await call(
        documents.create_document, ResumeDocumentCreate(profile_id=profile_id, **kwargs)
    )
    return created.id


async def revision_versions(document_id: uuid.UUID) -> list[int]:
    async with session_factory() as session:
        rows = await session.execute(
            select(ResumeDocumentRevision.version)
            .where(ResumeDocumentRevision.document_id == document_id)
            .order_by(ResumeDocumentRevision.version)
        )
        return list(rows.scalars())


async def test_create_copies_identity_from_the_profile_and_snapshots_version_one() -> None:
    _, profile_id = await seed_profile()

    created = await call(documents.create_document, ResumeDocumentCreate(profile_id=profile_id))

    assert created.title == "Ada profile resume"
    assert (created.page_target, created.version, created.status) == (1, 1, "draft")
    assert created.content.basics.full_name == "Ada Lovelace"
    assert [job.company for job in created.content.work][:2] == ["Engine Co", "Analytical Ltd"]
    assert created.content.work[0].highlights[0].origin == "profile_verbatim"
    assert await revision_versions(created.id) == [1]


@pytest.mark.parametrize("pages", [0, 5])
async def test_page_target_outside_one_to_four_is_rejected(pages: int) -> None:
    _, profile_id = await seed_profile()
    document_id = await new_document(profile_id)

    with pytest.raises(ValidationError):
        ResumeDocumentCreate(profile_id=profile_id, page_target=pages)
    with pytest.raises(ValidationError):
        ResumeDocumentUpdate(page_target=pages)
    assert (await call(documents.get_document, document_id)).page_target == 1


@pytest.mark.parametrize("pages", [1, 2, 3, 4])
async def test_page_target_one_to_four_is_accepted(pages: int) -> None:
    _, profile_id = await seed_profile()

    document_id = await new_document(profile_id, page_target=pages)

    assert (await call(documents.get_document, document_id)).page_target == pages


async def test_create_refuses_unknown_foreign_profiles_and_foreign_matches() -> None:
    _, profile_id = await seed_profile()
    await seed_profile()
    async with session_factory() as session:
        foreign = (
            await session.execute(select(Profile.id).where(Profile.id != profile_id))
        ).scalar_one()

    with pytest.raises(ProfileNotFoundError):
        await call(documents.create_document, ResumeDocumentCreate(profile_id=uuid.uuid4()))
    with pytest.raises(ProfileNotFoundError):
        await call(documents.create_document, ResumeDocumentCreate(profile_id=foreign))
    with pytest.raises(MatchNotFoundError):
        await call(
            documents.create_document,
            ResumeDocumentCreate(profile_id=profile_id, match_id=uuid.uuid4()),
        )


async def test_saving_content_bumps_the_version_and_a_no_op_does_not() -> None:
    _, profile_id = await seed_profile()
    document_id = await new_document(profile_id)
    document = await call(documents.get_document, document_id)
    edited = document.content.model_copy(deep=True)
    edited.work[0].highlights[0].text = "Rewrote this bullet"
    edited.work[0].highlights[0].origin = "user_edited"

    first = await call(documents.update_document, document_id, ResumeDocumentUpdate(content=edited))
    again = await call(documents.update_document, document_id, ResumeDocumentUpdate(content=edited))

    assert (first.version, again.version) == (2, 2)
    assert first.content.work[0].highlights[0].text == "Rewrote this bullet"
    assert await revision_versions(document_id) == [1, 2]


async def test_revision_history_is_capped_at_twenty_newest() -> None:
    _, profile_id = await seed_profile()
    document_id = await new_document(profile_id)
    content = (await call(documents.get_document, document_id)).content
    for index in range(25):
        content = content.model_copy(deep=True)
        content.basics.summary = f"summary {index}"
        await call(documents.update_document, document_id, ResumeDocumentUpdate(content=content))

    versions = await revision_versions(document_id)

    assert versions == list(range(7, 27))
    assert (await call(documents.get_document, document_id)).version == 26


async def test_metadata_updates_do_not_create_revisions() -> None:
    _, profile_id = await seed_profile()
    document_id = await new_document(profile_id)

    updated = await call(
        documents.update_document,
        document_id,
        ResumeDocumentUpdate(title="Backend roles", page_target=2, status="final"),
    )

    assert (updated.title, updated.page_target, updated.status) == ("Backend roles", 2, "final")
    assert updated.version == 1
    assert await revision_versions(document_id) == [1]


async def test_list_filters_by_profile_and_paginates() -> None:
    candidate_id, first_profile = await seed_profile()
    _, second_profile = await seed_profile(candidate_id)
    await new_document(first_profile)
    await new_document(second_profile)
    await new_document(second_profile)

    assert await call(documents.count_documents) == 3
    assert await call(documents.count_documents, second_profile) == 2
    page = await call(documents.list_documents, second_profile, Pagination(limit=1, offset=1))
    assert len(page) == 1
    assert page[0].profile_id == second_profile


async def test_deleting_a_profile_cascades_to_its_documents_and_revisions() -> None:
    _, profile_id = await seed_profile()
    document_id = await new_document(profile_id)

    async with session_factory() as session:
        await session.delete(await session.get_one(Profile, profile_id))
        await session.commit()

    async with session_factory() as session:
        assert await session.get(ResumeDocument, document_id) is None
    assert await revision_versions(document_id) == []


async def test_deleting_a_document_removes_it_and_its_revisions() -> None:
    _, profile_id = await seed_profile()
    document_id = await new_document(profile_id)

    await call(documents.delete_document, document_id)

    with pytest.raises(ResumeDocumentNotFoundError):
        await call(documents.get_document, document_id)
    assert await revision_versions(document_id) == []


async def test_documents_of_another_candidate_are_not_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mine_candidate, mine = await seed_profile()
    theirs_candidate, theirs = await seed_profile()
    async with session_factory() as session:
        stranger = ResumeDocument(candidate_id=theirs_candidate, profile_id=theirs, title="x")
        session.add(stranger)
        await session.flush()
        stranger_id = stranger.id
        await session.commit()
    await new_document(mine)

    async def single_user(_session: Any) -> uuid.UUID:
        return mine_candidate

    monkeypatch.setattr(documents, "candidate_id_or_none", single_user)

    for fn, args in (
        (documents.get_document, (stranger_id,)),
        (documents.delete_document, (stranger_id,)),
        (documents.get_conflicts, (stranger_id,)),
        (documents.update_document, (stranger_id, ResumeDocumentUpdate(title="y"))),
    ):
        with pytest.raises(ResumeDocumentNotFoundError):
            await call(fn, *args)
    with pytest.raises(ProfileNotFoundError):
        await call(documents.create_document, ResumeDocumentCreate(profile_id=theirs))


async def test_conflicts_split_open_from_kept_as_is_without_touching_the_profile(
    github: Any,
) -> None:
    candidate_id, profile_id = await seed_profile()
    await seed_golden_achievements(candidate_id)
    document_id = await new_document(profile_id)
    async with session_factory() as session:
        before = (await session.get_one(Profile, profile_id)).structured_profile
        before_updated = (await session.get_one(Profile, profile_id)).updated_at

    report = await call(documents.get_conflicts, document_id)
    mismatch = next(c for c in report.open if c.kind == "identity_mismatch")
    resolved = await call(
        documents.resolve_conflict,
        document_id,
        mismatch.key,
        ResolveConflictRequest(action="keep_as_is"),
    )
    rerun = await call(documents.get_conflicts, document_id)

    assert report.github_checked is True
    assert len(report.open) == 7
    assert [c.key for c in resolved.resolved] == [mismatch.key]
    assert mismatch.key not in {c.key for c in resolved.open}
    assert {c.key for c in rerun.resolved} == {mismatch.key}
    assert len(rerun.open) == 6
    async with session_factory() as session:
        profile = await session.get_one(Profile, profile_id)
        assert profile.structured_profile == before
        assert profile.updated_at == before_updated


async def test_reopening_restores_a_conflict_and_unknown_keys_are_not_found(github: Any) -> None:
    candidate_id, profile_id = await seed_profile()
    await seed_golden_achievements(candidate_id)
    document_id = await new_document(profile_id)
    key = (await call(documents.get_conflicts, document_id)).open[0].key
    await call(
        documents.resolve_conflict, document_id, key, ResolveConflictRequest(action="keep_as_is")
    )

    reopened = await call(
        documents.resolve_conflict, document_id, key, ResolveConflictRequest(action="reopen")
    )

    assert reopened.resolved == []
    assert key in {c.key for c in reopened.open}
    for action in ("keep_as_is", "reopen"):
        with pytest.raises(ConflictNotFoundError):
            await call(
                documents.resolve_conflict,
                document_id,
                "does-not-exist",
                ResolveConflictRequest(action=action),
            )


@pytest.mark.parametrize(
    ("identity", "note"),
    [
        (None, documents.NO_GITHUB_NOTE),
        (EvidenceSourceError("boom"), documents.GITHUB_FAILED_NOTE),
    ],
)
async def test_identity_check_degrades_with_a_note(
    github: Any, identity: SourceIdentity | Exception | None, note: str
) -> None:
    candidate_id, profile_id = await seed_profile()
    await seed_golden_achievements(candidate_id)
    document_id = await new_document(profile_id)
    github(identity)

    report = await call(documents.get_conflicts, document_id)

    assert (report.github_checked, report.note) == (False, note)
    assert "identity_mismatch" not in {c.kind for c in report.open}
    assert len(report.open) == 6


async def test_resync_identity_refreshes_basics_education_and_employer_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, profile_id = await seed_profile()
    document_id = await new_document(profile_id)
    document = await call(documents.get_document, document_id)
    edited = document.content.model_copy(deep=True)
    edited.basics.summary = "Tailored summary"
    edited.work[0].highlights[0].text = "My own wording"
    await call(documents.update_document, document_id, ResumeDocumentUpdate(content=edited))
    async with session_factory() as session:
        profile = await session.get_one(Profile, profile_id)
        data = dict(profile.structured_profile)
        data["contact"] = {**data["contact"], "full_name": "Ada King", "phone": "+44 1"}
        data["experience"] = [
            {**data["experience"][0], "title": "Principal Engineer"},
            *data["experience"][1:],
        ]
        profile.structured_profile = data
        await session.commit()

    synced = await call(documents.resync_identity, document_id)

    assert synced.content.basics.full_name == "Ada King"
    assert synced.content.basics.phone == "+44 1"
    assert synced.content.basics.summary == "Tailored summary"
    assert synced.content.work[0].title == "Principal Engineer"
    assert synced.content.work[0].highlights[0].text == "My own wording"
    assert synced.version == 3


async def test_the_overlap_threshold_comes_from_settings(
    github: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, profile_id = await seed_profile()
    document_id = await new_document(profile_id)
    monkeypatch.setattr(get_settings(), "resume_overlap_min_days", 366)

    report = await call(documents.get_conflicts, document_id)

    assert "overlapping_roles" not in {c.kind for c in report.open}
