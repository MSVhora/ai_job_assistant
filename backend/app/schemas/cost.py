from typing import Literal

from pydantic import BaseModel

from app.adapters.llm import CostEstimate

COST_UNAVAILABLE_MESSAGE = "cost unavailable for this model"


class CostEstimateResponse(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    usd: float | None
    basis: Literal["configured_prices", "litellm_price_map", "unavailable"]
    message: str | None = None

    @classmethod
    def from_estimate(cls, estimate: CostEstimate) -> "CostEstimateResponse":
        return cls(
            prompt_tokens=estimate.prompt_tokens,
            completion_tokens=estimate.completion_tokens,
            usd=estimate.usd,
            basis=estimate.basis,
            message=COST_UNAVAILABLE_MESSAGE if estimate.usd is None else None,
        )
