import math
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, ValidationInfo, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_MATCH_WEIGHTS = (
    "match_weight_vector",
    "match_weight_skill",
    "match_weight_recency",
    "match_weight_role_fit",
    "match_weight_company_fit",
    "match_weight_salary",
)


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
    llm_timeout_s: Annotated[float, Field(gt=0, le=600)] = 60.0
    # v6 #49: optional per-task model overrides (blank = llm_model) and a cap on concurrent
    # provider calls so a long extraction stays inside free-tier RPM limits.
    llm_model_classify: str | None = None
    llm_model_extract: str | None = None
    llm_model_write: str | None = None
    llm_model_judge: str | None = None
    llm_max_concurrency: Annotated[int, Field(ge=1, le=16)] = 4
    # Extraction runs this many chunks at once (bounded by llm_max_concurrency and the DB pool);
    # chunks shorter than the minimum carry too little to extract and are skipped (0 = none).
    extraction_concurrency: Annotated[int, Field(ge=1, le=8)] = 4
    extraction_min_chunk_chars: Annotated[int, Field(ge=0, le=5000)] = 200
    evidence_redaction_enabled: bool = True
    # Optional USD-per-million-token overrides for models LiteLLM's price map lacks or has stale.
    llm_price_in_per_mtok: Annotated[float | None, Field(ge=0)] = None
    llm_price_out_per_mtok: Annotated[float | None, Field(ge=0)] = None
    embedding_price_per_mtok: Annotated[float | None, Field(ge=0)] = None

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
    match_weight_vector: float = 0.35
    match_weight_skill: float = 0.25
    match_weight_recency: float = 0.15
    match_weight_role_fit: float = 0.15
    match_weight_company_fit: float = 0.05
    match_weight_salary: float = 0.05
    # Issue #37: recency decay on posted_at — exp(-days/decay_days); unknown
    # dates score 0.5 (neutral) so they keep surfacing.
    match_recency_decay_days: Annotated[int, Field(ge=1)] = 14
    # Issue #37: how many of the profile's top skills feed the SQL skill-hit
    # signal (the array is bound into every rescore pass).
    match_skill_signal_skills: Annotated[int, Field(ge=1)] = 25

    # Issue #39 tune-my-queries: max aggregated terms per category per signal
    # bucket in the LLM prompt (keeps the manual call's prompt bounded).
    tune_query_top_terms: Annotated[int, Field(ge=1)] = 10

    # Issue #38: pg_trgm title similarity threshold for cross-source canonical
    # grouping (1.0 = exact titles only, the honest "disable").
    posting_dedupe_similarity: Annotated[float, Field(ge=0.0, le=1.0)] = 0.92

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

    # v6 #48: GitHub evidence connector. The token (fine-grained or classic, read-only use)
    # is kept in .env only; the request budget and rate-limit floor pause a run before GitHub does.
    github_token: str | None = None
    github_api_url: str = "https://api.github.com"
    # Repositories synced at once; the shared request budget and rate-limit floor still apply.
    evidence_sync_concurrency: Annotated[int, Field(ge=1, le=6)] = 3
    github_max_requests_per_run: Annotated[int, Field(ge=1, le=5000)] = 1500
    github_min_remaining_pct: Annotated[int, Field(ge=0, le=90)] = 10
    evidence_lookback_years: Annotated[int, Field(ge=1, le=30)] = 6
    # v6 #54: two employment roles overlapping by at least this many days are flagged.
    resume_overlap_min_days: Annotated[int, Field(ge=1, le=366)] = 60
    # v6 #55: the JD is a bounded boost on a JD-independent base priority (impact, difficulty,
    # recency; weights sum to 1); bullets are written for budget x oversample candidates.
    resume_jd_weight: Annotated[float, Field(ge=0, le=0.5)] = 0.30
    resume_weight_impact: Annotated[float, Field(ge=0, le=1)] = 0.45
    resume_weight_difficulty: Annotated[float, Field(ge=0, le=1)] = 0.35
    resume_weight_recency: Annotated[float, Field(ge=0, le=1)] = 0.20
    resume_candidate_oversample: Annotated[float, Field(ge=1, le=3)] = 1.3
    resume_max_pages: Annotated[int, Field(ge=1, le=4)] = 4
    # v6 #56: upper bound on Typst compiles one page-fit run may spend (3 presets x ~7 each).
    resume_fit_max_compiles: Annotated[int, Field(ge=3, le=200)] = 30
    # v6 #58: interview agent. Retrieval score = weighted cosine + skill overlap + recency +
    # impact over approved achievements; below the floor the agent says it has no evidence.
    agent_history_turns: Annotated[int, Field(ge=1, le=20)] = 6
    agent_min_retrieval_score: Annotated[float, Field(ge=0, le=1)] = 0.30
    agent_weight_cosine: Annotated[float, Field(ge=0, le=1)] = 0.55
    agent_weight_overlap: Annotated[float, Field(ge=0, le=1)] = 0.25
    agent_weight_recency: Annotated[float, Field(ge=0, le=1)] = 0.10
    agent_weight_impact: Annotated[float, Field(ge=0, le=1)] = 0.10
    evidence_bot_logins: list[str] = [
        "dependabot",
        "renovate",
        "github-actions",
        "snyk-bot",
        "greenkeeper",
        "imgbot",
    ]

    @field_validator(
        "gemini_api_key",
        "adzuna_app_id",
        "adzuna_app_key",
        "apify_token",
        "github_token",
        "llm_model_classify",
        "llm_model_extract",
        "llm_model_write",
        "llm_model_judge",
        mode="before",
    )
    @classmethod
    def _blank_to_none(cls, value: object) -> object:
        if isinstance(value, str) and value.strip() == "":
            return None
        return value

    @field_validator(
        "match_weight_vector",
        "match_weight_skill",
        "match_weight_recency",
        "match_weight_role_fit",
        "match_weight_company_fit",
        "match_weight_salary",
        mode="after",
    )
    @classmethod
    def _check_weight_sum(cls, value: float, info: ValidationInfo) -> float:
        weights = {**info.data, info.field_name: value}
        if not all(name in weights for name in _MATCH_WEIGHTS):
            return value
        total = sum(weights[name] for name in _MATCH_WEIGHTS)
        if not math.isclose(total, 1.0, rel_tol=0.0, abs_tol=0.01):
            msg = (
                f"match weights must sum to 1.0 (±0.01), got {total:.4f} from "
                f"{ {name: weights[name] for name in _MATCH_WEIGHTS} }"
            )
            raise ValueError(msg)
        return value

    @model_validator(mode="after")
    def _check_resume_priority_weights(self) -> "Settings":
        total = (
            self.resume_weight_impact + self.resume_weight_difficulty + self.resume_weight_recency
        )
        if not math.isclose(total, 1.0, rel_tol=0.0, abs_tol=0.01):
            msg = f"resume priority weights must sum to 1.0 (±0.01), got {total:.4f}"
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _check_agent_weights(self) -> "Settings":
        total = (
            self.agent_weight_cosine
            + self.agent_weight_overlap
            + self.agent_weight_recency
            + self.agent_weight_impact
        )
        if not math.isclose(total, 1.0, rel_tol=0.0, abs_tol=0.01):
            msg = f"agent retrieval weights must sum to 1.0 (±0.01), got {total:.4f}"
            raise ValueError(msg)
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
