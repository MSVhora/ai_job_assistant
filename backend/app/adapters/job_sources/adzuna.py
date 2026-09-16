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
    SourceFilterDecl,
    SourceFilterOption,
    clean_text,
    parse_datetime,
)
from app.adapters.retry import Transient, retry_after_header, retryable_status, with_retry
from app.core.config import get_settings
from app.models import JobType

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.adzuna.com"
_TIMEOUT_S = 30.0
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
    """Map the rendering layer's term plan onto Adzuna's search params.

    Precedence table (normative copy in ``services/query_rendering.py``):
    ``what_phrase`` when a title exists; ``what_and``/``what_or`` combined
    with it; ``what_exclude`` whenever set; ``what`` (free text) only when
    there is no ``what_phrase``. No decisions are made here.
    """
    plan = query.term_plan
    if plan is None:
        if query.query:
            params["what"] = query.query
            return
        raise ConnectorError("adzuna search needs a query or a title phrase")
    if plan.what_phrase:
        params["what_phrase"] = plan.what_phrase
    if plan.what_and:
        params["what_and"] = " ".join(plan.what_and)
    if plan.what_or:
        params["what_or"] = " ".join(plan.what_or)
    if plan.what_exclude:
        params["what_exclude"] = " ".join(plan.what_exclude)
    if not plan.what_phrase and plan.what:
        params["what"] = plan.what
    if not any(key in params for key in ("what", "what_phrase", "what_and", "what_or")):
        raise ConnectorError("adzuna search needs a query or a title phrase")


def _apply_salary_filter(params: dict[str, str], query: JobSearchQuery) -> None:
    if query.salary_min is not None:
        params["salary_min"] = str(int(query.salary_min))
    if query.salary_max is not None:
        params["salary_max"] = str(int(query.salary_max))
    if query.salary_min is None:
        # No salary floor: include postings that don't publish salary, instead
        # of silently biasing results to companies that do (issue #34).
        params["salary_include_unknown"] = "1"


def _apply_freshness(params: dict[str, str], query: JobSearchQuery) -> None:
    if query.max_days_old is not None:
        params["max_days_old"] = str(query.max_days_old)


_SORT_BY_OPTIONS = (
    SourceFilterOption(value="relevance", label="Relevance"),
    SourceFilterOption(value="date", label="Date posted"),
    SourceFilterOption(value="salary", label="Salary"),
)

_FILTERS = [
    SourceFilterDecl(
        key="title_only",
        label="Title-only search",
        type="boolean",
        help_text="Match the title phrase only instead of the full description",
    ),
    SourceFilterDecl(
        key="full_time",
        label="Full-time only",
        type="boolean",
        help_text="Adzuna contract filter: keep full-time postings",
    ),
    SourceFilterDecl(
        key="part_time",
        label="Part-time only",
        type="boolean",
        help_text="Adzuna contract filter: keep part-time postings",
    ),
    SourceFilterDecl(
        key="contract",
        label="Contract only",
        type="boolean",
        help_text="Adzuna contract filter: keep contract postings",
    ),
    SourceFilterDecl(
        key="permanent",
        label="Permanent only",
        type="boolean",
        help_text="Adzuna contract filter: keep permanent postings",
    ),
    SourceFilterDecl(
        key="distance_km",
        label="Radius (km)",
        type="number",
        placeholder="25",
        help_text="Distance from the location to search within; requires a location",
    ),
    SourceFilterDecl(
        key="sort_by",
        label="Sort by",
        type="select",
        options=list(_SORT_BY_OPTIONS),
    ),
]

_CONTRACT_BOOL_KEYS = ("full_time", "part_time", "contract", "permanent")


def _apply_options(params: dict[str, str], query: JobSearchQuery) -> None:
    title_only = query.options.get("title_only")
    if title_only is True:
        params["title_only"] = "true"
    for key in _CONTRACT_BOOL_KEYS:
        if query.options.get(key) is True:
            params[key] = "true"
    distance_km = query.options.get("distance_km")
    if type(distance_km) is int and query.location:
        params["distance"] = str(distance_km)
    sort_by = query.options.get("sort_by")
    if type(sort_by) is str and sort_by in {option.value for option in _SORT_BY_OPTIONS}:
        params["sort_by"] = sort_by


class AdzunaJobSource:
    """Adzuna official-API connector.

    Search runs as a multi-pass run inside Adzuna's API dialect:

    - Pass 1 renders the term plan (``what_phrase`` + ``what_and``/``what_or``
      combined; ``what`` only when no phrase — normative precedence in
      ``services/query_rendering.py``).
    - Pass 2 (``title_only=true``) fires automatically when a title phrase
      exists and the user has not explicitly set ``title_only``, adding
      title-precision recall; merged results dedupe by ``external_id`` with
      the broad pass winning.
    - Pagination follows page 2 only when a page returns a full 50 rows and
      ``results_wanted`` is larger than what has been collected.

    Budget formula: **calls per run = Σ (sub-queries × pages)**. Every call
    beyond the first is gated on ``max_adzuna_calls_per_run`` (free tier:
    25/min, 250/day, 1000/wk, 2500/mo); when the budget is exhausted the run
    stops and logs rather than failing.
    """

    name = "adzuna"
    is_official_api = True
    disclosure_required = False
    supports_exclusions = True

    def __init__(self, client_factory: ClientFactory | None = None) -> None:
        self._client_factory: ClientFactory = client_factory or _default_client

    def is_configured(self) -> bool:
        settings = get_settings()
        return settings.adzuna_app_id is not None and settings.adzuna_app_key is not None

    def filters(self) -> list[SourceFilterDecl]:
        return list(_FILTERS)

    async def search(self, query: JobSearchQuery) -> list[RawJobPosting]:
        settings = get_settings()
        if not self.is_configured():
            raise ConnectorError("adzuna credentials are not configured")

        results_per_page = min(query.results_wanted, _MAX_RESULTS_PER_PAGE)
        params: dict[str, str] = {
            "app_id": settings.adzuna_app_id or "",
            "app_key": settings.adzuna_app_key or "",
            "results_per_page": str(results_per_page),
            "content-type": "application/json",
        }
        _apply_search_terms(params, query)
        _apply_salary_filter(params, query)
        _apply_freshness(params, query)
        _apply_options(params, query)
        if query.location:
            params["where"] = query.location
        url = f"{_BASE_URL}/v1/api/jobs/{query.country}/search"

        start = time.perf_counter()
        postings = await self._multi_pass_search(url, params, query, results_per_page)
        logger.info(
            "job_source.search source=adzuna duration_ms=%.0f fetched=%d country=%s",
            (time.perf_counter() - start) * 1000,
            len(postings),
            query.country,
        )
        return postings

    async def _multi_pass_search(
        self, url: str, params: dict[str, str], query: JobSearchQuery, results_per_page: int
    ) -> list[RawJobPosting]:
        plan = query.term_plan
        passes: list[dict[str, str]] = [{}]
        if plan is not None and plan.what_phrase and query.options.get("title_only") is not True:
            passes.append({"title_only": "true"})

        budget = get_settings().max_adzuna_calls_per_run
        calls = 0
        total_fetched = 0
        merged: dict[str, RawJobPosting] = {}
        for pass_params in passes:
            page = 1
            while True:
                calls += 1
                data = await self._get_json(url + f"/{page}", params | pass_params)
                page_results = self._extract_postings(data)
                total_fetched += len(page_results)
                for posting in page_results:
                    merged.setdefault(posting.external_id, posting)
                full_page = len(page_results) >= results_per_page
                more = full_page and len(merged) < query.results_wanted and calls < budget
                if not more:
                    break
                page += 1
        logger.info(
            "job_source.search source=adzuna multipass passes=%d calls=%d budget=%d "
            "raw_fetched=%d deduped=%d",
            len(passes),
            calls,
            budget,
            total_fetched,
            len(merged),
        )
        return list(merged.values())[: query.results_wanted]

    def _extract_postings(self, data: dict[str, Any]) -> list[RawJobPosting]:
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
        def _describe(exc: Exception) -> str:
            return f"transport error: {exc}" if isinstance(exc, httpx.HTTPError) else str(exc)

        try:
            async with self._client_factory() as client:

                async def _call() -> dict[str, Any]:
                    response = await client.get(url, params=params)
                    if response.status_code < 400:
                        try:
                            return response.json()
                        except ValueError as exc:
                            raise ConnectorError("adzuna returned invalid JSON") from exc
                    if retryable_status(response.status_code):
                        raise Transient(
                            f"status {response.status_code}",
                            retry_after_s=retry_after_header(response.headers.get("retry-after")),
                        )
                    raise ConnectorError(f"adzuna request failed (status {response.status_code})")

                return await with_retry("adzuna", _call, is_retryable=_is_retryable)
        except ConnectorError:
            raise
        except (httpx.HTTPError, Transient) as exc:
            raise ConnectorError(f"adzuna request failed ({_describe(exc)})") from exc


def _is_retryable(exc: Exception) -> bool:
    return isinstance(exc, (httpx.HTTPError, Transient))
