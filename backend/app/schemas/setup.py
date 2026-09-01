from pydantic import BaseModel


class SetupCheckResponse(BaseModel):
    llm_configured: bool
    embedding_configured: bool
    adzuna_configured: bool
    apify_configured: bool
    warnings: list[str] = []
