import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from fakes import VALID_PROFILE
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.db import session_factory
from app.main import app
from app.models import Candidate, Profile, ProfileRevision, Resume, RevisionSource

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
            parse_version="gemini/gemini-2.5-flash+profile_prompt_v5" if draft else "text_v1",
            parsed_at=datetime.now(UTC) if draft else None,
        )
        session.add(resume)
        await session.flush()
        await session.commit()
        return {"candidate_id": str(candidate.id), "resume_id": str(resume.id)}


async def create_profile(
    client: AsyncClient,
    name: str,
    structured_profile: dict[str, Any],
    source_resume_id: str | None = None,
) -> Any:
    body: dict[str, Any] = {"name": name, "structured_profile": structured_profile}
    if source_resume_id is not None:
        body["source_resume_id"] = source_resume_id
    return await client.post("/api/profiles", json=body)


async def fetch_revisions(profile_id: str) -> list[ProfileRevision]:
    async with session_factory() as session:
        result = await session.execute(
            select(ProfileRevision)
            .where(ProfileRevision.profile_id == uuid.UUID(profile_id))
            .order_by(ProfileRevision.created_at)
        )
        return list(result.scalars().all())


def with_headline(profile: dict[str, Any], headline: str) -> dict[str, Any]:
    return {**profile, "headline": headline}


async def test_create_profile_from_unchanged_draft_writes_single_ai_extraction_revision(
    client: AsyncClient,
) -> None:
    inserted = await insert_resume_with_draft(VALID_PROFILE)

    response = await create_profile(client, "Android", VALID_PROFILE, inserted["resume_id"])

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Android"
    assert body["structured_profile"]["contact"]["full_name"] == "Jane Doe"
    assert body["source_resume_id"] == inserted["resume_id"]
    assert body["source_resume_filename"] == "resume.pdf"
    assert body["last_revision"]["source"] == "ai_extraction"

    revisions = await fetch_revisions(body["profile_id"])
    assert len(revisions) == 1
    assert revisions[0].source == RevisionSource.ai_extraction
    assert revisions[0].diff["contact.full_name"] == {"old": None, "new": "Jane Doe"}


async def test_create_profile_with_corrections_writes_two_revisions(client: AsyncClient) -> None:
    inserted = await insert_resume_with_draft(VALID_PROFILE)

    response = await create_profile(
        client,
        "SWE",
        with_headline(VALID_PROFILE, "Principal Data Analyst"),
        inserted["resume_id"],
    )

    assert response.status_code == 201
    assert response.json()["last_revision"]["source"] == "manual_edit"

    revisions = await fetch_revisions(response.json()["profile_id"])
    assert [revision.source for revision in revisions] == [
        RevisionSource.ai_extraction,
        RevisionSource.manual_edit,
    ]
    assert revisions[1].diff == {
        "headline": {"old": "Senior Data Analyst", "new": "Principal Data Analyst"}
    }
    assert revisions[1].created_at > revisions[0].created_at


async def test_create_profile_without_resume_ref_writes_manual_edit_baseline(
    client: AsyncClient,
) -> None:
    response = await create_profile(client, "Manual", VALID_PROFILE)

    assert response.status_code == 201
    assert response.json()["source_resume_id"] is None
    assert response.json()["source_resume_filename"] is None

    revisions = await fetch_revisions(response.json()["profile_id"])
    assert len(revisions) == 1
    assert revisions[0].source == RevisionSource.manual_edit
    assert revisions[0].diff["skills"] == {"old": None, "new": ["SQL", "Python", "Tableau"]}


async def test_two_profiles_from_same_draft_have_independent_revisions(
    client: AsyncClient,
) -> None:
    inserted = await insert_resume_with_draft(VALID_PROFILE)
    android = await create_profile(client, "Android", VALID_PROFILE, inserted["resume_id"])
    swe = await create_profile(
        client,
        "SWE",
        with_headline(VALID_PROFILE, "Full-Stack Engineer"),
        inserted["resume_id"],
    )
    assert android.status_code == 201 and swe.status_code == 201
    android_id = android.json()["profile_id"]
    swe_id = swe.json()["profile_id"]

    patched = await client.patch(
        f"/api/profiles/{android_id}",
        json={"structured_profile": with_headline(VALID_PROFILE, "Android Lead")},
    )
    assert patched.status_code == 200

    android_revisions = await fetch_revisions(android_id)
    swe_revisions = await fetch_revisions(swe_id)
    assert len(android_revisions) == 2
    assert android_revisions[1].source == RevisionSource.manual_edit
    assert len(swe_revisions) == 2
    assert swe.json()["structured_profile"]["headline"] == "Full-Stack Engineer"

    fetched = await client.get(f"/api/profiles/{swe_id}")
    assert fetched.json()["structured_profile"]["headline"] == "Full-Stack Engineer"
    listed = await client.get("/api/profiles")
    assert [summary["name"] for summary in listed.json()] == ["Android", "SWE"]


async def test_content_patch_writes_manual_edit_diff(client: AsyncClient) -> None:
    created = await create_profile(client, "Android", VALID_PROFILE)
    profile_id = created.json()["profile_id"]

    response = await client.patch(
        f"/api/profiles/{profile_id}",
        json={"structured_profile": with_headline(VALID_PROFILE, "Android Lead")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["structured_profile"]["headline"] == "Android Lead"
    assert body["last_revision"]["source"] == "manual_edit"
    revisions = await fetch_revisions(profile_id)
    assert len(revisions) == 2
    assert revisions[1].diff == {"headline": {"old": "Senior Data Analyst", "new": "Android Lead"}}


async def test_merge_patch_updates_provenance_and_writes_reupload_merge(
    client: AsyncClient,
) -> None:
    created = await create_profile(client, "Android", VALID_PROFILE)
    profile_id = created.json()["profile_id"]
    reuploaded = await insert_resume_with_draft(with_headline(VALID_PROFILE, "Staff Data Analyst"))

    response = await client.patch(
        f"/api/profiles/{profile_id}",
        json={
            "structured_profile": with_headline(VALID_PROFILE, "Staff Data Analyst"),
            "source_resume_id": reuploaded["resume_id"],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["last_revision"]["source"] == "reupload_merge"
    assert body["source_resume_id"] == reuploaded["resume_id"]
    assert body["source_resume_filename"] == "resume.pdf"
    revisions = await fetch_revisions(profile_id)
    assert len(revisions) == 2
    assert revisions[1].source == RevisionSource.reupload_merge
    assert revisions[1].diff == {
        "headline": {"old": "Senior Data Analyst", "new": "Staff Data Analyst"}
    }


async def test_rename_patch_writes_no_revision(client: AsyncClient) -> None:
    created = await create_profile(client, "Android", VALID_PROFILE)
    profile_id = created.json()["profile_id"]

    response = await client.patch(f"/api/profiles/{profile_id}", json={"name": "Android Developer"})

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Android Developer"
    assert body["last_revision"] is None
    revisions = await fetch_revisions(profile_id)
    assert len(revisions) == 1


async def test_no_change_content_patch_writes_empty_diff_revision(client: AsyncClient) -> None:
    created = await create_profile(client, "Android", VALID_PROFILE)
    profile_id = created.json()["profile_id"]

    response = await client.patch(
        f"/api/profiles/{profile_id}", json={"structured_profile": VALID_PROFILE}
    )

    assert response.status_code == 200
    revisions = await fetch_revisions(profile_id)
    assert len(revisions) == 2
    assert revisions[1].source == RevisionSource.manual_edit
    assert revisions[1].diff == {}


async def test_delete_profile_cascades_revisions_and_keeps_other_profiles(
    client: AsyncClient,
) -> None:
    inserted = await insert_resume_with_draft(VALID_PROFILE)
    first = await create_profile(client, "Android", VALID_PROFILE, inserted["resume_id"])
    second = await create_profile(client, "SWE", VALID_PROFILE, inserted["resume_id"])
    first_id = first.json()["profile_id"]
    second_id = second.json()["profile_id"]

    response = await client.delete(f"/api/profiles/{first_id}")

    assert response.status_code == 204
    assert (await client.get(f"/api/profiles/{first_id}")).status_code == 404
    assert len(await fetch_revisions(first_id)) == 0

    kept = await client.get(f"/api/profiles/{second_id}")
    assert kept.status_code == 200
    assert kept.json()["name"] == "SWE"
    assert len(await fetch_revisions(second_id)) == 1


async def test_unknown_profile_returns_404(client: AsyncClient) -> None:
    assert (await client.get(f"/api/profiles/{uuid.uuid4()}")).status_code == 404
    assert (
        await client.patch(
            f"/api/profiles/{uuid.uuid4()}", json={"structured_profile": VALID_PROFILE}
        )
    ).status_code == 404
    assert (await client.delete(f"/api/profiles/{uuid.uuid4()}")).status_code == 404


async def test_create_with_unknown_resume_returns_404(client: AsyncClient) -> None:
    response = await create_profile(client, "Android", VALID_PROFILE, str(uuid.uuid4()))

    assert response.status_code == 404


async def test_draft_endpoint_returns_persisted_draft(client: AsyncClient) -> None:
    inserted = await insert_resume_with_draft(VALID_PROFILE)

    response = await client.get(f"/api/resumes/{inserted['resume_id']}/draft")

    assert response.status_code == 200
    body = response.json()
    assert body["resume_id"] == inserted["resume_id"]
    assert body["candidate_id"] == inserted["candidate_id"]
    assert body["draft_profile"]["contact"]["full_name"] == "Jane Doe"
    assert body["parse_version"] == "gemini/gemini-2.5-flash+profile_prompt_v5"
    assert body["parsed_at"] is not None


async def test_draft_endpoint_returns_404_for_unknown_resume(client: AsyncClient) -> None:
    response = await client.get(f"/api/resumes/{uuid.uuid4()}/draft")

    assert response.status_code == 404


async def test_draft_endpoint_returns_409_without_draft(client: AsyncClient) -> None:
    inserted = await insert_resume_with_draft(None)

    response = await client.get(f"/api/resumes/{inserted['resume_id']}/draft")

    assert response.status_code == 409


async def test_malformed_create_returns_422(client: AsyncClient) -> None:
    assert (await client.post("/api/profiles", json={})).status_code == 422
    assert (
        await client.post("/api/profiles", json={"name": "X", "structured_profile": {}})
    ).status_code == 422

    empty_content = {
        **VALID_PROFILE,
        "skills": [],
        "experience": [],
        "projects": [],
        "awards": [],
        "extra_sections": [],
    }
    response = await create_profile(client, "Empty", empty_content)
    assert response.status_code == 422


async def test_malformed_path_param_returns_readable_422(client: AsyncClient) -> None:
    response = await client.patch("/api/profiles/not-a-uuid", json={"name": "X"})

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert isinstance(detail, str)
    assert "profile_id" in detail


async def test_create_profile_copies_draft_search_queries(client: AsyncClient) -> None:

    from fakes import VALID_PROFILE

    inserted = await insert_resume_with_draft(VALID_PROFILE)
    stored = {
        "queries": {"adzuna": {"title": "Senior Data Analyst", "skills": ["SQL"]}},
        "generated_at": "2026-09-01T10:00:00Z",
        "generated_by": "gemini/gemini-2.5-flash",
        "prompt_version": "search_query_v1",
    }
    async with session_factory() as session:
        resume = await session.get(Resume, uuid.UUID(inserted["resume_id"]))
        assert resume is not None
        resume.search_queries = stored
        await session.commit()

    response = await create_profile(
        client, "Data", VALID_PROFILE, source_resume_id=inserted["resume_id"]
    )

    assert response.status_code == 201
    body = response.json()
    assert body["search_queries"]["queries"]["adzuna"]["title"] == "Senior Data Analyst"
    async with session_factory() as session:
        profile = await session.get(Profile, uuid.UUID(body["profile_id"]))
    assert profile is not None
    assert profile.search_queries == stored


async def test_profile_response_includes_search_queries(client: AsyncClient) -> None:
    from fakes import VALID_PROFILE

    inserted = await insert_resume_with_draft(VALID_PROFILE)
    created = (
        await create_profile(client, "Data", VALID_PROFILE, source_resume_id=inserted["resume_id"])
    ).json()

    fetched = await client.get(f"/api/profiles/{created['profile_id']}")
    assert fetched.status_code == 200
    assert fetched.json()["search_queries"] is None


async def test_regenerate_search_queries_persists(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    import json

    from fakes import VALID_PROFILE, install_acompletion, llm_response

    from app.core.config import get_settings

    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(get_settings(), "adzuna_app_id", "id")
    monkeypatch.setattr(get_settings(), "adzuna_app_key", "key")
    get_settings.cache_clear()

    inserted = await insert_resume_with_draft(VALID_PROFILE)
    created = (
        await create_profile(client, "Data", VALID_PROFILE, source_resume_id=inserted["resume_id"])
    ).json()
    queries_payload = {"queries": {"adzuna": {"title": "Senior Data Analyst", "skills": ["SQL"]}}}
    calls = install_acompletion(monkeypatch, lambda **kw: llm_response(json.dumps(queries_payload)))

    response = await client.post(f"/api/profiles/{created['profile_id']}/search-queries")

    assert response.status_code == 200
    body = response.json()
    assert body["queries"]["adzuna"]["title"] == "Senior Data Analyst"
    assert body["generated_by"] == "gemini/gemini-2.5-flash"
    assert "Sources needing a query spec: adzuna" in calls[0]["messages"][1]["content"]
    fetched = (await client.get(f"/api/profiles/{created['profile_id']}")).json()
    assert fetched["search_queries"]["queries"]["adzuna"]["title"] == "Senior Data Analyst"


async def test_regenerate_search_queries_unknown_profile_returns_404(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core.config import get_settings

    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    get_settings.cache_clear()

    response = await client.post(f"/api/profiles/{uuid.uuid4()}/search-queries")

    assert response.status_code == 404


async def test_regenerate_search_queries_rejects_unknown_source(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fakes import VALID_PROFILE

    from app.core.config import get_settings

    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(get_settings(), "adzuna_app_id", "id")
    monkeypatch.setattr(get_settings(), "adzuna_app_key", "key")
    get_settings.cache_clear()

    inserted = await insert_resume_with_draft(VALID_PROFILE)
    created = (
        await create_profile(client, "Data", VALID_PROFILE, source_resume_id=inserted["resume_id"])
    ).json()

    response = await client.post(
        f"/api/profiles/{created['profile_id']}/search-queries",
        json={"sources": ["apify_linkedin"]},
    )

    assert response.status_code == 400


async def test_regenerate_failure_keeps_persisted_queries(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fakes import VALID_PROFILE, ProviderError, install_acompletion

    from app.core.config import get_settings

    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(get_settings(), "adzuna_app_id", "id")
    monkeypatch.setattr(get_settings(), "adzuna_app_key", "key")

    async def no_delay(_: float) -> None:
        return None

    monkeypatch.setattr("app.adapters.llm.asyncio.sleep", no_delay)
    get_settings.cache_clear()

    inserted = await insert_resume_with_draft(VALID_PROFILE)
    created = (
        await create_profile(client, "Data", VALID_PROFILE, source_resume_id=inserted["resume_id"])
    ).json()
    stored = {
        "queries": {"adzuna": {"title": "Keep Me", "skills": ["SQL"]}},
        "generated_at": "2026-09-01T10:00:00Z",
        "generated_by": "gemini/gemini-2.5-flash",
        "prompt_version": "search_query_v1",
    }
    async with session_factory() as session:
        profile = await session.get(Profile, uuid.UUID(created["profile_id"]))
        assert profile is not None
        profile.search_queries = stored
        await session.commit()

    install_acompletion(monkeypatch, lambda **kw: ProviderError(429))
    response = await client.post(f"/api/profiles/{created['profile_id']}/search-queries")

    assert response.status_code == 502
    fetched = (await client.get(f"/api/profiles/{created['profile_id']}")).json()
    assert fetched["search_queries"]["queries"]["adzuna"]["title"] == "Keep Me"


async def test_created_profile_is_embedded(client: AsyncClient) -> None:
    inserted = await insert_resume_with_draft(VALID_PROFILE)
    created = (
        await create_profile(client, "Data", VALID_PROFILE, source_resume_id=inserted["resume_id"])
    ).json()

    async with session_factory() as session:
        profile = await session.get(Profile, uuid.UUID(created["profile_id"]))
        assert profile is not None
        assert profile.embedding is not None
        assert len(profile.embedding) == 768


async def test_content_patch_refreshes_embedding(client: AsyncClient) -> None:
    inserted = await insert_resume_with_draft(VALID_PROFILE)
    created = (
        await create_profile(client, "Data", VALID_PROFILE, source_resume_id=inserted["resume_id"])
    ).json()
    profile_id = uuid.UUID(created["profile_id"])
    async with session_factory() as session:
        profile = await session.get(Profile, profile_id)
        assert profile is not None
        first_embedding = profile.embedding
    assert first_embedding is not None

    response = await client.patch(
        f"/api/profiles/{profile_id}",
        json={"structured_profile": with_headline(VALID_PROFILE, "Principal Data Analyst")},
    )

    assert response.status_code == 200
    async with session_factory() as session:
        profile = await session.get(Profile, profile_id)
        assert profile is not None
        assert profile.embedding is not None
        assert profile.embedding != first_embedding


async def test_rename_only_patch_keeps_embedding(client: AsyncClient) -> None:
    inserted = await insert_resume_with_draft(VALID_PROFILE)
    created = (
        await create_profile(client, "Data", VALID_PROFILE, source_resume_id=inserted["resume_id"])
    ).json()
    profile_id = uuid.UUID(created["profile_id"])

    response = await client.patch(f"/api/profiles/{profile_id}", json={"name": "Renamed"})

    assert response.status_code == 200
    async with session_factory() as session:
        profile = await session.get(Profile, profile_id)
        assert profile is not None
        assert profile.embedding is not None


async def test_profile_save_survives_embedding_failure(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fakes import install_aembedding

    from app.adapters.llm import LLMError

    install_aembedding(monkeypatch, lambda **kw: LLMError("provider down"))
    inserted = await insert_resume_with_draft(VALID_PROFILE)

    response = await create_profile(
        client, "Data", VALID_PROFILE, source_resume_id=inserted["resume_id"]
    )

    assert response.status_code == 201
    async with session_factory() as session:
        profile = await session.get(Profile, uuid.UUID(response.json()["profile_id"]))
        assert profile is not None
        assert profile.embedding is None


async def test_patch_preferences_round_trip_writes_no_revision(client: AsyncClient) -> None:
    inserted = await insert_resume_with_draft(VALID_PROFILE)
    created = (
        await create_profile(client, "Data", VALID_PROFILE, source_resume_id=inserted["resume_id"])
    ).json()
    profile_id = created["profile_id"]
    assert created["preferences"] is None
    revisions_before = len(await fetch_revisions(profile_id))

    response = await client.patch(
        f"/api/profiles/{profile_id}/preferences", json={"priority": 0.25}
    )

    assert response.status_code == 200
    assert response.json() == {"priority": 0.25}
    fetched = (await client.get(f"/api/profiles/{profile_id}")).json()
    assert fetched["preferences"] == {"priority": 0.25}
    assert len(await fetch_revisions(profile_id)) == revisions_before


async def test_patch_preferences_unknown_profile_returns_404(client: AsyncClient) -> None:
    response = await client.patch(
        f"/api/profiles/{uuid.uuid4()}/preferences", json={"priority": 0.5}
    )

    assert response.status_code == 404


async def test_patch_preferences_out_of_range_returns_422(client: AsyncClient) -> None:
    inserted = await insert_resume_with_draft(VALID_PROFILE)
    created = (
        await create_profile(client, "Data", VALID_PROFILE, source_resume_id=inserted["resume_id"])
    ).json()

    too_high = await client.patch(
        f"/api/profiles/{created['profile_id']}/preferences", json={"priority": 1.5}
    )
    too_low = await client.patch(
        f"/api/profiles/{created['profile_id']}/preferences", json={"priority": -0.1}
    )

    assert too_high.status_code == 422
    assert too_low.status_code == 422


async def test_content_save_keeps_preferences(client: AsyncClient) -> None:
    inserted = await insert_resume_with_draft(VALID_PROFILE)
    created = (
        await create_profile(client, "Data", VALID_PROFILE, source_resume_id=inserted["resume_id"])
    ).json()
    profile_id = created["profile_id"]
    await client.patch(f"/api/profiles/{profile_id}/preferences", json={"priority": 0.25})

    saved = await client.patch(
        f"/api/profiles/{profile_id}",
        json={"structured_profile": with_headline(VALID_PROFILE, "Principal Data Analyst")},
    )

    assert saved.status_code == 200
    fetched = (await client.get(f"/api/profiles/{profile_id}")).json()
    assert fetched["preferences"] == {"priority": 0.25}
