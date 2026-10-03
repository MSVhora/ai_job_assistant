import copy
import uuid

import pytest
from fakes import VALID_PROFILE, seed_profile_light
from sqlalchemy import select

from app.core.db import session_factory
from app.core.errors import InvalidEvidenceInputError, ProfileNotFoundError
from app.models import EvidenceItem, EvidenceItemStatus, EvidenceKind, Profile
from app.services.evidence_pipeline.resume_ingest import ingest_profile

pytestmark = pytest.mark.usefixtures("clean_tables")


async def ingest(profile_id: uuid.UUID):
    async with session_factory() as session:
        result = await ingest_profile(session, profile_id)
        await session.commit()
        return result


async def lines() -> dict[str, EvidenceItem]:
    async with session_factory() as session:
        rows = (
            await session.execute(
                select(EvidenceItem).where(EvidenceItem.kind == EvidenceKind.resume_line)
            )
        ).scalars()
        return {row.body: row for row in rows}


async def edit_profile(profile_id: uuid.UUID, mutate) -> None:
    async with session_factory() as session:
        profile = await session.get_one(Profile, profile_id)
        data = copy.deepcopy(profile.structured_profile)
        mutate(data)
        profile.structured_profile = data
        await session.commit()


async def test_bullets_become_items_with_resume_project_keys() -> None:
    profile_id = await seed_profile_light()

    result = await ingest(profile_id)

    assert (result.created, result.unchanged, result.excluded) == (3, 0, 0)
    stored = await lines()
    assert set(stored) == {"Led reporting", "Built dashboards", "Built ETL toolkit"}
    assert stored["Led reporting"].project_key == "resume:Acme Corp"
    assert stored["Led reporting"].title == "Senior Data Analyst at Acme Corp"
    assert stored["Built ETL toolkit"].project_key == "resume:OpenPipeline"
    assert stored["Led reporting"].meta["section"] == "experience"
    assert stored["Built ETL toolkit"].meta["section"] == "projects"
    assert all(item.occurred_at is None for item in stored.values())


async def test_reingesting_an_unchanged_profile_is_a_no_op() -> None:
    profile_id = await seed_profile_light()
    await ingest(profile_id)

    result = await ingest(profile_id)

    assert (result.created, result.unchanged, result.excluded) == (0, 3, 0)
    assert len(await lines()) == 3


async def test_the_same_bullet_in_two_profiles_creates_one_item() -> None:
    first = await seed_profile_light("First")
    second = await seed_profile_light("Second")

    await ingest(first)
    result = await ingest(second)

    assert (result.created, result.unchanged) == (0, 3)
    stored = await lines()
    assert len(stored) == 3
    assert set(stored["Led reporting"].meta["profile_ids"]) == {str(first), str(second)}


async def test_editing_a_profile_adds_new_bullets_and_excludes_removed_ones() -> None:
    profile_id = await seed_profile_light()
    await ingest(profile_id)

    def mutate(data: dict) -> None:
        data["experience"][0]["bullets"] = ["Led reporting", "Cut report time by half"]

    await edit_profile(profile_id, mutate)
    result = await ingest(profile_id)

    assert (result.created, result.excluded) == (1, 1)
    stored = await lines()
    assert stored["Cut report time by half"].status is EvidenceItemStatus.kept
    assert stored["Built dashboards"].status is EvidenceItemStatus.excluded
    assert stored["Led reporting"].status is EvidenceItemStatus.kept


async def test_a_bullet_shared_with_another_profile_survives_removal_from_one() -> None:
    first = await seed_profile_light("First")
    second = await seed_profile_light("Second")
    await ingest(first)
    await ingest(second)

    def mutate(data: dict) -> None:
        data["experience"][0]["bullets"] = ["Led reporting"]

    await edit_profile(first, mutate)
    result = await ingest(first)

    assert result.excluded == 0
    assert (await lines())["Built dashboards"].status is EvidenceItemStatus.kept


async def test_a_removed_bullet_that_returns_is_revived() -> None:
    profile_id = await seed_profile_light()
    await ingest(profile_id)
    await edit_profile(profile_id, lambda d: d["experience"][0].update(bullets=["Led reporting"]))
    await ingest(profile_id)

    await edit_profile(
        profile_id,
        lambda d: d["experience"][0].update(bullets=["Led reporting", "Built dashboards"]),
    )
    result = await ingest(profile_id)

    assert result.created == 1
    assert (await lines())["Built dashboards"].status is EvidenceItemStatus.kept


async def test_unknown_profile_is_not_found() -> None:
    await seed_profile_light()

    async with session_factory() as session:
        with pytest.raises(ProfileNotFoundError):
            await ingest_profile(session, uuid.uuid4())


async def test_a_profile_with_invalid_content_is_rejected() -> None:
    profile_id = await seed_profile_light()
    await edit_profile(profile_id, lambda d: d.pop("contact"))

    async with session_factory() as session:
        with pytest.raises(InvalidEvidenceInputError):
            await ingest_profile(session, profile_id)


def test_the_seed_profile_has_the_bullets_these_tests_expect() -> None:
    assert VALID_PROFILE["experience"][0]["bullets"] == ["Led reporting", "Built dashboards"]
