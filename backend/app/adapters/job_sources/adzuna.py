import asyncio
import logging
import time
from typing import Any

import httpx
from pydantic import ValidationError

from app.adapters.job_sources.base import (
    ClientFactory,
    ConnectorError,
    JobPostingData,
    JobSearchQuery,
    RawJobPosting,
    clean_text,
    parse_datetime,
)
from app.core.config import get_settings
from app.models import JobType

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.adzuna.com"
_TIMEOUT_S = 30.0
_RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})
_RETRY_DELAY_S = 1.0
_MAX_RESULTS_PER_PAGE = 50

_CONTRACT_TIME_MAP: dict[str, JobType] = {
    "full_time": JobType.full_time,
    "part_time": JobType.part_time,
}
_CONTRACT_TYPE_MAP: dict[str, JobType] = {
    "contract": JobType.contract,
    "internship": JobType.internship,
    "temporary": JobType.temporary,
}


def _clean_salary(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value) if value >= 0 else None


def _job_type(payload: dict[str, Any]) -> JobType | None:
    contract_time = payload.get("contract_time")
    if isinstance(contract_time, str) and contract_time in _CONTRACT_TIME_MAP:
        return _CONTRACT_TIME_MAP[contract_time]
    contract_type = payload.get("contract_type")
    if isinstance(contract_type, str) and contract_type in _CONTRACT_TYPE_MAP:
        return _CONTRACT_TYPE_MAP[contract_type]
    return None


def _default_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=_TIMEOUT_S)


def _apply_search_terms(params: dict[str, str], query: JobSearchQuery) -> None:
    if query.title_phrase:
        params["what_phrase"] = query.title_phrase
        if query.skills_any:
            params["what_or"] = " ".join(query.skills_any)
        if query.exclude_any:
            params["what_exclude"] = " ".join(query.exclude_any)
        return
    if query.query:
        params["what"] = query.query
        return
    raise ConnectorError("adzuna search needs a query or a title phrase")


def _apply_salary_filter(params: dict[str, str], query: JobSearchQuery) -> None:
    if query.salary_min is not None:
        params["salary_min"] = str(int(query.salary_min))
    if query.salary_max is not None:
        params["salary_max"] = str(int(query.salary_max))


class AdzunaJobSource:
    name = "adzuna"
    is_official_api = True
    disclosure_required = False
    supports_exclusions = True

    def __init__(self, client_factory: ClientFactory | None = None) -> None:
        self._client_factory: ClientFactory = client_factory or _default_client

    def is_configured(self) -> bool:
        settings = get_settings()
        return settings.adzuna_app_id is not None and settings.adzuna_app_key is not None

    async def search(self, query: JobSearchQuery) -> list[RawJobPosting]:
        settings = get_settings()
        if not self.is_configured():
            raise ConnectorError("adzuna credentials are not configured")

        params: dict[str, str] = {
            "app_id": settings.adzuna_app_id or "",
            "app_key": settings.adzuna_app_key or "",
            "results_per_page": str(min(query.results_wanted, _MAX_RESULTS_PER_PAGE)),
            "content-type": "application/json",
        }
        _apply_search_terms(params, query)
        _apply_salary_filter(params, query)
        if query.location:
            params["where"] = query.location
        url = f"{_BASE_URL}/v1/api/jobs/{query.country}/search/1"

        start = time.perf_counter()
        data = await self._get_json(url, params)
        results = data.get("results")
        postings: list[RawJobPosting] = []
        if isinstance(results, list):
            for item in results:
                if not isinstance(item, dict):
                    continue
                external_id = str(item.get("id", "")).strip()
                if not external_id:
                    continue
                postings.append(RawJobPosting(external_id=external_id, payload=item))
        logger.info(
            "job_source.search source=adzuna duration_ms=%.0f fetched=%d country=%s",
            (time.perf_counter() - start) * 1000,
            len(postings),
            query.country,
        )
        return postings

    def normalize(self, raw: RawJobPosting) -> JobPostingData:
        payload = raw.payload
        title = clean_text(payload.get("title"))
        if title is None:
            raise ConnectorError("adzuna posting has no title")
        company = payload.get("company")
        location = payload.get("location")
        try:
            return JobPostingData(
                external_id=raw.external_id,
                title=title,
                company=clean_text(
                    company.get("display_name") if isinstance(company, dict) else company
                ),
                url=clean_text(payload.get("redirect_url")),
                location=clean_text(
                    location.get("display_name") if isinstance(location, dict) else location
                ),
                job_type=_job_type(payload),
                description=clean_text(payload.get("description")),
                posted_at=parse_datetime(payload.get("created")),
                salary_min=_clean_salary(payload.get("salary_min")),
                salary_max=_clean_salary(payload.get("salary_max")),
                raw_payload=payload,
            )
        except ValidationError as exc:
            raise ConnectorError(f"adzuna posting failed normalization: {exc}") from exc

    async def _get_json(self, url: str, params: dict[str, str]) -> dict[str, Any]:
        last_error: str | None = None
        async with self._client_factory() as client:
            for attempt in range(2):
                try:
                    response = await client.get(url, params=params)
                except httpx.HTTPError as exc:
                    last_error = f"transport error: {exc}"
                else:
                    if response.status_code < 400:
                        try:
                            data: dict[str, Any] = response.json()
                        except ValueError as exc:
                            raise ConnectorError("adzuna returned invalid JSON") from exc
                        return data
                    last_error = f"status {response.status_code}"
                    if response.status_code not in _RETRYABLE_STATUS:
                        break
                if attempt == 0:
                    await asyncio.sleep(_RETRY_DELAY_S)
        raise ConnectorError(f"adzuna request failed ({last_error})")
