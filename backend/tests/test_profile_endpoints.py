import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from fakes import VALID_PROFILE
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.db import session_factory
from app.main import app
from app.models import Candidate, ProfileRevision, Resume, RevisionSource

pytestmark = pytest.mark.usefixtures("clean_tables")


@pytest.fixture
async def client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        yield async_client


async def insert_resume_with_draft(draft: dict[str, Any] | None) -> dict[str, str]:
    async with session_factory() as session:
        result = await session.execute(select(Candidate).limit(1))
        candidate = result.scalars().first()
        if candidate is None:
            candidate = Candidate()
            session.add(candidate)
            await session.flush()
        resume = Resume(
            candidate_id=candidate.id,
            file_path="unused.pdf",
            original_filename="resume.pdf",
            content_type="application/pdf",
            size_bytes=1,
            extracted_text="resume text",
            draft_profile=draft,
            parse_version="gemini/gemini-2.5-flash+profile_prompt_v3" if draft else "text_v1",
            parsed_at=datetime.now(UTC) if draft else None,
        )
        session.add(resume)
        await session.flush()
        await session.commit()
        return {"candidate_id": str(candidate.id), "resume_id": str(resume.id)}


async def fetch_revisions() -> list[ProfileRevision]:
    async with session_factory() as session:
        result = await session.execute(select(ProfileRevision).order_by(ProfileRevision.created_at))
        return list(result.scalars().all())


def with_headline(profile: dict[str, Any], headline: str) -> dict[str, Any]:
    return {**profile, "headline": headline}


async def patch_profile(
    client: AsyncClient,
    structured_profile: dict[str, Any],
    source_resume_id: str | None = None,
) -> Any:
    body: dict[str, Any] = {"structured_profile": structured_profile}
    if source_resume_id is not None:
        body["source_resume_id"] = source_resume_id
    return await client.patch("/api/profile", json=body)


async def test_get_profile_returns_404_before_first_save(client: AsyncClient) -> None:
    assert (await client.get("/api/profile")).status_code == 404

    await insert_resume_with_draft(None)
    assert (await client.get("/api/profile")).status_code == 404


async def test_first_patch_from_unchanged_draft_writes_single_ai_extraction_revision(
    client: AsyncClient,
) -> None:
    inserted = await insert_resume_with_draft(VALID_PROFILE)

    response = await patch_profile(client, VALID_PROFILE, inserted["resume_id"])

    assert response.status_code == 200
    body = response.json()
    assert body["candidate_id"] == inserted["candidate_id"]
    assert body["structured_profile"]["contact"]["full_name"] == "Jane Doe"
    assert body["last_revision"]["source"] == "ai_extraction"

    revisions = await fetch_revisions()
    assert len(revisions) == 1
    assert revisions[0].source == RevisionSource.ai_extraction
    assert revisions[0].diff["contact.full_name"] == {"old": None, "new": "Jane Doe"}
    assert revisions[0].diff["headline"] == {"old": None, "new": "Senior Data Analyst"}
    assert revisions[0].diff["skills"] == {"old": None, "new": ["SQL", "Python", "Tableau"]}


async def test_first_patch_with_corrections_writes_two_revisions(client: AsyncClient) -> None:
    inserted = await insert_resume_with_draft(VALID_PROFILE)

    response = await patch_profile(
        client, with_headline(VALID_PROFILE, "Principal Data Analyst"), inserted["resume_id"]
    )

    assert response.status_code == 200
    assert response.json()["last_revision"]["source"] == "manual_edit"

    revisions = await fetch_revisions()
    assert [revision.source for revision in revisions] == [
        RevisionSource.ai_extraction,
        RevisionSource.manual_edit,
    ]
    assert revisions[1].diff == {
        "headline": {"old": "Senior Data Analyst", "new": "Principal Data Analyst"}
    }
    assert revisions[1].created_at > revisions[0].created_at


async def test_subsequent_patch_writes_manual_edit_diff(client: AsyncClient) -> None:
    inserted = await insert_resume_with_draft(VALID_PROFILE)
    assert (await patch_profile(client, VALID_PROFILE, inserted["resume_id"])).status_code == 200

    response = await patch_profile(client, with_headline(VALID_PROFILE, "Analytics Lead"))

    assert response.status_code == 200
    body = response.json()
    assert body["structured_profile"]["headline"] == "Analytics Lead"
    assert body["last_revision"]["source"] == "manual_edit"

    revisions = await fetch_revisions()
    assert len(revisions) == 2
    assert revisions[1].diff == {
        "headline": {"old": "Senior Data Analyst", "new": "Analytics Lead"}
    }

    fetched = await client.get("/api/profile")
    assert fetched.status_code == 200
    fetched_body = fetched.json()
    assert fetched_body["structured_profile"]["headline"] == "Analytics Lead"
    assert fetched_body["last_revision"]["source"] == "manual_edit"


async def test_no_change_patch_writes_empty_diff_revision(client: AsyncClient) -> None:
    inserted = await insert_resume_with_draft(VALID_PROFILE)
    assert (await patch_profile(client, VALID_PROFILE, inserted["resume_id"])).status_code == 200

    response = await patch_profile(client, VALID_PROFILE)

    assert response.status_code == 200
    revisions = await fetch_revisions()
    assert len(revisions) == 2
    assert revisions[1].source == RevisionSource.manual_edit
    assert revisions[1].diff == {}


async def test_reupload_merge_writes_reupload_merge_revision(client: AsyncClient) -> None:
    inserted = await insert_resume_with_draft(VALID_PROFILE)
    assert (await patch_profile(client, VALID_PROFILE, inserted["resume_id"])).status_code == 200
    reuploaded = await insert_resume_with_draft(with_headline(VALID_PROFILE, "Staff Data Analyst"))

    response = await patch_profile(
        client,
        with_headline(VALID_PROFILE, "Staff Data Analyst"),
        reuploaded["resume_id"],
    )

    assert response.status_code == 200
    revisions = await fetch_revisions()
    assert len(revisions) == 2
    assert revisions[1].source == RevisionSource.reupload_merge
    assert revisions[1].diff == {
        "headline": {"old": "Senior Data Analyst", "new": "Staff Data Analyst"}
    }


async def test_patch_with_unknown_resume_returns_404(client: AsyncClient) -> None:
    response = await patch_profile(client, VALID_PROFILE, str(uuid.uuid4()))

    assert response.status_code == 404


async def test_draft_endpoint_returns_persisted_draft(client: AsyncClient) -> None:
    inserted = await insert_resume_with_draft(VALID_PROFILE)

    response = await client.get(f"/api/resume/{inserted['resume_id']}/draft")

    assert response.status_code == 200
    body = response.json()
    assert body["resume_id"] == inserted["resume_id"]
    assert body["candidate_id"] == inserted["candidate_id"]
    assert body["draft_profile"]["contact"]["full_name"] == "Jane Doe"
    assert body["parse_version"] == "gemini/gemini-2.5-flash+profile_prompt_v3"
    assert body["parsed_at"] is not None


async def test_draft_endpoint_returns_404_for_unknown_resume(client: AsyncClient) -> None:
    response = await client.get(f"/api/resume/{uuid.uuid4()}/draft")

    assert response.status_code == 404


async def test_draft_endpoint_returns_409_without_draft(client: AsyncClient) -> None:
    inserted = await insert_resume_with_draft(None)

    response = await client.get(f"/api/resume/{inserted['resume_id']}/draft")

    assert response.status_code == 409


async def test_malformed_patch_returns_422(client: AsyncClient) -> None:
    assert (await client.patch("/api/profile", json={})).status_code == 422
    assert (await client.patch("/api/profile", json={"structured_profile": {}})).status_code == 422

    empty_content = {
        **VALID_PROFILE,
        "skills": [],
        "experience": [],
        "projects": [],
        "awards": [],
        "extra_sections": [],
    }
    response = await patch_profile(client, empty_content)
    assert response.status_code == 422
