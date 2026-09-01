from app.core.config import Settings, get_settings
from app.schemas.setup import SetupCheckResponse

_EMBEDDING_UNABLE = (
    "the configured embedding model provider cannot generate embeddings; "
    "job matching needs an embedding-capable provider (e.g. Gemini)"
)
_EMBEDDING_KEY_MISSING = "no API key configured for the embedding provider"


def check() -> SetupCheckResponse:
    settings = get_settings()
    llm_provider = settings.llm_model.split("/", 1)[0]
    embedding_provider = settings.embedding_model.split("/", 1)[0]
    warnings: list[str] = []

    llm_configured = _provider_key(settings, llm_provider) is not None
    embedding_configured = _provider_key(settings, embedding_provider) is not None
    if embedding_provider == "anthropic":
        warnings.append(_EMBEDDING_UNABLE)
    elif embedding_configured is False:
        warnings.append(_EMBEDDING_KEY_MISSING)

    return SetupCheckResponse(
        llm_configured=llm_configured,
        embedding_configured=embedding_configured,
        adzuna_configured=settings.adzuna_app_id is not None
        and settings.adzuna_app_key is not None,
        apify_configured=settings.apify_token is not None,
        warnings=warnings,
    )


def _provider_key(settings: Settings, provider: str) -> str | None:
    if provider == "gemini":
        return settings.gemini_api_key
    return None
