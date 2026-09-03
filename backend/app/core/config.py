from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/ai_job_assistant"
    cors_origins: list[str] = ["http://localhost:3000"]

    uploads_dir: Path = Path("./data/uploads")
    resume_max_upload_mb: int = 10

    gemini_api_key: str | None = None
    llm_model: str = "gemini/gemini-2.5-flash"
    embedding_model: str = "gemini/gemini-embedding-001"
    embedding_dimensions: int = 768
    extraction_max_chars: int = 20_000

    adzuna_app_id: str | None = None
    adzuna_app_key: str | None = None
    apify_token: str | None = None

    rerank_top_n: int = 10
    match_weight_vector: float = 0.4
    match_weight_role_fit: float = 0.4
    match_weight_company_fit: float = 0.2

    @field_validator(
        "gemini_api_key", "adzuna_app_id", "adzuna_app_key", "apify_token", mode="before"
    )
    @classmethod
    def _blank_to_none(cls, value: object) -> object:
        if isinstance(value, str) and value.strip() == "":
            return None
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
