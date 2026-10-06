import json
import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from fakes import VALID_PROFILE, install_acompletion, llm_response
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.db import session_factory
from app.main import app
from app.models import Candidate, Profile, Resume

pytestmark = pytest.mark.usefixtures("clean_tables")

JD = (
    "We are looking for a Senior Data Analyst with strong SQL and Python skills. "
    "You will build Tableau dashboards, own stakeholder reporting, and partner with "
    "data engineers. Experience with dbt and cloud warehouses (Snowflake) is a plus."
)

SCORED_REPORT: dict[str, Any] = {
    "source_resume_id": None,
    "source_profile_id": None,
    "overall_score": 72.0,
    "verdict": "Good match",
    "summary": "You are a reasonably strong fit for this role.",
    "categories": [
        {
            "name": "Keyword match",
            "score": 70,
            "weight": 0.4,
            "analysis": "Most core keywords present.",
            "issues": ["Snowflake is not mentioned anywhere"],
        },
        {
            "name": "Role alignment",
            "score": 80,
            "weight": 0.6,
            "analysis": "Your title matches the role.",
            "issues": [],
        },
    ],
    "matched_keywords": [
        {"keyword": "SQL", "priority": "critical"},
        {"keyword": "Python", "priority": "critical"},
    ],
    "missing_keywords": [{"keyword": "Snowflake", "priority": "important"}],
    "strengths": ["Senior data analyst title matches exactly"],
    "gaps": ["No warehouse tooling evidence"],
    "suggestions": [
        {
            "title": "Add Snowflake context",
            "area": "keywords",
            "detail": "Name the warehouse you used in the Acme bullet if true.",
            "rewrite_example": "Built dashboards on Snowflake via dbt models",
            "priority": "high",
        }
    ],
    "prompt_version": "ats_prompt_v1",
    "generated_at": datetime.now(UTC).isoformat(),
}


@pytest.fixture(autouse=True)
def gemini_key(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import get_settings

    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def ats_llm_handler(report: dict[str, Any]):
    def handler(**kwargs: Any):
        return llm_response(json.dumps(report))

    return handler


async def insert_profile(name: str = "Data") -> dict[str, str]:
    async with session_factory() as session:
        result = await session.execute(select(Candidate).limit(1))
        candidate = result.scalars().first()
        if candidate is None:
            candidate = Candidate()
            session.add(candidate)
            await session.flush()
        profile = Profile(
            candidate_id=candidate.id,
            name=name,
            structured_profile=VALID_PROFILE,
        )
        session.add(profile)
        await session.flush()
        await session.commit()
        return {"profile_id": str(profile.id), "candidate_id": str(candidate.id)}


async def insert_resume() -> str:
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
            extracted_text="Senior Data Analyst with SQL, Python, Tableau.",
            parse_version="text_v1",
        )
        session.add(resume)
        await session.flush()
        await session.commit()
        return str(resume.id)


@pytest.fixture
async def client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        yield async_client


async def test_score_with_profile(monkeypatch: pytest.MonkeyPatch, client: AsyncClient) -> None:
    inserted = await insert_profile()
    calls = install_acompletion(monkeypatch, ats_llm_handler(SCORED_REPORT))

    response = await client.post(
        "/api/ats/score",
        json={"profile_id": inserted["profile_id"], "job_description": JD},
    )

    assert response.status_code == 200
    report = response.json()
    assert report["source_profile_id"] == inserted["profile_id"]
    assert report["source_resume_id"] is None
    assert 0 <= report["overall_score"] <= 100
    assert report["suggestions"][0]["title"] == "Add Snowflake context"
    user_prompt = calls[0]["messages"][1]["content"]
    assert "Tableau" in user_prompt
    assert "JOB DESCRIPTION" in user_prompt


async def test_score_normalizes_paraphrased_enums(
    monkeypatch: pytest.MonkeyPatch, client: AsyncClient
) -> None:
    profile = await insert_profile()
    paraphrased = {
        **SCORED_REPORT,
        "verdict": (
            "Very strong match for this senior data analyst role given your SQL, "
            "Python and Tableau background plus dashboard experience"
        ),
        "summary": "You align well. " * 200,
        "matched_keywords": [{"keyword": "SQL", "priority": "Must have"}],
        "suggestions": [
            {
                "title": "Tighten the summary",
                "area": "Work Experience",
                "detail": "Do it",
                "priority": "Must fix now",
            }
        ],
    }
    install_acompletion(monkeypatch, ats_llm_handler(paraphrased))

    response = await client.post(
        "/api/ats/score",
        json={"profile_id": profile["profile_id"], "job_description": JD},
    )

    assert response.status_code == 200
    report = response.json()
    assert len(report["verdict"]) <= 200 and report["verdict"].strip()
    assert len(report["summary"]) <= 1600
    assert report["matched_keywords"][0]["priority"] == "critical"
    assert report["suggestions"][0]["area"] == "other"
    assert report["suggestions"][0]["priority"] == "medium"


async def test_score_with_resume(monkeypatch: pytest.MonkeyPatch, client: AsyncClient) -> None:
    resume_id = await insert_resume()
    install_acompletion(monkeypatch, ats_llm_handler(SCORED_REPORT))

    response = await client.post(
        "/api/ats/score",
        json={"resume_id": resume_id, "job_description": JD},
    )

    assert response.status_code == 200
    report = response.json()
    assert report["source_resume_id"] == resume_id
    assert report["source_profile_id"] is None


async def test_score_rejects_both_sources(client: AsyncClient) -> None:
    profile = await insert_profile()
    response = await client.post(
        "/api/ats/score",
        json={
            "resume_id": profile["candidate_id"],
            "profile_id": profile["profile_id"],
            "job_description": JD,
        },
    )
    assert response.status_code == 422


async def test_score_rejects_no_source(client: AsyncClient) -> None:
    response = await client.post(
        "/api/ats/score",
        json={"job_description": JD},
    )
    assert response.status_code == 422


async def test_score_rejects_short_jd(client: AsyncClient) -> None:
    profile = await insert_profile()
    response = await client.post(
        "/api/ats/score",
        json={"profile_id": profile["profile_id"], "job_description": "too short"},
    )
    assert response.status_code == 422


async def test_score_unknown_profile_404(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    install_acompletion(monkeypatch, ats_llm_handler(SCORED_REPORT))
    response = await client.post(
        "/api/ats/score",
        json={"profile_id": str(uuid.uuid4()), "job_description": JD},
    )
    assert response.status_code == 404


async def test_score_unknown_resume_404(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    install_acompletion(monkeypatch, ats_llm_handler(SCORED_REPORT))
    response = await client.post(
        "/api/ats/score",
        json={"resume_id": str(uuid.uuid4()), "job_description": JD},
    )
    assert response.status_code == 404
