import uuid

import pytest
from fakes import VALID_PROFILE, embedding_response, install_aembedding

from app.adapters.job_sources.base import JobPostingData
from app.adapters.llm import LLMError
from app.models import Profile
from app.schemas.profile import StructuredProfile
from app.services.embedding import (
    MAX_EMBED_CHARS,
    embed_postings,
    embed_texts,
    job_embed_text,
    profile_embed_text,
    refresh_profile_embedding,
)

FULL_PREFS = {
    "target_title": "Data Analyst",
    "target_location": "Berlin",
    "remote_preference": "hybrid",
    "seniority": "senior",
    "work_authorization": "EU citizen",
}


def posting(external_id: str, description: str | None) -> JobPostingData:
    return JobPostingData(
        external_id=external_id, title=f"Job {external_id}", description=description, raw_payload={}
    )


def test_job_embed_text_composes_title_and_description() -> None:
    text = job_embed_text("Data Analyst", "  Build dashboards.  ")
    assert text == "Data Analyst\nBuild dashboards."


def test_job_embed_text_truncates_long_descriptions() -> None:
    text = job_embed_text("Data Analyst", "x" * 10_000)
    assert text is not None
    assert len(text) == MAX_EMBED_CHARS


@pytest.mark.parametrize("description", [None, "", "   "])
def test_job_embed_text_returns_none_without_description(description: str | None) -> None:
    assert job_embed_text("Data Analyst", description) is None


def test_profile_embed_text_includes_matching_fields() -> None:
    text = profile_embed_text(
        StructuredProfile.model_validate({**VALID_PROFILE, "preferences": FULL_PREFS})
    )
    assert "Target role: Data Analyst" in text
    assert "Skills: SQL, Python, Tableau" in text
    assert "Seniority: senior" in text
    assert "Senior Data Analyst at Acme Corp" in text
    assert "Preferred location: Berlin" in text
    assert "Work authorization: EU citizen" in text


def test_profile_embed_text_caps_length() -> None:
    profile = StructuredProfile.model_validate({**VALID_PROFILE, "summary": "y" * 10_000})
    assert len(profile_embed_text(profile)) == MAX_EMBED_CHARS


async def test_embed_postings_batches_and_aligns(fake_embedding: list[dict[str, object]]) -> None:
    result = await embed_postings(
        [posting("1", "desc one"), posting("2", None), posting("3", "desc three")]
    )

    assert len(fake_embedding) == 1
    assert fake_embedding[0]["input"] == ["Job 1\ndesc one", "Job 3\ndesc three"]
    assert result[0] is not None and len(result[0]) == 768
    assert result[1] is None
    assert result[2] is not None and len(result[2]) == 768


async def test_embed_postings_without_descriptions_skips_provider(
    fake_embedding: list[dict[str, object]],
) -> None:
    result = await embed_postings([posting("1", None)])

    assert fake_embedding == []
    assert result == [None]


async def test_embed_texts_rejects_wrong_dimension(monkeypatch: pytest.MonkeyPatch) -> None:
    install_aembedding(
        monkeypatch,
        lambda **kw: embedding_response([[0.0, 0.1, 0.2] for _ in kw["input"]]),
    )

    with pytest.raises(LLMError, match="dimension mismatch"):
        await embed_texts(["some text"])


async def test_embed_texts_without_texts_skips_provider(
    fake_embedding: list[dict[str, object]],
) -> None:
    assert await embed_texts([]) == []
    assert fake_embedding == []


async def test_refresh_profile_embedding_sets_vector() -> None:
    profile = Profile(name="Data", structured_profile=VALID_PROFILE)

    assert await refresh_profile_embedding(profile) is True
    assert profile.embedding is not None
    assert len(profile.embedding) == 768


async def test_refresh_profile_embedding_survives_provider_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_aembedding(monkeypatch, lambda **kw: LLMError("provider down"))
    profile = Profile(name="Data", structured_profile=VALID_PROFILE)

    assert await refresh_profile_embedding(profile) is False
    assert profile.embedding is None


async def test_refresh_profile_embedding_skips_invalid_profile(
    fake_embedding: list[dict[str, object]],
) -> None:
    profile = Profile(id=uuid.uuid4(), name="Bad", structured_profile={"unexpected": "shape"})

    assert await refresh_profile_embedding(profile) is False
    assert profile.embedding is None
    assert fake_embedding == []
