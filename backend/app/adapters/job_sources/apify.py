import asyncio
import importlib
import logging
import time
from collections.abc import Callable
from typing import Any

import httpx

from app.adapters.job_sources.base import (
    ClientFactory,
    ConnectorConfigError,
    ConnectorError,
    JobPostingData,
    JobSearchQuery,
    RawJobPosting,
)
from app.adapters.job_sources.config import ActorConfig, build_actor_input
from app.core.config import get_settings

logger = logging.getLogger(__name__)

_API_BASE = "https://api.apify.com"
_TIMEOUT_S = 30.0
_POLL_INTERVAL_S = 5.0
_MAX_WAIT_S = 600.0
_RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})
_RETRY_DELAY_S = 1.0
_TERMINAL_FAILURES = frozenset({"FAILED", "ABORTED", "TIMED-OUT"})

MapperFn = Callable[[RawJobPosting], JobPostingData]


def _default_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=_TIMEOUT_S)


def _format_amount(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return f"{value:f}".rstrip("0").rstrip(".")


def _natural_keywords(query: JobSearchQuery) -> str | None:
    """LinkedIn-style natural-language keywords from a structured spec.

    Exclusions are dropped: the actor input has no exclusion field and LinkedIn's
    AI search has no exclusion filter (capability table in the queries plan).
    """
    if not query.title_phrase:
        return None
    keywords = query.title_phrase
    if query.skills_any:
        keywords += f" with {' and '.join(query.skills_any)}"
    if query.salary_min is not None:
        currency = f" {query.salary_currency}" if query.salary_currency else ""
        keywords += f", offering{currency} {_format_amount(query.salary_min)} or more"
    return keywords


def _with_effective_query(query: JobSearchQuery) -> JobSearchQuery:
    keywords = _natural_keywords(query)
    if keywords is None:
        if not query.query:
            raise ConnectorError("search needs a query or a title phrase")
        return query
    return query.model_copy(update={"query": keywords})


def _load_mapper(source_name: str) -> MapperFn:
    module_name = f"app.adapters.job_sources.mappers.{source_name.removeprefix('apify_')}"
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        raise ConnectorConfigError(
            f"actor {source_name!r} has no mapper module ({module_name})"
        ) from exc
    mapper = getattr(module, "normalize", None)
    if not callable(mapper):
        raise ConnectorConfigError(f"mapper module {module_name} does not define normalize()")
    return mapper


class ApifyActorSource:
    is_official_api = False
    disclosure_required = True
    supports_exclusions = False

    def __init__(self, config: ActorConfig, client_factory: ClientFactory | None = None) -> None:
        self._config = config
        self.name = config.name
        self._client_factory: ClientFactory = client_factory or _default_client
        self._normalize = _load_mapper(config.name)

    def is_configured(self) -> bool:
        return get_settings().apify_token is not None

    async def search(self, query: JobSearchQuery) -> list[RawJobPosting]:
        token = get_settings().apify_token
        if token is None:
            raise ConnectorError(f"{self.name} token is not configured")

        started = time.perf_counter()
        effective = _with_effective_query(query)
        async with self._client_factory() as client:
            run = await self._request_json(
                client,
                "POST",
                f"/v2/acts/{self._config.actor_id}/runs",
                token,
                json_body=build_actor_input(self._config, effective),
            )
            run_id = run.get("id")
            if not isinstance(run_id, str) or not run_id:
                raise ConnectorError(f"{self.name}: actor run response has no id")

            run = await self._wait_for_run(client, run_id, token)
            dataset_id = run.get("defaultDatasetId")
            if not isinstance(dataset_id, str) or not dataset_id:
                raise ConnectorError(f"{self.name}: run has no default dataset")

            items = await self._request_json(
                client, "GET", f"/v2/datasets/{dataset_id}/items", token, params={"clean": "true"}
            )
        postings = self._to_raw_postings(items.get("items", []))
        logger.info(
            "job_source.search source=%s duration_ms=%.0f fetched=%d",
            self.name,
            (time.perf_counter() - started) * 1000,
            len(postings),
        )
        return postings

    def normalize(self, raw: RawJobPosting) -> JobPostingData:
        return self._normalize(raw)

    async def _wait_for_run(
        self, client: httpx.AsyncClient, run_id: str, token: str
    ) -> dict[str, Any]:
        deadline = time.monotonic() + _MAX_WAIT_S
        while True:
            run = await self._request_json(client, "GET", f"/v2/actor-runs/{run_id}", token)
            status = str(run.get("status", ""))
            if status == "SUCCEEDED":
                return run
            if status in _TERMINAL_FAILURES:
                raise ConnectorError(f"{self.name}: actor run ended with status {status}")
            if time.monotonic() >= deadline:
                raise ConnectorError(
                    f"{self.name}: actor run did not finish within {_MAX_WAIT_S:.0f}s"
                )
            await asyncio.sleep(_POLL_INTERVAL_S)

    def _to_raw_postings(self, items: object) -> list[RawJobPosting]:
        postings: list[RawJobPosting] = []
        if not isinstance(items, list):
            return postings
        for item in items:
            if not isinstance(item, dict):
                continue
            external_id = str(item.get(self._config.external_id_field, "")).strip()
            if not external_id:
                continue
            postings.append(RawJobPosting(external_id=external_id, payload=item))
        return postings

    async def _request_json(
        self,
        client: httpx.AsyncClient,
        method: str,
        path: str,
        token: str,
        *,
        params: dict[str, object] | None = None,
        json_body: dict[str, object] | None = None,
    ) -> dict[str, Any]:
        query = {"token": token, **(params or {})}
        last_error: str | None = None
        for attempt in range(2):
            try:
                response = await client.request(
                    method, f"{_API_BASE}{path}", params=query, json=json_body
                )
            except httpx.HTTPError as exc:
                last_error = f"transport error: {exc}"
            else:
                if response.status_code < 400:
                    return _unwrap_json(response, self.name)
                last_error = f"status {response.status_code}"
                if response.status_code not in _RETRYABLE_STATUS:
                    break
            if attempt == 0:
                await asyncio.sleep(_RETRY_DELAY_S)
        raise ConnectorError(f"{self.name} request failed ({last_error})")


def _unwrap_json(response: httpx.Response, source_name: str) -> dict[str, Any]:
    try:
        payload: object = response.json()
    except ValueError as exc:
        raise ConnectorError(f"{source_name} returned invalid JSON") from exc
    if isinstance(payload, list):
        return {"items": payload}
    if isinstance(payload, dict) and isinstance(payload.get("data"), dict):
        return payload["data"]
    return payload if isinstance(payload, dict) else {}
