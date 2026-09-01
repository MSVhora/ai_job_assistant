import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import get_settings
from app.main import app


@pytest.fixture
async def client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        yield async_client


def configure(
    monkeypatch: pytest.MonkeyPatch,
    *,
    gemini: str | None = "key",
    embedding_model: str = "gemini/text-embedding-004",
    adzuna: str | None = None,
    apify: str | None = None,
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "gemini_api_key", gemini)
    monkeypatch.setattr(settings, "embedding_model", embedding_model)
    monkeypatch.setattr(settings, "adzuna_app_id", adzuna)
    monkeypatch.setattr(settings, "adzuna_app_key", adzuna)
    monkeypatch.setattr(settings, "apify_token", apify)


async def test_setup_check_reports_configured_providers(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    configure(monkeypatch, adzuna="id", apify="token")

    response = await client.post("/api/setup/check")

    assert response.status_code == 200
    assert response.json() == {
        "llm_configured": True,
        "embedding_configured": True,
        "adzuna_configured": True,
        "apify_configured": True,
        "warnings": [],
    }


async def test_setup_check_warns_when_embedding_key_missing(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    configure(monkeypatch, gemini=None)

    response = await client.post("/api/setup/check")

    body = response.json()
    assert body["llm_configured"] is False
    assert body["embedding_configured"] is False
    assert len(body["warnings"]) == 1
    assert "embedding" in body["warnings"][0]


async def test_setup_check_warns_when_embedding_provider_cannot_embed(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    configure(monkeypatch, embedding_model="anthropic/claude-3-5-sonnet")

    response = await client.post("/api/setup/check")

    body = response.json()
    assert body["embedding_configured"] is False
    assert "cannot generate embeddings" in body["warnings"][0]


def test_blank_env_keys_count_as_unconfigured(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import Settings

    monkeypatch.setenv("ADZUNA_APP_ID", "")
    monkeypatch.setenv("ADZUNA_APP_KEY", "  ")
    monkeypatch.setenv("APIFY_TOKEN", "")

    settings = Settings(_env_file=None)

    assert settings.adzuna_app_id is None
    assert settings.adzuna_app_key is None
    assert settings.apify_token is None
