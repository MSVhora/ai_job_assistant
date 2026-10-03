from pydantic import BaseModel


class SetupCheckResponse(BaseModel):
    llm_configured: bool
    embedding_configured: bool
    adzuna_configured: bool
    apify_configured: bool
    github_token_configured: bool
    task_models: dict[str, str] = {}
    warnings: list[str] = []
