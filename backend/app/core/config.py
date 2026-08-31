from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/ai_job_assistant"
    cors_origins: list[str] = ["http://localhost:3000"]

    gemini_api_key: str | None = None
    llm_model: str = "gemini/gemini-2.5-flash"
    embedding_model: str = "gemini/text-embedding-004"

    adzuna_app_id: str | None = None
    adzuna_app_key: str | None = None
    apify_token: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
