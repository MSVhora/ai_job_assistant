import io
from datetime import UTC, datetime

import pytest
from docx import Document
from fakes import VALID_PROFILE
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.db import session_factory
from app.main import app
from app.models import Candidate, Resume

pytestmark = pytest.mark.usefixtures("clean_tables")

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


@pytest.fixture
async def client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        yield async_client


def docx_bytes(content: str) -> bytes:
    buffer = io.BytesIO()
    document = Document()
    document.add_paragraph(content)
    document.save(buffer)
    return buffer.getvalue()


async def upload_docx(client: AsyncClient, filename: str) -> dict:
    response = await client.post(
        "/api/resumes",
        files={"file": (filename, io.BytesIO(docx_bytes(filename)), DOCX_MIME)},
    )
    assert response.status_code == 201
    return response.json()


async def test_list_resumes_empty_without_candidate(client: AsyncClient) -> None:
    response = await client.get("/api/resumes")

    assert response.status_code == 200
    assert response.json() == []


async def test_list_resumes_orders_newest_first(client: AsyncClient) -> None:
    await upload_docx(client, "first.docx")
    await upload_docx(client, "second.docx")

    response = await client.get("/api/resumes")

    assert response.status_code == 200
    summaries = response.json()
    assert len(summaries) == 2
    assert summaries[0]["original_filename"] == "second.docx"
    assert summaries[1]["original_filename"] == "first.docx"
    assert all(summary["has_draft"] is False for summary in summaries)
    assert all(summary["source_profile_names"] == [] for summary in summaries)


async def test_source_profile_names_follow_created_profiles(client: AsyncClient) -> None:
    first = await upload_docx(client, "first.docx")
    second = await upload_docx(client, "second.docx")

    for name in ("Android", "SWE"):
        saved = await client.post(
            "/api/profiles",
            json={
                "name": name,
                "structured_profile": VALID_PROFILE,
                "source_resume_id": second["resume_id"],
            },
        )
        assert saved.status_code == 201

    flagged = (await client.get("/api/resumes")).json()
    by_id = {summary["resume_id"]: summary for summary in flagged}
    assert by_id[second["resume_id"]]["source_profile_names"] == ["Android", "SWE"]
    assert by_id[first["resume_id"]]["source_profile_names"] == []


async def test_list_resumes_flags_draft_availability(client: AsyncClient) -> None:
    async with session_factory() as session:
        result = await session.execute(select(Candidate).limit(1))
        candidate = result.scalars().first()
        if candidate is None:
            candidate = Candidate()
            session.add(candidate)
            await session.flush()
        with_draft = Resume(
            candidate_id=candidate.id,
            file_path="with-draft.pdf",
            original_filename="with-draft.pdf",
            content_type="application/pdf",
            size_bytes=1,
            extracted_text="text",
            draft_profile=VALID_PROFILE,
            parse_version="test+prompt",
            parsed_at=datetime.now(UTC),
        )
        without_draft = Resume(
            candidate_id=candidate.id,
            file_path="without-draft.pdf",
            original_filename="without-draft.pdf",
            content_type="application/pdf",
            size_bytes=1,
            extracted_text="text",
        )
        session.add_all([with_draft, without_draft])
        await session.commit()

    response = await client.get("/api/resumes")

    assert response.status_code == 200
    summaries = response.json()
    by_name = {summary["original_filename"]: summary for summary in summaries}
    assert by_name["with-draft.pdf"]["has_draft"] is True
    assert by_name["without-draft.pdf"]["has_draft"] is False
