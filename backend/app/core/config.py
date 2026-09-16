from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator
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
    # Outbound retry policy shared by LLM calls and job-source HTTP calls.
    llm_retry_attempts: int = 3
    llm_retry_base_delay_s: float = 1.0

    adzuna_app_id: str | None = None
    adzuna_app_key: str | None = None
    # Issue #34: max HTTP calls per Adzuna run (Σ sub-queries × pages) — keeps
    # multi-pass runs inside Adzuna's free tier (25/min, 250/day).
    max_adzuna_calls_per_run: Annotated[int, Field(ge=1, le=8)] = 4
    apify_token: str | None = None
    # Issue #35: per-run billed-results cap for Apify actors (they bill per
    # result via limitPerSource); a guard above the request schema cap (100).
    max_apify_results_per_run: Annotated[int, Field(ge=1, le=1000)] = 250

    rerank_top_n: int = 10
    # Issue #36: runs stuck in pending/running for longer than this are
    # marked failed by the start_search sweeper, releasing the active-run
    # (profile, source) lock.
    max_run_age_minutes: Annotated[int, Field(ge=1)] = 30
    match_weight_vector: float = 0.4
    match_weight_role_fit: float = 0.4
    match_weight_company_fit: float = 0.2

    # Read-side freshness grace window (D4): postings without a source-reported
    # expiry become stale after this many days since posting.
    stale_posting_days: Annotated[int, Field(ge=1)] = 45

    # Seniority derivation bands from years_of_experience (issue #32): a YOE
    # below the next band's threshold maps down. 0-1 → junior, 2-4 → mid,
    # 5-7 → senior, 8-11 → staff, 12+ → principal (defaults).
    seniority_band_mid: Annotated[int, Field(ge=0)] = 2
    seniority_band_senior: Annotated[int, Field(ge=0)] = 5
    seniority_band_staff: Annotated[int, Field(ge=0)] = 8
    seniority_band_principal: Annotated[int, Field(ge=0)] = 12

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
